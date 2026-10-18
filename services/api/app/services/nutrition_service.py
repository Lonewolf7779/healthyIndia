"""
Nutrition calculation orchestration service.
Decouples FastAPI route handlers from the pure domain calculation engine.
"""

from app.nutrition.calculator import analyze_nutrition
from app.nutrition.models import RawNutrientInput
from app.schemas.nutrition import (
    NutrientComparisonSchema,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
    NutritionFlagSchema,
)


class NutritionService:
    @staticmethod
    def analyze(request: NutritionAnalysisRequest) -> NutritionAnalysisResponse:
        domain_input = RawNutrientInput(
            serving_size=request.serving_size,
            serving_unit=request.serving_unit,
            basis=request.basis,
            food_form=request.food_form,
            energy_kcal=request.energy_kcal,
            protein_g=request.protein_g,
            carbohydrates_g=request.carbohydrates_g,
            total_sugar_g=request.total_sugar_g,
            added_sugar_g=request.added_sugar_g,
            dietary_fiber_g=request.dietary_fiber_g,
            total_fat_g=request.total_fat_g,
            saturated_fat_g=request.saturated_fat_g,
            trans_fat_g=request.trans_fat_g,
            cholesterol_mg=request.cholesterol_mg,
            sodium_mg=request.sodium_mg,
        )

        result = analyze_nutrition(domain_input)

        comparisons = [
            NutrientComparisonSchema(
                nutrient_key=c.nutrient_key,
                display_name=c.display_name,
                amount=c.amount,
                unit=c.unit,
                reference_amount=c.reference_amount,
                reference_unit=c.reference_unit,
                percentage_of_daily_value=c.percentage_of_daily_value,
                status=c.status,
                source_citation=c.source_citation,
                regulatory_status=c.regulatory_status,
            )
            for c in result.daily_value_comparisons
        ]

        flags = [
            NutritionFlagSchema(
                id=f.id,
                severity=f.severity,
                title=f.title,
                explanation=f.explanation,
                citation=f.citation,
                regulatory_status=f.regulatory_status,
                metadata=f.metadata,
            )
            for f in result.flags
        ]

        return NutritionAnalysisResponse(
            status=result.status,
            serving_size=result.serving_size,
            serving_unit=result.serving_unit,
            food_form=result.food_form,
            per_100=result.per_100,
            per_serving=result.per_serving,
            daily_value_comparisons=comparisons,
            flags=flags,
            is_complete=result.is_complete,
            missing_nutrients=result.missing_nutrients,
            disclaimer=result.disclaimer,
        )
