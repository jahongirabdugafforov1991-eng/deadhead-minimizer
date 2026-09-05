from pydantic import BaseModel, Field

from app.models.enums import EquipmentType


class ManualKmaUpdate(BaseModel):
    """
    One market's current snapshot, entered by hand.
    This is intentionally the same shape the DAT ingestion pipeline will
    eventually populate automatically — so nothing downstream (map, deadhead
    endpoint, loop builder) needs to change when real ingestion replaces this.
    """

    kma_code: str = Field(..., description="Short code for the market, e.g. 'ATL'. Must already exist in kma_heatmaps.")
    equipment_type: EquipmentType
    load_count: int = Field(..., ge=0, description="Loads currently posted in this market")
    truck_count: int = Field(..., ge=0, description="Trucks currently available in this market")
    avg_outbound_rpm: float | None = Field(None, ge=0, description="Typical $/mile for loads leaving this market right now")


class ManualKmaUpdateBatch(BaseModel):
    """A dispatcher's full update — usually all of a company's tracked markets at once."""

    updates: list[ManualKmaUpdate] = Field(..., min_length=1)


class ManualKmaUpdateResult(BaseModel):
    kma_code: str
    equipment_type: EquipmentType
    load_to_truck_ratio: float
    zone_classification: str
    updated: bool
