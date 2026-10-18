"""
Pydantic schemas for nutrition analysis requests and responses.
"""

import hashlib
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.security import verify_extraction_token
from app.nutrition.models import ServingBasis, ServingUnit
from app.nutrition.standards import FlagSeverity, FoodForm, RegulatoryStatus


def compute_nutrition_values_hash(
    serving_size: float,
    serving_unit: str,
    basis: str,
    food_form: str,
    nutrients: dict[str, float | None],
) -> str:
    """
    Computes a deterministic SHA-256 hash across all input parameters to guarantee that
    confirmation cannot be reused if any value or structural parameter is altered.
    """
    items = [
        f"serving_size:{serving_size:.4f}",
        f"serving_unit:{serving_unit}",
        f"basis:{basis}",
        f"food_form:{food_form}",
    ]
    for k in sorted(nutrients.keys()):
        v = nutrients[k]
        val_str = f"{float(v):.4f}" if v is not None else "null"
        items.append(f"{k}:{val_str}")
    canonical_repr = "|".join(items)
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


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

    data_source: str = Field(
        default="manual",
        description="Source of data: 'manual' or 'ocr'.",
        examples=["manual"],
    )
    is_confirmed: bool = Field(
        default=True,
        description="Explicit user confirmation that input values have been reviewed.",
        examples=[True],
    )
    extraction_id: str | None = Field(
        default=None,
        description="Extraction session ID corresponding to the issued extraction_token.",
    )
    extraction_token: str | None = Field(
        default=None,
        description=(
            "Cryptographically signed verification token issued by "
            "/api/v1/extraction/ocr for OCR-derived payloads."
        ),
    )
    confirmed_values_hash: str | None = Field(
        default=None,
        description="Cryptographic SHA-256 digest of confirmed nutrient values and dimensions.",
    )

    @model_validator(mode="after")
    def validate_biological_plausibility(self) -> "NutritionAnalysisRequest":
        # 1. Enforce confirmation: unconfirmed requests are rejected fail-closed
        if not self.is_confirmed:
            raise ValueError(
                "Final nutrition calculation requires explicit confirmation of input values."
            )

        if self.data_source not in ("manual", "ocr"):
            raise ValueError("data_source must be either 'manual' or 'ocr'.")

        nutrient_vals = {
            "added_sugar_g": self.added_sugar_g,
            "carbohydrates_g": self.carbohydrates_g,
            "cholesterol_mg": self.cholesterol_mg,
            "dietary_fiber_g": self.dietary_fiber_g,
            "energy_kcal": self.energy_kcal,
            "protein_g": self.protein_g,
            "saturated_fat_g": self.saturated_fat_g,
            "sodium_mg": self.sodium_mg,
            "total_fat_g": self.total_fat_g,
            "total_sugar_g": self.total_sugar_g,
            "trans_fat_g": self.trans_fat_g,
        }

        if self.data_source == "ocr":
            if not self.extraction_token:
                raise ValueError(
                    "OCR-derived data requires a valid extraction_token issued by the scanner."
                )
            if not self.confirmed_values_hash:
                raise ValueError("OCR-derived data requires an explicit confirmed_values_hash.")

            # Cryptographically authenticate the extraction token against server secret
            is_valid, err_msg = verify_extraction_token(
                token=self.extraction_token,
                extraction_id=self.extraction_id,
            )
            if not is_valid:
                raise ValueError(f"Extraction token authentication failed: {err_msg}")

            expected_hash = compute_nutrition_values_hash(
                serving_size=self.serving_size,
                serving_unit=self.serving_unit.value,
                basis=self.basis.value,
                food_form=self.food_form.value,
                nutrients=nutrient_vals,
            )
            if self.confirmed_values_hash != expected_hash:
                raise ValueError(
                    "Confirmed values hash does not match submitted values; "
                    "values were modified after confirmation without re-verifying."
                )
        elif self.data_source == "manual":
            if self.extraction_token is not None or self.extraction_id is not None:
                raise ValueError(
                    "Manual data source cannot carry an extraction_token or extraction_id; "
                    "use data_source='ocr'."
                )

        # 2. Incompatible unit checks: mass vs volume without density
        if self.food_form == FoodForm.SOLID:
            if self.serving_unit in (ServingUnit.ML, ServingUnit.L):
                raise ValueError(
                    "Solid food cannot declare volume serving unit (ml/l) "
                    "without explicit substance density."
                )
            if self.basis == ServingBasis.PER_100ML:
                raise ValueError(
                    "Solid food cannot be analyzed on a per-100ml basis "
                    "without explicit substance density."
                )
        elif self.food_form == FoodForm.LIQUID:
            if self.serving_unit in (ServingUnit.G, ServingUnit.KG):
                raise ValueError(
                    "Liquid food cannot declare mass serving unit (g/kg) "
                    "without explicit substance density."
                )
            if self.basis == ServingBasis.PER_100G:
                raise ValueError(
                    "Liquid food cannot be analyzed on a per-100g basis "
                    "without explicit substance density."
                )

        # 3. Non-negative nutrient checks
        for k, v in nutrient_vals.items():
            if v is not None and v < 0:
                raise ValueError(f"Nutrient '{k}' cannot be negative ({v}).")

        # 4. Check added sugar vs total sugar
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

        # 5. Check total sugar vs carbohydrates
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

        # 6. Check sub-fats vs total fat plausibility
        sub_fats = (self.saturated_fat_g or 0.0) + (self.trans_fat_g or 0.0)
        if self.total_fat_g is not None and sub_fats > (self.total_fat_g + 0.05):
            raise ValueError(
                f"Sum of saturated fat and trans fat ({round(sub_fats, 2)}g) "
                f"cannot exceed total fat ({self.total_fat_g}g)."
            )

        # 7. Check solid food macronutrient sum limit on per-100g basis
        if self.basis == ServingBasis.PER_100G:
            macro_sum = (
                (self.protein_g or 0.0) + (self.carbohydrates_g or 0.0) + (self.total_fat_g or 0.0)
            )
            if macro_sum > 105.0:
                raise ValueError(
                    f"Sum of macronutrients ({macro_sum:.1f}g) exceeds 100g serving basis "
                    "(105g maximum with analytical tolerance)."
                )

        # 8. Check energy plausibility against minimum fat calories (9 kcal/g)
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


class EverydayExplanationSchema(BaseModel):
    original_value: float | str
    original_unit: str
    guidance_type: str
    plain_language_summary: str
    everyday_comparison: str
    formula: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    reference_source: str | None = None
    limitations_and_uncertainty: str
    is_conversion_available: bool = True


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
    everyday_explanations: list[EverydayExplanationSchema] = Field(
        default_factory=list,
        description="Plain-language quantity explanations and everyday comparisons.",
    )
    calculation_assumptions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Transparent record of scaling formulas, rounding rules, and reference diet standards."
        ),
    )
