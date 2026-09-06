"""
System events — the real backbone behind two dashboard pieces:
  1. The activity log feed (recent relocation acceptances + market zone shifts)
  2. The KPI strip's "Deadhead Miles Avoided" and "Revenue Protected" numbers,
     which are genuine SUMs over today's accepted relocations, not scripted.

Zone-shift events are inserted automatically by app/api/v1/manual_update.py
whenever a market's classification changes — nothing to call here for those.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.events import AcceptRelocationRequest, EventsSummary, SystemEvent

router = APIRouter(prefix="/events", tags=["events"])

INSERT_EVENT_SQL = text(
    """
    INSERT INTO system_events (event_type, message, kma_code, deadhead_miles, net_gain_usd)
    VALUES (:event_type, :message, :kma_code, :deadhead_miles, :net_gain_usd)
    RETURNING id, event_type, message, kma_code, deadhead_miles, net_gain_usd, created_at
    """
)


@router.post("/accept-relocation", response_model=SystemEvent)
async def accept_relocation(payload: AcceptRelocationRequest, db: AsyncSession = Depends(get_db)) -> SystemEvent:
    gain_text = f" · net +${payload.net_gain_usd:,.0f}" if payload.net_gain_usd else ""
    message = (
        f"{payload.truck_label} relocated to {payload.kma_name} "
        f"({payload.deadhead_miles:.0f} mi deadhead){gain_text}"
    )

    result = await db.execute(
        INSERT_EVENT_SQL,
        {
            "event_type": "relocation_accepted",
            "message": message,
            "kma_code": payload.kma_code,
            "deadhead_miles": payload.deadhead_miles,
            "net_gain_usd": payload.net_gain_usd,
        },
    )
    row = result.mappings().one()
    await db.commit()

    return SystemEvent(
        id=str(row["id"]),
        event_type=row["event_type"],
        message=row["message"],
        kma_code=row["kma_code"],
        deadhead_miles=float(row["deadhead_miles"]) if row["deadhead_miles"] is not None else None,
        net_gain_usd=float(row["net_gain_usd"]) if row["net_gain_usd"] is not None else None,
        created_at=row["created_at"],
    )


@router.get("/recent", response_model=list[SystemEvent])
async def recent_events(db: AsyncSession = Depends(get_db), limit: int = 20) -> list[SystemEvent]:
    stmt = text(
        """
        SELECT id, event_type, message, kma_code, deadhead_miles, net_gain_usd, created_at
        FROM system_events
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    result = await db.execute(stmt, {"limit": limit})
    rows = result.mappings().all()

    return [
        SystemEvent(
            id=str(row["id"]),
            event_type=row["event_type"],
            message=row["message"],
            kma_code=row["kma_code"],
            deadhead_miles=float(row["deadhead_miles"]) if row["deadhead_miles"] is not None else None,
            net_gain_usd=float(row["net_gain_usd"]) if row["net_gain_usd"] is not None else None,
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.get("/summary", response_model=EventsSummary)
async def events_summary(db: AsyncSession = Depends(get_db)) -> EventsSummary:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = text(
        """
        SELECT
            COUNT(*) AS relocations_count,
            COALESCE(SUM(deadhead_miles), 0) AS total_deadhead_miles,
            COALESCE(SUM(net_gain_usd), 0) AS total_net_gain
        FROM system_events
        WHERE event_type = 'relocation_accepted' AND created_at >= :today_start
        """
    )
    result = await db.execute(stmt, {"today_start": today_start})
    row = result.mappings().one()

    return EventsSummary(
        relocations_accepted_today=row["relocations_count"],
        deadhead_miles_avoided_today=float(row["total_deadhead_miles"]),
        revenue_protected_today=float(row["total_net_gain"]),
    )
