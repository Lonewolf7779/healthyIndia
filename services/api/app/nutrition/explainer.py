"""
Everyday Quantity Explanations for healthyIndia.

Translates scientific nutritional and additive quantities into plain-language
explanations and standardized household comparisons for Indian consumers.

Core Principles:
1. Always retain original scientific values, units, and context.
2. Mass-to-volume conversions strictly require substance-specific density.
3. Ordinary household spoons (chamach) vary (3–8 ml); standardized 5 ml metric
   spoons are always explicitly specified.
4. If a reliable conversion is unavailable, return:
   "An accurate household comparison is not available."
5. Clearly distinguish:
   - Actual quantity in product or serving
   - Recommended nutrient intake (RDA/daily reference value)
   - Acceptable daily intake (ADI) - toxicological ceiling, not a nutritional target
   - Maximum permitted concentration in food (e.g. ppm)
   - Calculated exposure estimates
6. No false reassurance: an explanation of quantity does not imply safety.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QuantityGuidanceType(StrEnum):
    ACTUAL_SERVING_QUANTITY = "actual_serving_quantity"
    RECOMMENDED_DIETARY_INTAKE = "recommended_dietary_intake"
    ACCEPTABLE_DAILY_INTAKE = "acceptable_daily_intake"
    MAXIMUM_PERMITTED_CONCENTRATION = "maximum_permitted_concentration"
    EXPOSURE_ESTIMATE = "exposure_estimate"


class EverydayExplanation(BaseModel):
    original_value: float | str
    original_unit: str
    guidance_type: QuantityGuidanceType
    plain_language_summary: str
    everyday_comparison: str
    formula: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    reference_source: str | None = None
    limitations_and_uncertainty: str
    is_conversion_available: bool = True


# Substance bulk densities (g/ml) verified from primary physical tables
SUBSTANCE_DENSITIES: dict[str, float] = {
    "granulated_sugar": 0.84,  # ~4.2 g per 5 ml level metric tsp
    "table_salt": 1.20,  # ~6.0 g per 5 ml level metric tsp
    "vegetable_oil": 0.92,  # ~4.6 g per 5 ml level metric tsp
    "water": 1.00,  # 5.0 g per 5 ml level metric tsp
    "wheat_flour": 0.57,  # ~2.85 g per 5 ml level metric tsp
    "baking_soda": 0.96,  # ~4.8 g per 5 ml level metric tsp
}

# Standardized volumetric utensils
METRIC_TEASPOON_ML = 5.0
METRIC_TABLESPOON_ML = 15.0
STANDARD_CUP_ML = 250.0

# Indian Dietary Reference Values (ICMR-NIN 2020 RDA & WHO Guidelines)
DAILY_ADDED_SUGAR_LIMIT_G = 25.0  # ICMR-NIN 2020 recommendation (<5% of 2000 kcal)
DAILY_SODIUM_LIMIT_MG = 2000.0  # ICMR-NIN 2020 & WHO upper limit (~5g salt)
DAILY_SATURATED_FAT_LIMIT_G = 22.0  # ~10% of 2000 kcal diet
REFERENCE_BODY_WEIGHT_INDIA_KG = 60.0  # Standard reference adult weight (ICMR-NIN 2020)
REFERENCE_BODY_WEIGHT_WHO_KG = 70.0  # Global adult weight (WHO)


def mass_to_metric_teaspoons(mass_g: float, substance_key: str) -> tuple[float | None, str | None]:
    """
    Converts mass in grams to standardized 5 ml metric teaspoons using substance density.
    Returns (teaspoons_count, assumption_text) or (None, None) if substance density unknown.
    """
    density = SUBSTANCE_DENSITIES.get(substance_key)
    if not density or density <= 0.0:
        return None, None

    volume_ml = mass_g / density
    teaspoons = round(volume_ml / METRIC_TEASPOON_ML, 1)
    assumption = (
        f"Based on substance bulk density of {density} g/ml for {substance_key.replace('_', ' ')} "
        f"and a standardized 5 ml metric teaspoon (~{round(density * 5.0, 1)} g per level tsp)."
    )
    return teaspoons, assumption


def generate_nutrition_quantity_explanations(
    per_serving: dict[str, float | None],
    serving_size: float,
    serving_unit: str,
) -> list[EverydayExplanation]:
    """
    Generates plain-language everyday explanations for nutritional values per serving.
    """
    explanations: list[EverydayExplanation] = []

    # 1. Serving Size explanation
    serving_text = f"{serving_size} {serving_unit}"
    if serving_unit.lower() in ("g", "gram", "grams"):
        if 25.0 <= serving_size <= 35.0:
            comparison = f"About 1 standard snack or biscuit portion ({serving_text})."
        elif 90.0 <= serving_size <= 110.0:
            comparison = f"Standard 100 g reference comparison portion ({serving_text})."
        else:
            comparison = f"A single declared packaged portion of {serving_text}."
        explanations.append(
            EverydayExplanation(
                original_value=serving_size,
                original_unit=serving_unit,
                guidance_type=QuantityGuidanceType.ACTUAL_SERVING_QUANTITY,
                plain_language_summary=f"Declared food serving size is {serving_text}.",
                everyday_comparison=comparison,
                formula=None,
                assumptions=["Declared manufacturer serving size from food package label."],
                reference_source="Package Nutrition Facts Panel",
                limitations_and_uncertainty=(
                    "Actual personal serving sizes consumed in Indian households vary by "
                    "individual."
                ),
                is_conversion_available=True,
            )
        )
    elif serving_unit.lower() in ("ml", "milliliter", "millilitres"):
        cups = round(serving_size / STANDARD_CUP_ML, 1)
        comparison = (
            f"{serving_text} is about {cups} standard measuring cup(s) (250 ml standard cup)."
        )
        explanations.append(
            EverydayExplanation(
                original_value=serving_size,
                original_unit=serving_unit,
                guidance_type=QuantityGuidanceType.ACTUAL_SERVING_QUANTITY,
                plain_language_summary=f"Declared liquid serving size is {serving_text}.",
                everyday_comparison=comparison,
                formula=f"{serving_size} ml / 250 ml = {cups} cup(s)",
                assumptions=["Standard measuring cup volume defined as 250 ml."],
                reference_source="Package Nutrition Facts Panel",
                limitations_and_uncertainty=(
                    "Household drinking glasses and cups range from 150 ml to 350 ml."
                ),
                is_conversion_available=True,
            )
        )

    # 2. Added Sugars explanation
    added_sugar = per_serving.get("added_sugar_g")
    if added_sugar is not None:
        if added_sugar > 0.0:
            tsps, assumption = mass_to_metric_teaspoons(added_sugar, "granulated_sugar")
            pct_limit = round((added_sugar / DAILY_ADDED_SUGAR_LIMIT_G) * 100.0, 1)
            explanations.append(
                EverydayExplanation(
                    original_value=added_sugar,
                    original_unit="g",
                    guidance_type=QuantityGuidanceType.RECOMMENDED_DIETARY_INTAKE,
                    plain_language_summary=(
                        f"This serving provides {added_sugar} g of added sugars, which represents "
                        f"{pct_limit}% of the recommended daily limit (25 g/day for an adult)."
                    ),
                    everyday_comparison=(
                        f"Equivalent to about {tsps} level standardized "
                        "5 ml metric teaspoons of sugar."
                    ),
                    formula=f"{added_sugar} g / 4.2 g per tsp = {tsps} standardized tsp",
                    assumptions=[
                        assumption or "Standardized metric 5 ml teaspoon.",
                        "Recommended adult added sugar upper limit: 25 g/day (ICMR-NIN 2020 RDA).",
                    ],
                    reference_source="ICMR-National Institute of Nutrition (NIN) Guidelines 2020",
                    limitations_and_uncertainty=(
                        "Indian household spoons (chamach) vary in size (3–8 ml). An everyday "
                        "comparison explains quantity scale and does not mean a portion is "
                        "healthy or harmful."
                    ),
                    is_conversion_available=True,
                )
            )
        else:
            explanations.append(
                EverydayExplanation(
                    original_value=0.0,
                    original_unit="g",
                    guidance_type=QuantityGuidanceType.ACTUAL_SERVING_QUANTITY,
                    plain_language_summary="Zero (0.0 g) added sugar declared per serving.",
                    everyday_comparison="Contains no added refined sugars per declared serving.",
                    formula=None,
                    assumptions=["Manufacturer declared nutrition label."],
                    reference_source="Package Nutrition Facts Panel",
                    limitations_and_uncertainty=(
                        "Does not account for naturally occurring intrinsic sugars."
                    ),
                    is_conversion_available=True,
                )
            )

    # 3. Sodium explanation
    sodium = per_serving.get("sodium_mg")
    if sodium is not None:
        if sodium > 0.0:
            # Table salt (NaCl) is 39.34% sodium by mass. 1g salt ~ 393.4 mg sodium.
            salt_equivalent_g = round(sodium / 393.4, 2)
            pct_limit = round((sodium / DAILY_SODIUM_LIMIT_MG) * 100.0, 1)
            salt_tsps = round((salt_equivalent_g / 6.0), 2)  # 6.0 g salt per 5 ml tsp

            if salt_tsps < 0.2:
                fraction_text = "less than 1/4"
            elif salt_tsps < 0.35:
                fraction_text = "about 1/4"
            elif salt_tsps < 0.65:
                fraction_text = "about 1/2"
            elif salt_tsps < 0.85:
                fraction_text = "about 3/4"
            else:
                fraction_text = f"about {round(salt_tsps, 1)}"

            explanations.append(
                EverydayExplanation(
                    original_value=sodium,
                    original_unit="mg",
                    guidance_type=QuantityGuidanceType.RECOMMENDED_DIETARY_INTAKE,
                    plain_language_summary=(
                        f"This serving contains {sodium} mg of sodium, which is {pct_limit}% "
                        f"of the daily recommended limit (2,000 mg sodium or ~5 g salt per day)."
                    ),
                    everyday_comparison=(
                        f"The sodium in this serving equals the sodium in approximately "
                        f"{salt_equivalent_g} g of table salt "
                        f"({fraction_text} standard metric teaspoon of salt)."
                    ),
                    formula=(
                        f"{sodium} mg sodium / 393.4 mg sodium per g NaCl = "
                        f"{salt_equivalent_g} g salt"
                    ),
                    assumptions=[
                        "Sodium chloride (table salt) is 39.34% elemental sodium by mass.",
                        "Standard 5 ml metric teaspoon of fine table salt weighs ~6.0 g.",
                        "Daily sodium upper limit: 2,000 mg/day (ICMR-NIN 2020 and WHO Guideline).",
                    ],
                    reference_source="ICMR-NIN 2020 RDA & WHO Sodium Intake Guidelines",
                    limitations_and_uncertainty=(
                        "Sodium may originate from baking soda, MSG, or food additives in "
                        "addition to table salt. Household salt shakers vary; standardized "
                        "measuring spoons are used here."
                    ),
                    is_conversion_available=True,
                )
            )

    # 4. Saturated Fat explanation
    sat_fat = per_serving.get("saturated_fat_g")
    if sat_fat is not None and sat_fat > 0.0:
        pct_limit = round((sat_fat / DAILY_SATURATED_FAT_LIMIT_G) * 100.0, 1)
        tsps, assumption = mass_to_metric_teaspoons(sat_fat, "vegetable_oil")
        explanations.append(
            EverydayExplanation(
                original_value=sat_fat,
                original_unit="g",
                guidance_type=QuantityGuidanceType.RECOMMENDED_DIETARY_INTAKE,
                plain_language_summary=(
                    f"This serving provides {sat_fat} g of saturated fat, which is {pct_limit}% "
                    f"of the daily recommended upper limit (~22 g/day for a 2,000 kcal diet)."
                ),
                everyday_comparison=(
                    f"In fat mass, this equals about {tsps} level standard metric "
                    "teaspoon(s) of fat."
                ),
                formula=f"{sat_fat} g / 4.6 g per tsp = {tsps} standardized tsp",
                assumptions=[
                    assumption or "Vegetable fat density ~0.92 g/ml.",
                    "Daily saturated fat ceiling: ~22 g/day (10% of 2,000 kcal, ICMR-NIN 2020).",
                ],
                reference_source="ICMR-NIN Dietary Guidelines 2020",
                limitations_and_uncertainty=(
                    "Saturated fat is dispersed within the food matrix rather than poured "
                    "separately. Comparison explains mass, not nutritional balance."
                ),
                is_conversion_available=True,
            )
        )

    return explanations


def explain_unconvertible_quantity(
    original_value: Any, original_unit: str, context_reason: str
) -> EverydayExplanation:
    """
    Returns explicit fallback explanation when a reliable conversion cannot be established.
    """
    return EverydayExplanation(
        original_value=original_value,
        original_unit=original_unit,
        guidance_type=QuantityGuidanceType.ACTUAL_SERVING_QUANTITY,
        plain_language_summary=f"Declared quantity: {original_value} {original_unit}.",
        everyday_comparison="An accurate household comparison is not available.",
        formula=None,
        assumptions=[],
        reference_source=None,
        limitations_and_uncertainty=(
            "Cannot establish a safe conversion without verified physical density: "
            f"{context_reason}"
        ),
        is_conversion_available=False,
    )
