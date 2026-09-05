from pydantic import BaseModel, Field

from app.models.enums import EquipmentType, ZoneClassification


class LoopPlanRequest(BaseModel):
    """Input for POST /api/v1/routing/plan-loop"""

    origin_query: str = Field(..., min_length=2, description="Starting point as 'City, ST' or ZIP")
    equipment_type: EquipmentType
    num_legs: int = Field(3, ge=2, le=5, description="Number of loaded legs in the loop, e.g. 3 for a weekly triangle")
    min_leg_miles: float = Field(150.0, gt=0, description="Minimum distance for a leg to count as a real haul, not noise")
    max_leg_miles: float = Field(800.0, gt=0, description="Maximum distance per leg — keeps legs realistic for weekly loops")

    def model_post_init(self, __context) -> None:
        if self.min_leg_miles >= self.max_leg_miles:
            raise ValueError("min_leg_miles must be less than max_leg_miles")


class LoopLeg(BaseModel):
    leg_number: int
    from_kma_code: str
    from_kma_name: str
    to_kma_code: str
    to_kma_name: str
    distance_miles: float
    rpm_usd: float
    estimated_revenue_usd: float
    to_zone_classification: ZoneClassification


class LoopPlanResponse(BaseModel):
    origin_resolved: str
    equipment_type: EquipmentType
    legs: list[LoopLeg]
    total_miles: float
    total_estimated_revenue_usd: float
    blended_rpm_usd: float
    closes_near_origin: bool = Field(
        ..., description="True if the final leg lands within max_leg_miles of the starting point"
    )
