"""
Credible dietary reference values and thresholds based on Indian (FSSAI/ICMR-NIN)
and international (WHO) standards.

Regulatory Status Distinctions:
1. MANDATORY_REGULATION: Legally binding FSSAI regulations in force (e.g. trans fat
   sales limit < 2%, mandatory back-of-pack nutrient declarations).
2. OFFICIAL_DIETARY_REFERENCE: Authoritative daily reference values published by
   ICMR-NIN (2020) or FSSAI Schedule II for an adult reference diet (2,000 kcal).
3. PROPOSED_DRAFT_CRITERIA: Draft/proposed regulatory thresholds (e.g. FSSAI Draft HFSS
   schedules for Front-of-Pack Labelling). These provide guidance, not binding law.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class FoodForm(StrEnum):
    SOLID = "solid"  # Per 100g basis
    LIQUID = "liquid"  # Per 100ml basis


class FlagSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"


class RegulatoryStatus(StrEnum):
    MANDATORY_REGULATION = "mandatory_regulation"
    OFFICIAL_DIETARY_REFERENCE = "official_dietary_reference"
    PROPOSED_DRAFT_CRITERIA = "proposed_draft_criteria"


@dataclass(frozen=True)
class DailyReferenceValue:
    nutrient_name: str
    amount: float
    unit: str
    source: str
    description: str
    regulatory_status: RegulatoryStatus = RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE


# ICMR-NIN / FSSAI Daily Reference Values for a standard 2000 kcal adult diet
DAILY_REFERENCE_VALUES: Final[dict[str, DailyReferenceValue]] = {
    "energy": DailyReferenceValue(
        nutrient_name="Energy",
        amount=2000.0,
        unit="kcal",
        source="ICMR-NIN (2020) Reference Adult Diet",
        description="Standard daily energy reference intake for adult assessment.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "protein": DailyReferenceValue(
        nutrient_name="Protein",
        amount=54.0,
        unit="g",
        source="ICMR-NIN (2020) RDA for Adult",
        description="Recommended daily protein allowance.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "carbohydrates": DailyReferenceValue(
        nutrient_name="Carbohydrates",
        amount=250.0,
        unit="g",
        source="ICMR-NIN (2020) Energy Intake Basis (50-60% energy)",
        description="Daily reference carbohydrate intake.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "added_sugar": DailyReferenceValue(
        nutrient_name="Added Sugar",
        amount=50.0,
        unit="g",
        source="FSSAI / WHO Guideline (Max 10% of total daily energy)",
        description="Recommended maximum daily intake threshold for added sugars (~10 tsp).",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "total_fat": DailyReferenceValue(
        nutrient_name="Total Fat",
        amount=67.0,
        unit="g",
        source="ICMR-NIN (2020) / FSSAI (Max 30% of energy)",
        description="Recommended maximum daily intake for total dietary fat.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "saturated_fat": DailyReferenceValue(
        nutrient_name="Saturated Fat",
        amount=20.0,
        unit="g",
        source="FSSAI / WHO Guideline (Max 10% of total daily energy)",
        description="Recommended upper limit for saturated fat to reduce cardiovascular risk.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "trans_fat": DailyReferenceValue(
        nutrient_name="Trans Fat",
        amount=2.2,
        unit="g",
        source="FSSAI Sales Restriction Regulations (2021) / WHO (<1% energy, <2% of total fat)",
        description="Strict regulatory upper limit for industrial trans fats.",
        regulatory_status=RegulatoryStatus.MANDATORY_REGULATION,
    ),
    "sodium": DailyReferenceValue(
        nutrient_name="Sodium",
        amount=2000.0,
        unit="mg",
        source="WHO Guideline (2012) / FSSAI (Equivalent to 5g table salt per day)",
        description="Recommended maximum daily intake of sodium for adults.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
    "dietary_fiber": DailyReferenceValue(
        nutrient_name="Dietary Fiber",
        amount=30.0,
        unit="g",
        source="ICMR-NIN (2020) Daily Requirement",
        description="Recommended adequate daily intake of dietary fiber.",
        regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
    ),
}


# FSSAI HFSS (High in Fat, Sugar, Salt) per-100g / per-100ml Draft Guidance Thresholds
# NOTE: These are PROPOSED draft criteria for consumer transparency, NOT gazetted binding mandates.
HFSS_THRESHOLDS: Final[dict[FoodForm, dict[str, float]]] = {
    FoodForm.SOLID: {
        "added_sugar_g_per_100g": 10.0,  # > 10g added sugar per 100g
        "saturated_fat_g_per_100g": 4.0,  # > 4g saturated fat per 100g
        "trans_fat_g_per_100g": 0.2,  # > 0.2g trans fat per 100g
        "sodium_mg_per_100g": 600.0,  # > 600mg sodium per 100g
    },
    FoodForm.LIQUID: {
        "added_sugar_g_per_100g": 5.0,  # > 5g added sugar per 100ml
        "saturated_fat_g_per_100g": 2.0,  # > 2g saturated fat per 100ml
        "trans_fat_g_per_100g": 0.1,  # > 0.1g trans fat per 100ml
        "sodium_mg_per_100g": 300.0,  # > 300mg sodium per 100ml
    },
}
