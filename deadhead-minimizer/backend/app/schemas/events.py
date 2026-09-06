from datetime import datetime

from pydantic import BaseModel


class AcceptRelocationRequest(BaseModel):
    """Logged when a dispatcher acts on a relocation recommendation."""

    truck_label: str  # free text, e.g. "Truck #482" — no real truck records tracked yet
    kma_code: str
    kma_name: str
    deadhead_miles: float
    net_gain_usd: float | None = None


class SystemEvent(BaseModel):
    id: str
    event_type: str
    message: str
    kma_code: str | None
    deadhead_miles: float | None
    net_gain_usd: float | None
    created_at: datetime


class EventsSummary(BaseModel):
    """Today's rollup — powers the KPI strip."""

    relocations_accepted_today: int
    deadhead_miles_avoided_today: float
    revenue_protected_today: float
