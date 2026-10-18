import pytest

from app.nutrition.calculator import analyze_nutrition, normalize_nutrients
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FlagSeverity, FoodForm, RegulatoryStatus


def test_normal_per_serving_conversion() -> None:
    # 30g serving, 150 kcal, 6g fat, 18g carbs, 6g added sugar, 300mg sodium
    raw_input = RawNutrientInput(
        serving_size=30.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=150.0,
        protein_g=3.0,
        carbohydrates_g=18.0,
        total_sugar_g=8.0,
        added_sugar_g=6.0,
        total_fat_g=6.0,
        saturated_fat_g=3.0,
        trans_fat_g=0.0,
        sodium_mg=300.0,
    )
    result = analyze_nutrition(raw_input)

    assert result.status == "complete"
    assert result.is_complete is True
    # 30g -> 100g factor is 100/30 = 3.333...
    assert result.per_100["added_sugar_g"] == 20.0
    assert result.per_100["sodium_mg"] == 1000.0
    assert result.per_100["saturated_fat_g"] == 10.0

    # Check flags and regulatory status distinction
    sugar_flag = next(f for f in result.flags if f.id == "high_added_sugar")
    assert sugar_flag.regulatory_status == RegulatoryStatus.PROPOSED_DRAFT_CRITERIA
    assert "Proposed Criteria" in sugar_flag.title


def test_discrete_serving_unit_not_multiplied_to_100() -> None:
    # 1 piece (no weight in grams), e.g. 1 biscuit
    raw_input = RawNutrientInput(
        serving_size=1.0,
        serving_unit=ServingUnit.PIECE,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=50.0,
        protein_g=1.0,
        carbohydrates_g=8.0,
        total_sugar_g=4.0,
        added_sugar_g=3.0,
        total_fat_g=2.0,
        saturated_fat_g=1.0,
        trans_fat_g=0.0,
        sodium_mg=50.0,
    )
    result = analyze_nutrition(raw_input)

    # Per-serving retains reported values
    assert result.per_serving["added_sugar_g"] == 3.0

    # Per-100 MUST NOT be falsely computed as 3 * 100 = 300g!
    assert result.per_100["added_sugar_g"] is None
    assert result.per_100["energy_kcal"] is None

    # Flag explaining discrete unit must be present
    flag_ids = [f.id for f in result.flags]
    assert "discrete_serving_unit" in flag_ids


def test_normal_per_100g_conversion() -> None:
    raw_input = RawNutrientInput(
        serving_size=25.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        energy_kcal=400.0,
        protein_g=8.0,
        carbohydrates_g=60.0,
        total_sugar_g=20.0,
        added_sugar_g=16.0,
        total_fat_g=12.0,
        saturated_fat_g=4.0,
        trans_fat_g=0.0,
        sodium_mg=400.0,
    )
    result = analyze_nutrition(raw_input)

    assert result.status == "complete"
    assert result.per_100["energy_kcal"] == 400.0
    assert result.per_serving["energy_kcal"] == 100.0
    assert result.per_serving["added_sugar_g"] == 4.0
    assert result.per_serving["sodium_mg"] == 100.0


def test_missing_values_never_default_to_zero() -> None:
    raw_input = RawNutrientInput(
        serving_size=50.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=200.0,
        protein_g=4.0,
        carbohydrates_g=30.0,
        total_sugar_g=10.0,
        added_sugar_g=None,
        dietary_fiber_g=None,
        total_fat_g=5.0,
        saturated_fat_g=2.0,
        trans_fat_g=None,
        sodium_mg=150.0,
    )
    result = analyze_nutrition(raw_input)

    assert result.status == "incomplete_data"
    assert result.is_complete is False
    assert "added_sugar_g" in result.missing_nutrients
    assert "trans_fat_g" in result.missing_nutrients
    assert result.per_100["dietary_fiber_g"] is None
    assert result.per_serving["dietary_fiber_g"] is None

    # Strict check: values in per_100 and per_serving MUST be None, not 0.0
    assert result.per_100["added_sugar_g"] is None
    assert result.per_100["trans_fat_g"] is None
    assert result.per_serving["added_sugar_g"] is None
    assert result.per_serving["trans_fat_g"] is None

    added_sugar_comp = next(
        c for c in result.daily_value_comparisons if c.nutrient_key == "added_sugar_g"
    )
    assert added_sugar_comp.status == "not_provided"
    assert added_sugar_comp.percentage_of_daily_value is None

    flag_ids = [f.id for f in result.flags]
    assert "incomplete_label_data" in flag_ids


def test_zero_or_negative_serving_size_raises_error() -> None:
    raw_input_zero = RawNutrientInput(
        serving_size=0.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
    )
    with pytest.raises(ValueError, match="Serving size must be greater than zero"):
        normalize_nutrients(raw_input_zero)


def test_boundary_thresholds_for_solid_food() -> None:
    raw_at_threshold = RawNutrientInput(
        serving_size=100.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        added_sugar_g=10.0,
    )
    result_at = analyze_nutrition(raw_at_threshold)
    assert any(f.id == "high_added_sugar" for f in result_at.flags)

    raw_below_threshold = RawNutrientInput(
        serving_size=100.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        added_sugar_g=9.9,
    )
    result_below = analyze_nutrition(raw_below_threshold)
    assert not any(f.id == "high_added_sugar" for f in result_below.flags)


def test_trans_fat_binding_regulatory_flag() -> None:
    raw_trans = RawNutrientInput(
        serving_size=100.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        trans_fat_g=0.5,
    )
    result = analyze_nutrition(raw_trans)
    flag = next(f for f in result.flags if f.id == "elevated_trans_fat")
    assert flag.severity == FlagSeverity.ALERT
    assert flag.regulatory_status == RegulatoryStatus.MANDATORY_REGULATION
    assert "Binding Regulation" in flag.title
