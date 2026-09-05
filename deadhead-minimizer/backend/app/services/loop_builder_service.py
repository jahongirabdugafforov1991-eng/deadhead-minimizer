"""
Triangulation Loop Builder — deterministic, no LLM involved.

Approach: greedy nearest-value circuit search over KMA centroids.
  - At each leg, candidate next-hops are KMAs within [min_leg_miles, max_leg_miles]
    of the truck's current position, excluding already-visited KMAs.
  - Non-final legs are scored by a value function that rewards high avg_outbound_rpm
    and penalizes soft/dead zones — we want the truck landing in strong markets, not
    just wherever is closest.
  - The FINAL leg is scored differently: among valid candidates, we prefer the one
    closest to the original origin, so the loop actually closes and the truck is
    repositioned to run the same loop again next week (that's the "weekly loop"
    property triangulation is supposed to deliver, not just a random walk).

This is an orienteering-style greedy heuristic, not a global optimum (that would be
an NP-hard combinatorial search). Good enough for MVP; swap in a beam search or
OR-Tools VRP solver later if greedy loops turn out suboptimal in practice.
"""

import math
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EquipmentType, ZoneClassification
from app.schemas.loop import LoopLeg, LoopPlanResponse
from app.services.deadhead_service import GeocodingError, GeoPoint, geocode_destination

EARTH_RADIUS_MILES = 3958.8

# Multiplier applied to a KMA's avg_outbound_rpm when scoring candidates —
# rewards landing in genuinely hot markets over merely "closest" markets.
ZONE_VALUE_WEIGHT: dict[ZoneClassification, float] = {
    ZoneClassification.HOT: 1.25,
    ZoneClassification.BALANCED: 1.05,
    ZoneClassification.SOFT: 0.85,
    ZoneClassification.DEAD: 0.55,
}


@dataclass
class KmaNode:
    kma_code: str
    kma_name: str
    lat: float
    lon: float
    avg_outbound_rpm: float | None
    zone_classification: ZoneClassification


class LoopPlanningError(ValueError):
    """Raised when no viable loop can be built from the available KMA data."""


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


async def _fetch_kma_nodes(db: AsyncSession, equipment_type: EquipmentType) -> list[KmaNode]:
    stmt = text(
        """
        SELECT kma_code, kma_name,
               ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lon,
               avg_outbound_rpm, zone_classification
        FROM kma_heatmaps
        WHERE equipment_type = :equipment_type
        """
    )
    result = await db.execute(stmt, {"equipment_type": equipment_type.value})
    return [
        KmaNode(
            kma_code=row.kma_code,
            kma_name=row.kma_name,
            lat=row.lat,
            lon=row.lon,
            avg_outbound_rpm=float(row.avg_outbound_rpm) if row.avg_outbound_rpm is not None else None,
            zone_classification=ZoneClassification(row.zone_classification),
        )
        for row in result.mappings().all()
    ]


def _score_candidate(node: KmaNode, distance: float, is_final_leg: bool, origin: GeoPoint) -> float:
    """Higher is better. Final leg prioritizes closing the loop over pure RPM value."""
    rpm = node.avg_outbound_rpm or 1.0
    zone_weight = ZONE_VALUE_WEIGHT[node.zone_classification]

    if is_final_leg:
        distance_home = _haversine_miles(node.lat, node.lon, origin.lat, origin.lon)
        # Reward proximity to origin heavily, but still let RPM/zone quality break ties
        return (rpm * zone_weight) - (distance_home * 0.05)

    return rpm * zone_weight


async def build_triangulation_loop(
    db: AsyncSession,
    origin_query: str,
    equipment_type: EquipmentType,
    num_legs: int,
    min_leg_miles: float,
    max_leg_miles: float,
) -> LoopPlanResponse:
    origin = await geocode_destination(db, origin_query)
    nodes = await _fetch_kma_nodes(db, equipment_type)

    if len(nodes) < num_legs:
        raise LoopPlanningError(
            f"Only {len(nodes)} KMAs seeded for equipment_type='{equipment_type.value}' — "
            f"need at least {num_legs} to build a {num_legs}-leg loop."
        )

    legs: list[LoopLeg] = []
    visited_codes: set[str] = set()
    current_label = origin.label
    current_lat, current_lon = origin.lat, origin.lon
    current_code = "ORIGIN"

    for leg_number in range(1, num_legs + 1):
        is_final_leg = leg_number == num_legs

        candidates = [
            (node, _haversine_miles(current_lat, current_lon, node.lat, node.lon))
            for node in nodes
            if node.kma_code not in visited_codes
        ]
        candidates = [(n, d) for n, d in candidates if min_leg_miles <= d <= max_leg_miles]

        if not candidates:
            raise LoopPlanningError(
                f"No viable KMA found for leg {leg_number} within "
                f"[{min_leg_miles}, {max_leg_miles}] miles of '{current_label}'. "
                "Try widening min/max_leg_miles or seeding more KMAs."
            )

        best_node, best_distance = max(
            candidates, key=lambda pair: _score_candidate(pair[0], pair[1], is_final_leg, origin)
        )

        rpm = best_node.avg_outbound_rpm or 0.0
        revenue = round(rpm * best_distance, 2)

        legs.append(
            LoopLeg(
                leg_number=leg_number,
                from_kma_code=current_code,
                from_kma_name=current_label,
                to_kma_code=best_node.kma_code,
                to_kma_name=best_node.kma_name,
                distance_miles=round(best_distance, 1),
                rpm_usd=rpm,
                estimated_revenue_usd=revenue,
                to_zone_classification=best_node.zone_classification,
            )
        )

        visited_codes.add(best_node.kma_code)
        current_code, current_label = best_node.kma_code, best_node.kma_name
        current_lat, current_lon = best_node.lat, best_node.lon

    total_miles = sum(leg.distance_miles for leg in legs)
    total_revenue = sum(leg.estimated_revenue_usd for leg in legs)
    blended_rpm = round(total_revenue / total_miles, 2) if total_miles > 0 else 0.0
    closes_near_origin = _haversine_miles(current_lat, current_lon, origin.lat, origin.lon) <= max_leg_miles

    return LoopPlanResponse(
        origin_resolved=origin.label,
        equipment_type=equipment_type,
        legs=legs,
        total_miles=round(total_miles, 1),
        total_estimated_revenue_usd=round(total_revenue, 2),
        blended_rpm_usd=blended_rpm,
        closes_near_origin=closes_near_origin,
    )
