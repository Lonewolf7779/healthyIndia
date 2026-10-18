"""
Pure domain models for nutrition calculation.
Independent of FastAPI and database engines.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.nutrition.standards import FlagSeverity, FoodForm, RegulatoryStatus


class ServingBasis(StrEnum):
    PER_SERVING = "per_serving"
    PER_100G = "per_100g"
    PER_100ML = "per_100ml"


class ServingUnit(StrEnum):
    G = "g"
    ML = "ml"
    PIECE = "piece"
    PORTION = "portion"


@dataclass(frozen=True)
class RawNutrientInput:
    """
    Nutritional values parsed from a package label or user entry.
    All nutrient fields are optional (None) to ensure missing values
    are explicitly recognized and never silently defaulted to zero.
    """

    serving_size: float
    serving_unit: ServingUnit
    basis: ServingBasis
    food_form: FoodForm = FoodForm.SOLID

    # Core macronutrients and indicators
    energy_kcal: float | None = None
    protein_g: float | None = None
    carbohydrates_g: float | None = None
    total_sugar_g: float | None = None
    added_sugar_g: float | None = None
    dietary_fiber_g: float | None = None
    total_fat_g: float | None = None
    saturated_fat_g: float | None = None
    trans_fat_g: float | None = None
    cholesterol_mg: float | None = None
    sodium_mg: float | None = None


@dataclass(frozen=True)
class NutrientComparison:
    nutrient_key: str
    display_name: str
    amount: float | None
    unit: str
    reference_amount: float | None
    reference_unit: str | None
    percentage_of_daily_value: float | None
    status: str  # "calculated", "not_provided", "no_reference_standard"
    source_citation: str | None
    regulatory_status: RegulatoryStatus = RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE


@dataclass(frozen=True)
class NutritionFlag:
    id: str
    severity: FlagSeverity
    title: str
    explanation: str
    citation: str
    regulatory_status: RegulatoryStatus
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NutritionAnalysisResult:
    """
    Complete deterministic analysis outcome.
    """

    status: str  # "complete" | "incomplete_data"
    serving_size: float
    serving_unit: ServingUnit
    food_form: FoodForm

    # Normalized values (per 100g or per 100ml)
    # Values remain None if not provided on the label or if discrete units lack net weight
    per_100: dict[str, float | None]

    # Original per-serving values (calculated or reported)
    per_serving: dict[str, float | None]

    # Comparisons against credible daily reference values
    daily_value_comparisons: list[NutrientComparison]

    # Threshold flags (e.g., HFSS)
    flags: list[NutritionFlag]

    # Data completeness tracking
    is_complete: bool
    missing_nutrients: list[str]

    # Scientific and legal limitations
    disclaimer: str
