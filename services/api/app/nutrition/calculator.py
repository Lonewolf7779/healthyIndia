"""
Deterministic nutrition calculation engine.

Strict Rules:
1. Pure Python mathematical calculations only.
2. Missing values are NEVER silently converted to zero or estimated.
3. Unit-aware conversions between per-serving and per-100g/ml bases.
4. Discrete units (piece/portion) without gram weights are not erroneously multiplied by 100.
5. Flags clearly distinguish binding FSSAI regulations from proposed draft guidance and RDAs.
"""

from app.nutrition.explainer import generate_nutrition_quantity_explanations
from app.nutrition.models import (
    NutrientComparison,
    NutritionAnalysisResult,
    NutritionFlag,
    RawNutrientInput,
    ServingBasis,
    ServingUnit,
)
from app.nutrition.standards import (
    DAILY_REFERENCE_VALUES,
    HFSS_THRESHOLDS,
    FlagSeverity,
    FoodForm,
    RegulatoryStatus,
)

# Mandatory nutrients required on packaged food labels by FSSAI (2020)
MANDATORY_NUTRIENT_KEYS: tuple[str, ...] = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "total_sugar_g",
    "added_sugar_g",
    "total_fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "sodium_mg",
)

ALL_NUTRIENT_KEYS: tuple[str, ...] = MANDATORY_NUTRIENT_KEYS + (
    "dietary_fiber_g",
    "cholesterol_mg",
)

NUTRIENT_TO_REFERENCE_KEY: dict[str, str] = {
    "energy_kcal": "energy",
    "protein_g": "protein",
    "carbohydrates_g": "carbohydrates",
    "added_sugar_g": "added_sugar",
    "total_fat_g": "total_fat",
    "saturated_fat_g": "saturated_fat",
    "trans_fat_g": "trans_fat",
    "sodium_mg": "sodium",
    "dietary_fiber_g": "dietary_fiber",
}

DISCLAIMER: str = (
    "healthyIndia calculations are deterministic comparisons based on published FSSAI (2020) "
    "and ICMR-NIN (2020) reference guidelines for a standard 2,000 kcal adult diet. "
    "These indicators do not diagnose medical conditions, guarantee health outcomes, or determine "
    "absolute product safety. Missing label values are never assumed to be zero."
)


