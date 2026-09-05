from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.enums import EquipmentType, ZoneClassification


class DeadheadAnalysisRequest(BaseModel):
    """Input for POST /api/v1/routing/analyze-deadhead"""

    destination_query: str = Field(
        ..., min_length=2, description="Delivery destination as 'City, ST' or a 5-digit ZIP, e.g. 'Atlanta, GA' or '30301'"
    )
    target_delivery_date: date = Field(..., description="Date the truck lands at the destination")
    equipment_type: EquipmentType = Field(..., description="Truck's equipment type — ratios are equipment-specific")
    radius_miles: float = Field(150.0, gt=0, le=300, description="Search radius around destination for candidate KMAs")
    current_rpm: float | None = Field(
        None, ge=0, description="RPM of the load being delivered — used to compute net arbitrage vs relocation options"
    )
    max_results: int = Field(10, ge=1, le=50)

    @field_validator("destination_query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class RelocationOption(BaseModel):
    """A single candidate KMA the truck could reposition into."""

    kma_code: str
    kma_name: str
    zip3: str
    zone_classification: ZoneClassification

    deadhead_miles: float = Field(..., description="Empty miles from destination to this KMA's centroid")
    load_to_truck_ratio: float
    avg_outbound_rpm: float | None = Field(None, description="Average $/mile for loads leaving this KMA")

    deadhead_cost_estimate_usd: float = Field(
        ..., description="Estimated fuel+time cost of the deadhead run, at a flat $0.65/mi baseline"
    )
    net_rpm_arbitrage: float | None = Field(
        None,
        description=(
            "(avg_outbound_rpm - deadhead_cost_per_mile_amortized) minus current_rpm, i.e. how much better/worse "
            "off the truck is by relocating here vs staying put. Positive = worth the deadhead."
        ),
    )
    recommended: bool = Field(..., description="True if this is a hot/balanced zone with positive net arbitrage")


class DeadheadAnalysisResponse(BaseModel):
    origin_resolved: str = Field(..., description="Geocoded label of the input destination")
    search_radius_miles: float
    target_delivery_date: date
    options: list[RelocationOption]
    best_option: RelocationOption | None = None
