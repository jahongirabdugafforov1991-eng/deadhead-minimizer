from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.loop import LoopPlanRequest, LoopPlanResponse
from app.schemas.routing import DeadheadAnalysisRequest, DeadheadAnalysisResponse
from app.services.deadhead_service import GeocodingError, find_relocation_options, geocode_destination
from app.services.loop_builder_service import LoopPlanningError, build_triangulation_loop

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post("/analyze-deadhead", response_model=DeadheadAnalysisResponse)
async def analyze_deadhead(
    payload: DeadheadAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> DeadheadAnalysisResponse:
    """
    Given a truck's delivery destination and equipment type, return ranked
    relocation options into nearby Key Market Areas, scored by net RPM
    arbitrage (expected earning power at the new zone minus the cost of the
    deadhead run to get there).
    """
    try:
        origin = await geocode_destination(db, payload.destination_query)
    except GeocodingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    options = await find_relocation_options(
        db=db,
        origin=origin,
        equipment_type=payload.equipment_type,
        radius_miles=payload.radius_miles,
        current_rpm=payload.current_rpm,
        max_results=payload.max_results,
    )

    if not options:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No KMAs found within {payload.radius_miles} miles of "
                f"'{payload.destination_query}' for equipment type '{payload.equipment_type.value}'. "
                "Try increasing radius_miles."
            ),
        )

    return DeadheadAnalysisResponse(
        origin_resolved=origin.label,
        search_radius_miles=payload.radius_miles,
        target_delivery_date=payload.target_delivery_date,
        options=options,
        best_option=options[0],
    )


@router.post("/plan-loop", response_model=LoopPlanResponse)
async def plan_loop(
    payload: LoopPlanRequest,
    db: AsyncSession = Depends(get_db),
) -> LoopPlanResponse:
    """
    Build a deterministic multi-leg triangulation loop (e.g. a 3-leg weekly
    circuit) starting from the truck's current position, greedily chaining
    high-value KMAs and biasing the final leg to close back near the origin.
    """
    try:
        return await build_triangulation_loop(
            db=db,
            origin_query=payload.origin_query,
            equipment_type=payload.equipment_type,
            num_legs=payload.num_legs,
            min_leg_miles=payload.min_leg_miles,
            max_leg_miles=payload.max_leg_miles,
        )
    except GeocodingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LoopPlanningError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