def normalize_nutrients(
    input_data: RawNutrientInput,
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """
    Computes both per-100g/ml and per-serving dictionaries.
    Missing nutrients (None) are strictly preserved as None.
    If serving_unit is discrete (piece/portion), per-100 is not falsely calculated.
    """
    if input_data.serving_size <= 0:
        raise ValueError("Serving size must be greater than zero.")

    raw_dict: dict[str, float | None] = {key: getattr(input_data, key) for key in ALL_NUTRIENT_KEYS}

    for key, val in raw_dict.items():
        if val is not None and val < 0:
            raise ValueError(
                f"Nutrient '{key}' has negative value {val}, which is physically impossible."
            )

    per_100: dict[str, float | None] = {}
    per_serving: dict[str, float | None] = {}

    # Check for discrete units that cannot be converted to 100g without piece weight
    if input_data.serving_unit in (ServingUnit.PIECE, ServingUnit.PORTION):
        if input_data.basis == ServingBasis.PER_SERVING:
            for key, value in raw_dict.items():
                per_serving[key] = value
                per_100[key] = None  # Cannot scale piece to 100g without mass
            return per_100, per_serving

        # If basis is per_100g, per_serving cannot be computed without piece weight
        for key, value in raw_dict.items():
            per_100[key] = value
            per_serving[key] = None
        return per_100, per_serving

    if input_data.basis == ServingBasis.PER_SERVING:
        scale_to_100 = 100.0 / input_data.serving_size
        for key, value in raw_dict.items():
            per_serving[key] = value
            per_100[key] = round(value * scale_to_100, 2) if value is not None else None

    elif input_data.basis in (ServingBasis.PER_100G, ServingBasis.PER_100ML):
        scale_to_serving = input_data.serving_size / 100.0
        for key, value in raw_dict.items():
            per_100[key] = value
            per_serving[key] = round(value * scale_to_serving, 2) if value is not None else None

    else:
        raise ValueError(f"Unsupported serving basis: {input_data.basis}")

    return per_100, per_serving


def calculate_daily_value_comparisons(
    per_serving: dict[str, float | None],
) -> list[NutrientComparison]:
    """
    Calculates percentage of daily reference intake per serving.
    Preserves missing status when a nutrient was not provided on the label.
    """
    comparisons: list[NutrientComparison] = []

    for nutrient_key, ref_key in NUTRIENT_TO_REFERENCE_KEY.items():
        ref_standard = DAILY_REFERENCE_VALUES.get(ref_key)
        if not ref_standard:
            continue

        amount = per_serving.get(nutrient_key)
        if amount is None:
            comparisons.append(
                NutrientComparison(
                    nutrient_key=nutrient_key,
                    display_name=ref_standard.nutrient_name,
                    amount=None,
                    unit=ref_standard.unit,
                    reference_amount=ref_standard.amount,
                    reference_unit=ref_standard.unit,
                    percentage_of_daily_value=None,
                    status="not_provided",
                    source_citation=ref_standard.source,
                    regulatory_status=ref_standard.regulatory_status,
                )
            )
        else:
            percentage = round((amount / ref_standard.amount) * 100.0, 1)
            comparisons.append(
                NutrientComparison(
                    nutrient_key=nutrient_key,
                    display_name=ref_standard.nutrient_name,
                    amount=amount,
                    unit=ref_standard.unit,
                    reference_amount=ref_standard.amount,
                    reference_unit=ref_standard.unit,
                    percentage_of_daily_value=percentage,
                    status="calculated",
                    source_citation=ref_standard.source,
                    regulatory_status=ref_standard.regulatory_status,
                )
            )

    return comparisons


def evaluate_nutrition_flags(
    per_100: dict[str, float | None],
    food_form: FoodForm,
    serving_unit: ServingUnit,
    missing_mandatory: list[str],
) -> list[NutritionFlag]:
    """
    Evaluates objective, evidence-based nutrition flags against FSSAI HFSS thresholds.
    Distinguishes binding law from draft guidance. Never declares food completely safe or unsafe.
    """
    flags: list[NutritionFlag] = []
    thresholds = HFSS_THRESHOLDS[food_form]
    unit_basis = "100g" if food_form == FoodForm.SOLID else "100ml"

    # Discrete serving unit notice
    if serving_unit in (ServingUnit.PIECE, ServingUnit.PORTION):
        flags.append(
            NutritionFlag(
                id="discrete_serving_unit",
                severity=FlagSeverity.INFO,
                title="Discrete Serving Unit (No Gram Weight)",
                explanation=(
                    f"Serving size is reported in '{serving_unit.value}' without net gram weight. "
                    f"Per-100g threshold comparisons cannot be computed without physical weight."
                ),
                citation="healthyIndia Unit Normalization Rule",
                regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
            )
        )
        return flags

    # 1. Added Sugar Flag (Draft Criteria)
    added_sugar = per_100.get("added_sugar_g")
    sugar_threshold = thresholds["added_sugar_g_per_100g"]
    if added_sugar is not None and added_sugar >= sugar_threshold:
        flags.append(
            NutritionFlag(
                id="high_added_sugar",
                severity=FlagSeverity.WARNING,
                title="High in Added Sugar (Proposed Criteria)",
                explanation=(
                    f"Contains {added_sugar}g of added sugar per {unit_basis}, "
                    f"meeting or exceeding the FSSAI draft HFSS threshold of "
                    f"{sugar_threshold}g/{unit_basis}."
                ),
                citation=(
                    "FSSAI Draft Labelling Amendment Regulations "
                    "(Proposed HFSS Criteria, Non-Binding)"
                ),
                regulatory_status=RegulatoryStatus.PROPOSED_DRAFT_CRITERIA,
                metadata={"measured_per_100": added_sugar, "threshold": sugar_threshold},
            )
        )

    # 2. Saturated Fat Flag (Draft Criteria)
    sat_fat = per_100.get("saturated_fat_g")
    sat_fat_threshold = thresholds["saturated_fat_g_per_100g"]
    if sat_fat is not None and sat_fat >= sat_fat_threshold:
        flags.append(
            NutritionFlag(
                id="high_saturated_fat",
                severity=FlagSeverity.WARNING,
                title="High in Saturated Fat (Proposed Criteria)",
                explanation=(
                    f"Contains {sat_fat}g of saturated fat per {unit_basis}, meeting or exceeding "
                    f"the FSSAI draft HFSS threshold of {sat_fat_threshold}g/{unit_basis}."
                ),
                citation=(
                    "FSSAI Draft Labelling Amendment Regulations "
                    "(Proposed HFSS Criteria, Non-Binding)"
                ),
                regulatory_status=RegulatoryStatus.PROPOSED_DRAFT_CRITERIA,
                metadata={"measured_per_100": sat_fat, "threshold": sat_fat_threshold},
            )
        )

    # 3. Trans Fat Flag (Binding Legal Restriction)
    trans_fat = per_100.get("trans_fat_g")
    trans_threshold = thresholds["trans_fat_g_per_100g"]
    if trans_fat is not None and trans_fat >= trans_threshold:
        flags.append(
            NutritionFlag(
                id="elevated_trans_fat",
                severity=FlagSeverity.ALERT,
                title="Contains Significant Trans Fat (Binding Regulation)",
                explanation=(
                    f"Contains {trans_fat}g of trans fat per {unit_basis}. FSSAI legally mandates "
                    f"limiting industrial trans fats to under 2% of total fat."
                ),
                citation=(
                    "FSSAI Food Safety and Standards (Sales Restriction) "
                    "Regulations, 2021 (Binding Law)"
                ),
                regulatory_status=RegulatoryStatus.MANDATORY_REGULATION,
                metadata={"measured_per_100": trans_fat, "threshold": trans_threshold},
            )
        )

    # 4. Sodium Flag (Draft Criteria & WHO Guideline)
    sodium = per_100.get("sodium_mg")
    sodium_threshold = thresholds["sodium_mg_per_100g"]
    if sodium is not None and sodium >= sodium_threshold:
        flags.append(
            NutritionFlag(
                id="high_sodium",
                severity=FlagSeverity.WARNING,
                title="High in Sodium (Proposed Criteria)",
                explanation=(
                    f"Contains {sodium}mg of sodium per {unit_basis}, meeting or exceeding "
                    f"the FSSAI draft HFSS threshold of {sodium_threshold}mg/{unit_basis}."
                ),
                citation="FSSAI Draft Labelling Amendment Regulations & WHO Sodium Guidance",
                regulatory_status=RegulatoryStatus.PROPOSED_DRAFT_CRITERIA,
                metadata={"measured_per_100": sodium, "threshold": sodium_threshold},
            )
        )

    # 5. Incomplete Label Warning
    if missing_mandatory:
        flags.append(
            NutritionFlag(
                id="incomplete_label_data",
                severity=FlagSeverity.INFO,
                title="Incomplete Nutrition Data",
                explanation=(
                    f"The following mandatory fields were not provided on the package label: "
                    f"{', '.join(missing_mandatory)}. Missing values cannot be assumed to be zero."
                ),
                citation="healthyIndia Core Data Integrity Principle",
                regulatory_status=RegulatoryStatus.OFFICIAL_DIETARY_REFERENCE,
                metadata={"missing_fields": missing_mandatory},
            )
        )

    return flags


def analyze_nutrition(input_data: RawNutrientInput) -> NutritionAnalysisResult:
    """
    Main entry point for pure deterministic nutrition analysis.
    """
    per_100, per_serving = normalize_nutrients(input_data)

    missing_mandatory = [key for key in MANDATORY_NUTRIENT_KEYS if getattr(input_data, key) is None]
    is_complete = len(missing_mandatory) == 0
    status = "complete" if is_complete else "incomplete_data"

    daily_value_comparisons = calculate_daily_value_comparisons(per_serving)
    flags = evaluate_nutrition_flags(
        per_100,
        input_data.food_form,
        input_data.serving_unit,
        missing_mandatory,
    )
    everyday_explanations = generate_nutrition_quantity_explanations(
        per_serving=per_serving,
        serving_size=input_data.serving_size,
        serving_unit=input_data.serving_unit.value,
    )

    scaling_desc = (
        f"Scaled using deterministic factor {round(100.0 / input_data.serving_size, 4)} "
        f"based on serving size {input_data.serving_size}{input_data.serving_unit.value}."
        if input_data.serving_unit not in (ServingUnit.PIECE, ServingUnit.PORTION)
        else "Discrete piece/portion units without net gram weight cannot be scaled to 100g."
    )

    calculation_assumptions = {
        "serving_scaling_formula": scaling_desc,
        "rounding_precision": (
            "Nutrient amounts rounded to 2 decimal places; "
            "% Daily Values rounded to 1 decimal place."
        ),
        "daily_reference_source": (
            "ICMR-NIN (2020) and FSSAI (2020) daily reference values for a 2,000 kcal/day diet."
        ),
        "missing_value_policy": (
            "Missing values are strictly preserved as unprovided (None) "
            "and never silently converted to zero."
        ),
    }

    return NutritionAnalysisResult(
        status=status,
        serving_size=input_data.serving_size,
        serving_unit=input_data.serving_unit,
        food_form=input_data.food_form,
        per_100=per_100,
        per_serving=per_serving,
        daily_value_comparisons=daily_value_comparisons,
        flags=flags,
        is_complete=is_complete,
        missing_nutrients=missing_mandatory,
        disclaimer=DISCLAIMER,
        everyday_explanations=everyday_explanations,
        calculation_assumptions=calculation_assumptions,
    )
