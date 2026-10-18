from fastapi import APIRouter, status

from app.schemas.nutrition import NutritionAnalysisRequest, NutritionAnalysisResponse
from app.services.nutrition_service import NutritionService

router = APIRouter()


@router.post(
    "/analyze",
    response_model=NutritionAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Deterministic Nutrition Label Analysis",
    description=(
        "Analyzes raw nutritional panel data deterministically against FSSAI and "
        "ICMR-NIN reference guidelines. Missing fields are never treated as zero."
    ),
)
async def analyze_nutrition_label(
    request: NutritionAnalysisRequest,
) -> NutritionAnalysisResponse:
    """
    Analyzes submitted nutritional values and returns:
    - Normalization to per-100g or per-100ml
    - Daily value percentage comparisons
    - FSSAI HFSS threshold flags
    - Explicit tracking of missing values
    """
    return NutritionService.analyze(request)
