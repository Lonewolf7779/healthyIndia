"""
Category C: Comprehensive Nutrition Calculation and Biological Plausibility Suite.

Validates deterministic normalization, daily value comparisons, boundary thresholds,
missing value preservation, precision, and physical/biological plausibility rules.
"""

import pytest
from pydantic import ValidationError

from app.nutrition.calculator import (
    ALL_NUTRIENT_KEYS,
    analyze_nutrition,
    normalize_nutrients,
)
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FlagSeverity, FoodForm, RegulatoryStatus
from app.schemas.nutrition import NutritionAnalysisRequest


def test_bidirectional_scaling_and_precision() -> None:
    """
    Validates accurate scaling between per-serving and per-100g/ml bases.
    Tests precision rounding (2 decimal places) and avoids scaling drift.
    """
    # 35g serving, per-serving basis
    inp_serving = RawNutrientInput(
        serving_size=35.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=140.0,
        protein_g=2.5,
        carbohydrates_g=21.0,
        total_sugar_g=7.0,
        added_sugar_g=5.0,
        total_fat_g=5.0,
        saturated_fat_g=2.2,
        trans_fat_g=0.0,
        sodium_mg=175.0,
    )
    res_serving = analyze_nutrition(inp_serving)

    # 100 / 35 = 2.85714...
    # 140 * (100 / 35) = 400.0
    assert res_serving.per_100["energy_kcal"] == 400.0
    # 2.5 * (100 / 35) = 7.1428... -> 7.14
    assert res_serving.per_100["protein_g"] == 7.14
    # 21.0 * (100 / 35) = 60.0
    assert res_serving.per_100["carbohydrates_g"] == 60.0
    # 175.0 * (100 / 35) = 500.0
    assert res_serving.per_100["sodium_mg"] == 500.0

    # Opposite direction: 100g basis scaled down to 35g serving
    inp_100 = RawNutrientInput(
        serving_size=35.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        energy_kcal=400.0,
        protein_g=7.14,
        carbohydrates_g=60.0,
        total_sugar_g=20.0,
        added_sugar_g=14.29,
        total_fat_g=14.29,
        saturated_fat_g=6.29,
        trans_fat_g=0.0,
        sodium_mg=500.0,
    )
    res_100 = analyze_nutrition(inp_100)
    assert res_100.per_serving["energy_kcal"] == 140.0
    assert res_100.per_serving["carbohydrates_g"] == 21.0
    assert res_100.per_serving["sodium_mg"] == 175.0


def test_liquid_beverage_scaling() -> None:
    """
    Validates scaling for liquid beverages with ml units and liquid HFSS thresholds.
    """
    inp_liquid = RawNutrientInput(
        serving_size=200.0,
        serving_unit=ServingUnit.ML,
        basis=ServingBasis.PER_100ML,
        food_form=FoodForm.LIQUID,
        energy_kcal=45.0,
        protein_g=0.1,
        carbohydrates_g=11.0,
        total_sugar_g=10.5,
        added_sugar_g=8.0,
        total_fat_g=0.0,
        saturated_fat_g=0.0,
        trans_fat_g=0.0,
        sodium_mg=25.0,
    )
    result = analyze_nutrition(inp_liquid)

    # 200 ml serving is 2x the 100 ml amount
    assert result.per_serving["energy_kcal"] == 90.0
    assert result.per_serving["added_sugar_g"] == 16.0
    assert result.per_serving["sodium_mg"] == 50.0

    # Liquid threshold for added sugar is 6.0 g / 100 ml. 8.0 >= 6.0 -> high added sugar flag!
    sugar_flag = next((f for f in result.flags if f.id == "high_added_sugar"), None)
    assert sugar_flag is not None
    assert "Proposed Criteria" in sugar_flag.title
    assert "100ml" in sugar_flag.explanation


