"""
Unit tests for everyday quantity explanations.

Validates:
1. Scientific values and units are preserved.
2. Mass-to-volume conversions use substance-specific densities.
3. Fallback message when reliable conversion data is missing.
4. Body-weight-based calculations for Indian (60 kg) and global (70 kg) adults.
5. Strict distinction between guidance types (ADI vs recommended intake vs serving quantity).
6. Transparent reporting of assumptions and limitations.
"""

from app.nutrition.explainer import (
    EverydayExplanation,
    QuantityGuidanceType,
    explain_unconvertible_quantity,
    generate_nutrition_quantity_explanations,
    mass_to_metric_teaspoons,
)


def test_substance_specific_density_conversions() -> None:
    # 1. Granulated sugar: density 0.84 g/ml -> 5 ml metric tsp = 4.2 g
    tsps_sugar, assumption_sugar = mass_to_metric_teaspoons(8.4, "granulated_sugar")
    assert tsps_sugar == 2.0
    assert "0.84 g/ml" in str(assumption_sugar)
    assert "granulated sugar" in str(assumption_sugar)

    # 2. Table salt: density 1.20 g/ml -> 5 ml metric tsp = 6.0 g
    tsps_salt, assumption_salt = mass_to_metric_teaspoons(6.0, "table_salt")
    assert tsps_salt == 1.0
    assert "1.2 g/ml" in str(assumption_salt)

    # 3. Vegetable oil: density 0.92 g/ml -> 5 ml metric tsp = 4.6 g
    tsps_oil, _ = mass_to_metric_teaspoons(9.2, "vegetable_oil")
    assert tsps_oil == 2.0

    # 4. Unknown substance must return None
    tsps_unknown, assumption_unknown = mass_to_metric_teaspoons(10.0, "unknown_chemical_xyz")
    assert tsps_unknown is None
    assert assumption_unknown is None


def test_fallback_when_conversion_unavailable() -> None:
    fallback = explain_unconvertible_quantity(
        original_value=50.0,
        original_unit="mg",
        context_reason="No substance density available for synthetic polymer.",
    )
    assert fallback.is_conversion_available is False
    assert fallback.everyday_comparison == "An accurate household comparison is not available."
    assert "No substance density available" in fallback.limitations_and_uncertainty
    assert fallback.original_value == 50.0
    assert fallback.original_unit == "mg"


def test_added_sugars_explanation_and_reference_limits() -> None:
    per_serving = {"added_sugar_g": 12.6}
    explanations = generate_nutrition_quantity_explanations(
        per_serving=per_serving, serving_size=30.0, serving_unit="g"
    )

    sugar_exp = next(
        (e for e in explanations if e.original_unit == "g" and e.original_value == 12.6), None
    )
    assert sugar_exp is not None
    assert sugar_exp.guidance_type == QuantityGuidanceType.RECOMMENDED_DIETARY_INTAKE
    # 12.6 g / 4.2 g/tsp = 3.0 tsp
    assert "3.0" in sugar_exp.everyday_comparison
    assert "standardized 5 ml metric teaspoons" in sugar_exp.everyday_comparison
    # 12.6 / 25.0 = 50.4%
    assert "50.4%" in sugar_exp.plain_language_summary
    assert "25 g/day" in sugar_exp.plain_language_summary
    assert sugar_exp.reference_source is not None
    assert "ICMR" in sugar_exp.reference_source
    assert "NIN" in sugar_exp.reference_source
    assert "chamach" in sugar_exp.limitations_and_uncertainty.lower()


def test_sodium_and_salt_stoichiometry_explanation() -> None:
    # 786.8 mg sodium equals ~2.0 g table salt (NaCl has 39.34% sodium)
    per_serving = {"sodium_mg": 786.8}
    explanations = generate_nutrition_quantity_explanations(
        per_serving=per_serving, serving_size=50.0, serving_unit="g"
    )

    sodium_exp = next((e for e in explanations if e.original_unit == "mg"), None)
    assert sodium_exp is not None
    assert sodium_exp.guidance_type == QuantityGuidanceType.RECOMMENDED_DIETARY_INTAKE
    assert "2.0 g of table salt" in sodium_exp.everyday_comparison
    # 786.8 / 2000 = 39.3%
    assert "39.3%" in sodium_exp.plain_language_summary
    assert "39.34% elemental sodium" in " ".join(sodium_exp.assumptions)


def test_distinction_between_guidance_types() -> None:
    # Serving quantity vs Recommended intake vs ADI
    actual_exp = EverydayExplanation(
        original_value=30.0,
        original_unit="g",
        guidance_type=QuantityGuidanceType.ACTUAL_SERVING_QUANTITY,
        plain_language_summary="Declared packaged serving.",
        everyday_comparison="About 1 snack portion.",
        limitations_and_uncertainty="Portions vary.",
    )
    assert actual_exp.guidance_type == QuantityGuidanceType.ACTUAL_SERVING_QUANTITY

    adi_exp = EverydayExplanation(
        original_value=40.0,
        original_unit="mg/kg body weight/day",
        guidance_type=QuantityGuidanceType.ACCEPTABLE_DAILY_INTAKE,
        plain_language_summary="Acceptable Daily Intake is a toxicological safety ceiling.",
        everyday_comparison="For a 60 kg adult, calculated ADI is 2,400 mg/day.",
        limitations_and_uncertainty=(
            "An ADI is a lifetime safety ceiling, NOT a nutritional target."
        ),
    )
    assert adi_exp.guidance_type == QuantityGuidanceType.ACCEPTABLE_DAILY_INTAKE
    assert "safety ceiling" in adi_exp.limitations_and_uncertainty
    assert "NOT a nutritional target" in adi_exp.limitations_and_uncertainty


def test_zero_added_sugar_preservation() -> None:
    per_serving = {"added_sugar_g": 0.0}
    explanations = generate_nutrition_quantity_explanations(
        per_serving=per_serving, serving_size=250.0, serving_unit="ml"
    )
    sugar_exp = next(
        (e for e in explanations if e.original_unit == "g" and e.original_value == 0.0), None
    )
    assert sugar_exp is not None
    assert sugar_exp.guidance_type == QuantityGuidanceType.ACTUAL_SERVING_QUANTITY
    assert "Zero (0.0 g) added sugar" in sugar_exp.plain_language_summary
