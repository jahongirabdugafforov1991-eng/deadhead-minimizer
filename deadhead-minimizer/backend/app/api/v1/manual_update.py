"""
Manual market update endpoint.

This is the pilot's substitute for automated DAT ingestion. A dispatcher (or
an ops person) periodically types in "here's what the board looks like right
now" for the markets their fleet operates in. It writes to the exact same
`kma_heatmaps` table the real DAT pipeline will write to later — so the map,
the deadhead endpoint, and the loop builder all keep working unmodified once
real ingestion replaces this screen.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import EquipmentType
from app.models.kma_heatmap import KmaHeatmap
from app.schemas.manual_update import ManualKmaUpdateBatch, ManualKmaUpdateResult
from app.schemas.markets import MarketPoint

router = APIRouter(prefix="/markets", tags=["manual-data"])


@router.get("/heatmap", response_model=list[MarketPoint])
async def get_heatmap(
    equipment_type: EquipmentType,
    db: AsyncSession = Depends(get_db),
) -> list[MarketPoint]:
    """
    Returns every tracked market's current snapshot for the map — centroid
    coordinates, ratio, zone, and rate. The frontend renders these as
    colored circle markers (see the note on HeatmapLayer re: real polygon
    boundaries not being available yet).
    """
    stmt = text(
        """
        SELECT kma_code, kma_name, zip3,
               ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lon,
               load_count, truck_count, load_to_truck_ratio,
               avg_outbound_rpm, zone_classification, updated_at
        FROM kma_heatmaps
        WHERE equipment_type = :equipment_type
        ORDER BY load_to_truck_ratio DESC
        """
    )
    result = await db.execute(stmt, {"equipment_type": equipment_type.value})
    rows = result.mappings().all()

    return [
        MarketPoint(
            kma_code=row["kma_code"],
            kma_name=row["kma_name"],
            zip3=row["zip3"],
            lat=row["lat"],
            lon=row["lon"],
            load_count=row["load_count"],
            truck_count=row["truck_count"],
            load_to_truck_ratio=float(row["load_to_truck_ratio"]),
            avg_outbound_rpm=float(row["avg_outbound_rpm"]) if row["avg_outbound_rpm"] is not None else None,
            zone_classification=row["zone_classification"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("/manual-update", response_model=list[ManualKmaUpdateResult])
async def manual_update_markets(
    payload: ManualKmaUpdateBatch,
    db: AsyncSession = Depends(get_db),
) -> list[ManualKmaUpdateResult]:
    """
    Update load/truck counts for one or more markets by hand.
    Only updates markets that already exist in kma_heatmaps (created via the
    seed script or a prior full record) — this endpoint adjusts counts on
    existing markets rather than creating brand-new ones from scratch.
    """
    results: list[ManualKmaUpdateResult] = []

    for update in payload.updates:
        ratio = round(update.load_count / update.truck_count, 2) if update.truck_count > 0 else 99.99
        zone = KmaHeatmap.classify(ratio).value

        # Fetch the current zone before overwriting it, so we can detect a real
        # shift (e.g. balanced -> hot) and log it as an activity event below.
        prior = await db.execute(
            text(
                "SELECT zone_classification, kma_name FROM kma_heatmaps "
                "WHERE kma_code = :kma_code AND equipment_type = :equipment_type"
            ),
            {"kma_code": update.kma_code, "equipment_type": update.equipment_type.value},
        )
        prior_row = prior.mappings().first()
        prior_zone = prior_row["zone_classification"] if prior_row else None
        kma_name = prior_row["kma_name"] if prior_row else update.kma_code

        stmt = text(
            """
            UPDATE kma_heatmaps
            SET load_count = :load_count,
                truck_count = :truck_count,
                load_to_truck_ratio = :ratio,
                avg_outbound_rpm = COALESCE(:avg_outbound_rpm, avg_outbound_rpm),
                zone_classification = :zone_classification,
                source = 'manual_entry',
                updated_at = now()
            WHERE kma_code = :kma_code AND equipment_type = :equipment_type
            RETURNING kma_code
            """
        )
        result = await db.execute(
            stmt,
            {
                "load_count": update.load_count,
                "truck_count": update.truck_count,
                "ratio": ratio,
                "avg_outbound_rpm": update.avg_outbound_rpm,
                "zone_classification": zone,
                "kma_code": update.kma_code,
                "equipment_type": update.equipment_type.value,
            },
        )
        row = result.first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Market '{update.kma_code}' ({update.equipment_type.value}) doesn't exist yet. "
                    "Add it via the seed script first, then use this endpoint to keep it updated."
                ),
            )

        results.append(
            ManualKmaUpdateResult(
                kma_code=update.kma_code,
                equipment_type=update.equipment_type,
                load_to_truck_ratio=ratio,
                zone_classification=zone,
                updated=True,
            )
        )

        # Log an activity event when the zone genuinely changed — this is what
        # feeds the dashboard's live activity log, no manual step required.
        if prior_zone is not None and prior_zone != zone:
            event_type = "dead_zone_warning" if zone == "dead" else "zone_shift"
            message = f"Ratio shift: {kma_name} now {ratio:.2f}x ({zone}, was {prior_zone})"
            await db.execute(
                text(
                    "INSERT INTO system_events (event_type, message, kma_code) "
                    "VALUES (:event_type, :message, :kma_code)"
                ),
                {"event_type": event_type, "message": message, "kma_code": update.kma_code},
            )

    await db.commit()
    return results
