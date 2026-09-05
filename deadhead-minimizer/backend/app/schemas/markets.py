from datetime import datetime

from pydantic import BaseModel


class MarketPoint(BaseModel):
    """One market's current snapshot, shaped for the map to consume directly."""

    kma_code: str
    kma_name: str
    zip3: str
    lat: float
    lon: float
    load_count: int
    truck_count: int
    load_to_truck_ratio: float
    avg_outbound_rpm: float | None
    zone_classification: str
    updated_at: datetime