def test_strict_preservation_of_missing_vs_zero() -> None:
    """
    Guarantees missing nutrients (None) are never treated as zero, and explicit
    zeroes (0.0) are accurately calculated with 0.0% daily value.
    """
    inp = RawNutrientInput(
        serving_size=50.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=220.0,
        protein_g=4.0,
        carbohydrates_g=30.0,
        total_sugar_g=10.0,
        added_sugar_g=None,  # Missing
        total_fat_g=8.0,
        saturated_fat_g=None,  # Missing
        trans_fat_g=0.0,  # Explicit zero
        sodium_mg=200.0,
    )
    result = analyze_nutrition(inp)

    # Missing nutrients remain strictly None
    assert result.per_100["added_sugar_g"] is None
    assert result.per_serving["added_sugar_g"] is None
    assert result.per_100["saturated_fat_g"] is None
    assert result.per_serving["saturated_fat_g"] is None

    # Missing daily comparison has status not_provided
    added_comp = next(
        c for c in result.daily_value_comparisons if c.nutrient_key == "added_sugar_g"
    )
    assert added_comp.status == "not_provided"
    assert added_comp.percentage_of_daily_value is None

    # Explicit zero trans fat is calculated as 0.0%
    trans_comp = next(c for c in result.daily_value_comparisons if c.nutrient_key == "trans_fat_g")
    assert trans_comp.status == "calculated"
    assert trans_comp.percentage_of_daily_value == 0.0

    # Incompleteness is transparently flagged
    assert result.is_complete is False
    assert result.status == "incomplete_data"
    assert "added_sugar_g" in result.missing_nutrients
    assert "saturated_fat_g" in result.missing_nutrients


def test_discrete_serving_unit_preserves_per_serving_only() -> None:
    """
    Discrete pieces/portions cannot be scaled to 100g without individual piece mass.
    """
    inp = RawNutrientInput(
        serving_size=1.0,
        serving_unit=ServingUnit.PIECE,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=80.0,
        protein_g=1.5,
        carbohydrates_g=12.0,
        total_sugar_g=4.0,
        added_sugar_g=3.0,
        total_fat_g=3.0,
        saturated_fat_g=1.5,
        trans_fat_g=0.0,
        sodium_mg=60.0,
    )
    res = analyze_nutrition(inp)

    # Per-serving is populated
    assert res.per_serving["energy_kcal"] == 80.0
    # Per-100 must be all None
    for k in ALL_NUTRIENT_KEYS:
        assert res.per_100[k] is None

    # Info flag explaining discrete unit
    assert any(f.id == "discrete_serving_unit" for f in res.flags)


def test_invalid_negative_values_rejected() -> None:
    """
    Pydantic schema validation rejects negative numbers for serving size and nutrients.
    """
    with pytest.raises(ValidationError) as exc:
        NutritionAnalysisRequest(
            serving_size=-10.0,  # Negative serving size
            energy_kcal=100.0,
        )
    assert "greater than 0" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        NutritionAnalysisRequest(
            serving_size=30.0,
            sodium_mg=-5.0,  # Negative nutrient
        )
    assert "greater than or equal to 0" in str(exc.value)


def test_biological_plausibility_validations() -> None:
    """
    Validates biological sanity checks on package labels:
    1. Added sugar cannot exceed total sugar
    2. Total sugar cannot exceed carbohydrates
    3. Saturated fat + trans fat cannot exceed total fat
    4. Declared calories cannot violate minimum fat calories (8 kcal/g)
    """
    # 1. Added sugar > total sugar
    with pytest.raises(ValidationError, match="Added sugar .* cannot exceed total sugar"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            total_sugar_g=5.0,
            added_sugar_g=6.0,
        )

    # 2. Total sugar > total carbohydrates
    with pytest.raises(ValidationError, match="Total sugar .* cannot exceed total carbohydrates"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            carbohydrates_g=10.0,
            total_sugar_g=12.0,
        )

    # 3. Sub-fats > total fat
    with pytest.raises(ValidationError, match="cannot exceed total fat"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            total_fat_g=5.0,
            saturated_fat_g=4.0,
            trans_fat_g=2.0,  # 4 + 2 = 6 > 5
        )

    # 4. Impossible energy given fat content (Fat produces ~9 kcal/g, thermodynamic min 8 kcal/g)
    with pytest.raises(ValidationError, match="biologically implausible"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            total_fat_g=20.0,
            energy_kcal=100.0,  # 20g fat alone requires at least 160 kcal
        )


