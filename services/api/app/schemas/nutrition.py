"""
Pydantic schemas for nutrition analysis requests and responses.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.nutrition.models import ServingBasis, ServingUnit
from app.nutrition.standards import FlagSeverity, FoodForm, RegulatoryStatus


class NutritionAnalysisRequest(BaseModel):
    """
    Input schema representing nutritional panel information.
    All nutrient values are optional to preserve the distinction
    between an unlisted nutrient (None) and zero (0.0).
    """

    serving_size: float = Field(
        ...,
        gt=0.0,
        le=5000.0,
        description="Declared serving size (must be strictly positive).",
        examples=[30.0],
    )
    serving_unit: ServingUnit = Field(
        default=ServingUnit.G,
        description="Unit of serving size.",
        examples=[ServingUnit.G],
    )
    basis: ServingBasis = Field(
        default=ServingBasis.PER_SERVING,
        description="Basis on which the package values are reported.",
        examples=[ServingBasis.PER_SERVING],
    )
    food_form: FoodForm = Field(
        default=FoodForm.SOLID,
        description="Physical state of the food (solid food or liquid beverage).",
        examples=[FoodForm.SOLID],
    )

    # Optional nutrient values (None indicates omitted or unread)
    energy_kcal: float | None = Field(
        default=None,
        ge=0.0,
        le=5000.0,
        description="Energy in kilocalories (kcal).",
        examples=[140.0],
    )
    protein_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Protein content in grams (g).",
        examples=[3.0],
    )
    carbohydrates_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Total carbohydrates in grams (g).",
        examples=[20.0],
    )
    total_sugar_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Total sugars in grams (g).",
        examples=[12.0],
    )
    added_sugar_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Added sugars in grams (g).",
        examples=[10.0],
    )
    dietary_fiber_g: float | None = Field(
        default=None,
        ge=0.0,
        le=200.0,
        description="Dietary fiber in grams (g).",
        examples=[1.5],
    )
    total_fat_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Total fat in grams (g).",
        examples=[6.0],
    )
    saturated_fat_g: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
        description="Saturated fat in grams (g).",
        examples=[2.5],
    )
    trans_fat_g: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Trans fat in grams (g).",
        examples=[0.0],
    )
    cholesterol_mg: float | None = Field(
        default=None,
        ge=0.0,
        le=5000.0,
        description="Cholesterol in milligrams (mg).",
        examples=[0.0],
    )
    sodium_mg: float | None = Field(
        default=None,
        ge=0.0,
        le=50000.0,
        description="Sodium in milligrams (mg).",
        examples=[180.0],
    )

    @model_validator(mode="after")
    def validate_biological_plausibility(self) -> "NutritionAnalysisRequest":
        # Check added sugar vs total sugar
        if (
            self.added_sugar_g is not None
            and self.total_sugar_g is not None
            and self.added_sugar_g > (self.total_sugar_g + 0.05)
        ):
            msg = (
                f"Added sugar ({self.added_sugar_g}g) cannot exceed "
                f"total sugar ({self.total_sugar_g}g)."
            )
            raise ValueError(msg)

        # Check total sugar vs carbohydrates
        if (
            self.total_sugar_g is not None
            and self.carbohydrates_g is not None
            and self.total_sugar_g > (self.carbohydrates_g + 0.05)
        ):
            msg = (
                f"Total sugar ({self.total_sugar_g}g) cannot exceed "
                f"total carbohydrates ({self.carbohydrates_g}g)."
            )
            raise ValueError(msg)

        # Check sub-fats vs total fat plausibility
        sub_fats = (self.saturated_fat_g or 0.0) + (self.trans_fat_g or 0.0)
        if self.total_fat_g is not None and sub_fats > (self.total_fat_g + 0.05):
            raise ValueError(
                f"Sum of saturated fat and trans fat ({round(sub_fats, 2)}g) "
                f"cannot exceed total fat ({self.total_fat_g}g)."
            )

        # Check energy plausibility against minimum fat calories (9 kcal/g)
        if (
            self.energy_kcal is not None
            and self.total_fat_g is not None
            and self.total_fat_g > 1.0
            and self.energy_kcal < (self.total_fat_g * 8.0)
        ):
            msg = (
                f"Declared energy ({self.energy_kcal} kcal) is biologically implausible "
                f"for declared total fat ({self.total_fat_g}g, yielding min ~"
                f"{round(self.total_fat_g * 9.0, 1)} kcal)."
            )
            raise ValueError(msg)

        return self


class NutrientComparisonSchema(BaseModel):
    nutrient_key: str
    display_name: str
    amount: float | None
    unit: str
    reference_amount: float | None
    reference_unit: str | None
    percentage_of_daily_value: float | None
    status: str
    source_citation: str | None
    regulatory_status: RegulatoryStatus = RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE


class NutritionFlagSchema(BaseModel):
    id: str
    severity: FlagSeverity
    title: str
    explanation: str
    citation: str
    regulatory_status: RegulatoryStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class NutritionAnalysisResponse(BaseModel):
    status: str = Field(
        ...,
        description="'complete' if all core nutrients were provided, otherwise 'incomplete_data'.",
    )
    serving_size: float
    serving_unit: ServingUnit
    food_form: FoodForm

    per_100: dict[str, float | None] = Field(
        ..., description="Nutrient amounts normalized to 100g (solid) or 100ml (liquid)."
    )
    per_serving: dict[str, float | None] = Field(
        ..., description="Nutrient amounts for the declared serving size."
    )
    daily_value_comparisons: list[NutrientComparisonSchema] = Field(
        ..., description="Comparison against ICMR-NIN/FSSAI daily reference values per serving."
    )
    flags: list[NutritionFlagSchema] = Field(
        ...,
        description=(
            "Transparent threshold flags (distinguishing binding laws from draft guidance)."
        ),
    )
    is_complete: bool = Field(
        ..., description="False if any mandatory nutrient was missing from input."
    )
    missing_nutrients: list[str] = Field(
        ..., description="List of nutrient fields not reported on the package label."
    )
    disclaimer: str = Field(
        ..., description="Scientific limitations and legal transparency statement."
    )
