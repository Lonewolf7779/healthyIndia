from fastapi import APIRouter, status

from app.schemas.ingredients import IngredientAnalysisRequest, IngredientAnalysisResponse
from app.services.ingredient_service import IngredientService

router = APIRouter()


@router.post(
    "/analyze",
    response_model=IngredientAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Deterministic Food Additive & Ingredient Analysis",
    description=(
        "Parses food ingredient declarations deterministically against curated FSSAI/Codex "
        "additive reference data. Preserves unmatched text as unknown."
    ),
)
async def analyze_ingredients_endpoint(
    request: IngredientAnalysisRequest,
) -> IngredientAnalysisResponse:
    """
    Analyzes submitted ingredient strings:
    - Extracts INS / E numbers and verified exact aliases
    - Identifies functional classes (preservative, colour, emulsifier, etc.)
    - Returns jurisdiction, regulatory limitations, and citations
    - Strictly preserves unmatched text as unknown without probabilistic guessing
    """
    return IngredientService.analyze(request)
