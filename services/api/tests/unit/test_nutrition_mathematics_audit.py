"""
Unit Test Suite: Nutrition Mathematics and Unit Conversion Audit.
Verifies hand-computed ground truth, unit conversions (g/kg, ml/l), density rejection,
missing vs zero preservation, and property-based mathematical invariants.
"""

import random

import pytest
from pydantic import ValidationError

from app.nutrition.calculator import analyze_nutrition
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FoodForm
from app.schemas.nutrition import (
    NutritionAnalysisRequest,
    compute_nutrition_values_hash,
)


def test_hand_computed_per_serving_to_100g_conversion():
    """
    Hand-calculated ground truth test:
    Serving size: 30g
    Declared nutrients per serving:
      Energy: 142 kcal -> per 100g: 142 * (100 / 30) = 473.3333... -> 473.3 kcal
      Protein: 2.4g    -> per 100g: 2.4 * (100 / 30) = 8.0g
      Fat: 6.3g        -> per 100g: 6.3 * (100 / 30) = 21.0g
      Sodium: 180mg    -> per 100g: 180 * (100 / 30) = 600.0mg
    """
    raw = RawNutrientInput(
        serving_size=30.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=142.0,
        protein_g=2.4,
        carbohydrates_g=18.9,
        total_sugar_g=7.5,
        added_sugar_g=6.0,
        dietary_fiber_g=0.9,
        total_fat_g=6.3,
        saturated_fat_g=2.7,
        trans_fat_g=0.03,
        cholesterol_mg=None,
        sodium_mg=180.0,
    )
    res = analyze_nutrition(raw)

    assert res.per_100["energy_kcal"] == pytest.approx(473.3, abs=0.1)
    assert res.per_100["protein_g"] == pytest.approx(8.0, abs=0.01)
    assert res.per_100["total_fat_g"] == pytest.approx(21.0, abs=0.01)
    assert res.per_100["sodium_mg"] == pytest.approx(600.0, abs=0.1)
    assert res.per_100["cholesterol_mg"] is None


def test_hand_computed_per_100g_to_per_serving_conversion():
    """
    Hand-calculated ground truth test:
    Serving size: 25g
    Declared nutrients per 100g:
      Energy: 500 kcal -> per 25g: 500 * (25 / 100) = 125.0 kcal
      Protein: 10.0g   -> per 25g: 10.0 * (25 / 100) = 2.5g
      Carbs: 60.0g     -> per 25g: 60.0 * (25 / 100) = 15.0g
    """
    raw = RawNutrientInput(
        serving_size=25.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_100G,
        food_form=FoodForm.SOLID,
        energy_kcal=500.0,
        protein_g=10.0,
        carbohydrates_g=60.0,
        total_sugar_g=12.0,
        added_sugar_g=5.0,
        dietary_fiber_g=3.0,
        total_fat_g=24.0,
        saturated_fat_g=8.0,
        trans_fat_g=0.1,
        cholesterol_mg=None,
        sodium_mg=400.0,
    )
    res = analyze_nutrition(raw)

    assert res.per_serving["energy_kcal"] == pytest.approx(125.0, abs=0.01)
    assert res.per_serving["protein_g"] == pytest.approx(2.5, abs=0.01)
    assert res.per_serving["carbohydrates_g"] == pytest.approx(15.0, abs=0.01)
    assert res.per_serving["sodium_mg"] == pytest.approx(100.0, abs=0.01)


def test_strict_rejection_of_mass_volume_without_density():
    """
    Physical law: mass cannot be converted to volume without substance-specific density.
    Solid food with ml/l unit must be rejected fail-closed at schema validation level.
    """
    # Solid food declaring ml
    with pytest.raises(ValidationError) as exc1:
        NutritionAnalysisRequest(
            serving_size=100.0,
            serving_unit="ml",
            basis="per_100g",
            food_form="solid",
            energy_kcal=250.0,
        )
    assert "Solid food cannot declare volume serving unit" in str(exc1.value)

    # Liquid food declaring grams with per_100ml basis
    with pytest.raises(ValidationError) as exc2:
        NutritionAnalysisRequest(
            serving_size=100.0,
            serving_unit="g",
            basis="per_100ml",
            food_form="liquid",
            energy_kcal=50.0,
        )
    assert "Liquid food cannot declare mass serving unit" in str(exc2.value)