def test_division_by_zero_prevention() -> None:
    """
    Ensures zero serving size triggers clear ValueError.
    """
    inp = RawNutrientInput(
        serving_size=0.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
    )
    with pytest.raises(ValueError, match="Serving size must be greater than zero"):
        normalize_nutrients(inp)


def test_flag_regulatory_status_distinction() -> None:
    """
    Ensures mandatory binding laws and draft non-binding criteria are cleanly distinguished.
    """
    # High sugar + High trans fat product
    inp = RawNutrientInput(
        serving_size=100.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        added_sugar_g=25.0,
        trans_fat_g=0.5,
        saturated_fat_g=8.0,
        sodium_mg=800.0,
    )
    res = analyze_nutrition(inp)

    # Trans fat is binding law
    trans_flag = next(f for f in res.flags if f.id == "elevated_trans_fat")
    assert trans_flag.regulatory_status == RegulatoryStatus.MANDATORY_REGULATION
    assert trans_flag.severity == FlagSeverity.ALERT

    # Added sugar is draft criteria
    sugar_flag = next(f for f in res.flags if f.id == "high_added_sugar")
    assert sugar_flag.regulatory_status == RegulatoryStatus.PROPOSED_DRAFT_CRITERIA
    assert sugar_flag.severity == FlagSeverity.WARNING

    # Saturated fat is draft criteria
    sat_flag = next(f for f in res.flags if f.id == "high_saturated_fat")
    assert sat_flag.regulatory_status == RegulatoryStatus.PROPOSED_DRAFT_CRITERIA

    # Sodium is draft criteria
    sodium_flag = next(f for f in res.flags if f.id == "high_sodium")
    assert sodium_flag.regulatory_status == RegulatoryStatus.PROPOSED_DRAFT_CRITERIA


def test_all_canonical_fixtures_nutrition_analysis() -> None:
    """
    Runs deterministic nutrition analysis on all 9 canonical fixtures
    to verify calculation stability and data completeness contracts.
    """
    from tests.fixtures.realistic_fixtures import load_realistic_fixtures

    fixtures = load_realistic_fixtures()
    for fixture in fixtures:
        parser_data = fixture["expected_parser"]
        serving_size = fixture.get("serving_size") or 30.0
        serving_unit = ServingUnit.ML if fixture.get("serving_unit") == "ml" else ServingUnit.G
        basis = (
            ServingBasis.PER_100G
            if fixture.get("declared_basis") == "per_100g"
            else (
                ServingBasis.PER_100ML
                if fixture.get("declared_basis") == "per_100ml"
                else ServingBasis.PER_SERVING
            )
        )
        food_form = FoodForm.LIQUID if fixture.get("food_form") == "liquid" else FoodForm.SOLID

        inp = RawNutrientInput(
            serving_size=serving_size,
            serving_unit=serving_unit,
            basis=basis,
            food_form=food_form,
            energy_kcal=parser_data.get("energy_kcal"),
            protein_g=parser_data.get("protein_g"),
            carbohydrates_g=parser_data.get("carbohydrates_g"),
            total_sugar_g=parser_data.get("total_sugar_g"),
            added_sugar_g=parser_data.get("added_sugar_g"),
            total_fat_g=parser_data.get("total_fat_g"),
            saturated_fat_g=parser_data.get("saturated_fat_g"),
            trans_fat_g=parser_data.get("trans_fat_g"),
            dietary_fiber_g=parser_data.get("dietary_fiber_g"),
            sodium_mg=parser_data.get("sodium_mg"),
        )

        res = analyze_nutrition(inp)
        assert res.disclaimer is not None
        assert res.serving_size == serving_size
        assert res.food_form == food_form
        assert len(res.daily_value_comparisons) > 0

        # Incomplete fixtures must report status incomplete_data
        if fixture["id"] == "fixture_07_incomplete_nutrition_label":
            assert res.is_complete is False
            assert res.status == "incomplete_data"
            assert "added_sugar_g" in res.missing_nutrients
            assert "trans_fat_g" in res.missing_nutrients
