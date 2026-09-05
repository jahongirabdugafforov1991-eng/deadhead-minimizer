"""
Deadhead relocation analysis.

Flow:
  1. Resolve the incoming destination string (City/ST or ZIP) to a lat/lon point.
  2. Run a PostGIS ST_DWithin radius query against `kma_heatmaps` centroids for the
     requested equipment type, ordered by distance.
  3. Score each candidate KMA by net RPM arbitrage vs. the truck's current load RPM.
  4. Return ranked relocation options.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import EquipmentType, ZoneClassification
from app.schemas.routing import RelocationOption

settings = get_settings()

# Flat baseline operating cost per deadhead mile (fuel + maintenance amortization,
# excludes driver pay since that's owed regardless of loaded/empty).
# Swap this for a per-carrier configurable value once cost accounting is wired up.
DEADHEAD_COST_PER_MILE_USD = 0.65

METERS_PER_MILE = 1609.34


@dataclass
class GeoPoint:
    label: str
    lat: float
    lon: float


class GeocodingError(ValueError):
    """Raised when the destination query can't be resolved to a coordinate."""


async def geocode_destination(db: AsyncSession, destination_query: str) -> GeoPoint:
    """
    Resolve a 'City, ST' or 5-digit ZIP string to coordinates.

    Production note: this currently resolves against the zip3 centroids we already
    store in `kma_heatmaps` (fast, no external call, but only 3-digit precision).
    For full 5-digit / free-text geocoding, swap this for a call to the Mapbox
    Geocoding API using the same MAPBOX token the frontend uses — keep the
    GeoPoint return contract identical so the rest of the pipeline doesn't change.
    """
    query = destination_query.strip()

    zip3 = query[:3] if query.isdigit() else None

    if zip3:
        stmt = text(
            """
            SELECT kma_name, ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lon
            FROM kma_heatmaps
            WHERE zip3 = :zip3
            LIMIT 1
            """
        )
        result = await db.execute(stmt, {"zip3": zip3})
    else:
        # "City, ST" free text — match against kma_name (e.g. "Atlanta, GA")
        stmt = text(
            """
            SELECT kma_name, ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lon
            FROM kma_heatmaps
            WHERE kma_name ILIKE :pattern
            LIMIT 1
            """
        )
        result = await db.execute(stmt, {"pattern": f"%{query}%"})

    row = result.first()
    if row is None:
        raise GeocodingError(
            f"Could not resolve destination '{destination_query}' against known KMAs. "
            "Wire up the Mapbox Geocoding API fallback for arbitrary addresses."
        )

    return GeoPoint(label=row.kma_name, lat=row.lat, lon=row.lon)


async def find_relocation_options(
    db: AsyncSession,
    origin: GeoPoint,
    equipment_type: EquipmentType,
    radius_miles: float,
    current_rpm: float | None,
    max_results: int,
) -> list[RelocationOption]:
    """
    PostGIS radius search: find candidate KMAs within `radius_miles` of `origin`,
    for the given equipment type, ranked by distance.

    ST_DWithin on a `geography` column takes meters and correctly accounts for
    the earth's curvature — this is why the centroid column is typed geography
    rather than geometry.
    """
    radius_meters = radius_miles * METERS_PER_MILE

    stmt = text(
        """
        SELECT
            kma_code,
            kma_name,
            zip3,
            load_to_truck_ratio,
            avg_outbound_rpm,
            zone_classification,
            ST_Distance(
                centroid,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) / :meters_per_mile AS distance_miles
        FROM kma_heatmaps
        WHERE equipment_type = :equipment_type
          AND ST_DWithin(
                centroid,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_meters
              )
        ORDER BY distance_miles ASC
        LIMIT :max_results
        """
    )

    result = await db.execute(
        stmt,
        {
            "lon": origin.lon,
            "lat": origin.lat,
            "radius_meters": radius_meters,
            "meters_per_mile": METERS_PER_MILE,
            "equipment_type": equipment_type.value,
            "max_results": max_results,
        },
    )
    rows = result.mappings().all()

    options: list[RelocationOption] = []
    for row in rows:
        deadhead_miles = float(row["distance_miles"])
        deadhead_cost = round(deadhead_miles * DEADHEAD_COST_PER_MILE_USD, 2)
        avg_outbound_rpm = float(row["avg_outbound_rpm"]) if row["avg_outbound_rpm"] is not None else None

        net_arbitrage = _compute_net_arbitrage(
            avg_outbound_rpm=avg_outbound_rpm,
            deadhead_miles=deadhead_miles,
            deadhead_cost=deadhead_cost,
            current_rpm=current_rpm,
        )

        zone = ZoneClassification(row["zone_classification"])
        options.append(
            RelocationOption(
                kma_code=row["kma_code"],
                kma_name=row["kma_name"],
                zip3=row["zip3"],
                zone_classification=zone,
                deadhead_miles=round(deadhead_miles, 1),
                load_to_truck_ratio=float(row["load_to_truck_ratio"]),
                avg_outbound_rpm=avg_outbound_rpm,
                deadhead_cost_estimate_usd=deadhead_cost,
                net_rpm_arbitrage=net_arbitrage,
                recommended=_is_recommended(zone, net_arbitrage),
            )
        )

    # Rank by net arbitrage when we have it, otherwise by ratio — highest value first.
    options.sort(
        key=lambda o: (o.net_rpm_arbitrage if o.net_rpm_arbitrage is not None else o.load_to_truck_ratio),
        reverse=True,
    )
    return options


def _compute_net_arbitrage(
    avg_outbound_rpm: float | None,
    deadhead_miles: float,
    deadhead_cost: float,
    current_rpm: float | None,
) -> float | None:
    """
    Net RPM arbitrage = value of relocating here vs. sitting in the current dead zone.

    We amortize the deadhead cost across a nominal 500-mile next loaded leg (a
    reasonable average haul length) to express it as an RPM-equivalent drag, then
    compare the resulting effective RPM against the truck's current load RPM.
    """
    if avg_outbound_rpm is None or current_rpm is None:
        return None

    NOMINAL_NEXT_LEG_MILES = 500
    deadhead_drag_rpm = deadhead_cost / NOMINAL_NEXT_LEG_MILES
    effective_rpm = avg_outbound_rpm - deadhead_drag_rpm

    return round(effective_rpm - current_rpm, 2)


def _is_recommended(zone: ZoneClassification, net_arbitrage: float | None) -> bool:
    if zone in (ZoneClassification.HOT, ZoneClassification.BALANCED):
        return net_arbitrage is None or net_arbitrage > 0
    return False