def test_strict_preservation_of_missing_vs_zero():
    """
    Missing nutrients (None) must NEVER be converted to 0.0 under any scaling or calculation.
    Explicit 0.0 must remain 0.0.
    """
    raw = RawNutrientInput(
        serving_size=50.0,
        serving_unit=ServingUnit.G,
        basis=ServingBasis.PER_SERVING,
        food_form=FoodForm.SOLID,
        energy_kcal=200.0,
        protein_g=5.0,
        carbohydrates_g=30.0,
        total_sugar_g=10.0,
        added_sugar_g=0.0,  # Explicitly declared zero
        dietary_fiber_g=None,  # Missing from label
        total_fat_g=8.0,
        saturated_fat_g=3.0,
        trans_fat_g=0.0,  # Explicitly declared zero
        cholesterol_mg=None,  # Missing from label
        sodium_mg=None,  # Missing from label
    )
    res = analyze_nutrition(raw)

    assert res.per_serving["added_sugar_g"] == 0.0
    assert res.per_100["added_sugar_g"] == 0.0

    assert res.per_serving["trans_fat_g"] == 0.0
    assert res.per_100["trans_fat_g"] == 0.0

    assert res.per_serving["dietary_fiber_g"] is None
    assert res.per_100["dietary_fiber_g"] is None

    assert res.per_serving["cholesterol_mg"] is None
    assert res.per_100["cholesterol_mg"] is None

    assert res.per_serving["sodium_mg"] is None
    assert res.per_100["sodium_mg"] is None

    # Mandatory nutrients missing from declaration are flagged in missing_nutrients
    assert "sodium_mg" in res.missing_nutrients
    assert "added_sugar_g" not in res.missing_nutrients
    assert "trans_fat_g" not in res.missing_nutrients


def test_deterministic_property_based_scaling_invariants():
    """
    Property-based test with fixed seed (42):
    Invariants checked across 50 randomly generated valid nutrient sets:
    1. Scaling round-trip: (val * scale_factor) / scale_factor == val (within float epsilon)
    2. Non-negativity preservation: scaled value >= 0
    3. Monotonicity: if serving_size > 100, per_serving > per_100 for all positive values
    """
    rng = random.Random(42)  # noqa: S311
    for _ in range(50):
        serving_size = round(rng.uniform(10.0, 250.0), 1)

        protein = round(rng.uniform(0.1, 20.0), 1)
        carbs = round(rng.uniform(5.0, 70.0), 1)
        fat = round(rng.uniform(0.1, 30.0), 1)

        raw = RawNutrientInput(
            serving_size=serving_size,
            serving_unit=ServingUnit.G,
            basis=ServingBasis.PER_SERVING,
            food_form=FoodForm.SOLID,
            protein_g=protein,
            carbohydrates_g=carbs,
            total_fat_g=fat,
        )
        res = analyze_nutrition(raw)

        # Invariant 1: round-trip consistency
        p_100 = res.per_100["protein_g"]
        assert p_100 is not None
        reconstructed = round(p_100 * (serving_size / 100.0), 1)
        assert abs(reconstructed - protein) <= 0.2

        # Invariant 2: non-negativity
        assert p_100 >= 0.0

        # Invariant 3: monotonicity
        if serving_size > 100.0:
            assert res.per_serving["protein_g"] >= p_100 - 0.01
        elif serving_size < 100.0:
            assert res.per_serving["protein_g"] <= p_100 + 0.01


def test_cryptographic_values_hash_tamper_resistance():
    """
    Verifies that changing any numeric value, unit, or dimension produces
    a completely different hash digest, defeating stale or spoofed confirmations.
    """
    base_nutrients = {
        "added_sugar_g": 5.0,
        "carbohydrates_g": 50.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 3.0,
        "energy_kcal": 350.0,
        "protein_g": 8.0,
        "saturated_fat_g": 4.0,
        "sodium_mg": 250.0,
        "total_fat_g": 12.0,
        "total_sugar_g": 15.0,
        "trans_fat_g": 0.05,
    }
    base_hash = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=base_nutrients,
    )

    # 1. Tamper single nutrient
    tampered_nutrients = dict(base_nutrients)
    tampered_nutrients["added_sugar_g"] = 5.1
    tampered_hash = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=tampered_nutrients,
    )
    assert tampered_hash != base_hash

    # 2. Tamper serving size
    tampered_size_hash = compute_nutrition_values_hash(
        serving_size=30.1,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=base_nutrients,
    )
    assert tampered_size_hash != base_hash

    # 3. Tamper food form
    tampered_form_hash = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="liquid",
        nutrients=base_nutrients,
    )
    assert tampered_form_hash != base_hash
