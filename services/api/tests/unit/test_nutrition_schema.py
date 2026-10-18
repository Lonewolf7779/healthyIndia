import pytest
from pydantic import ValidationError

from app.schemas.nutrition import NutritionAnalysisRequest


def test_valid_nutrition_request() -> None:
    req = NutritionAnalysisRequest(
        serving_size=30.0,
        energy_kcal=120.0,
        protein_g=4.0,
        carbohydrates_g=15.0,
        total_sugar_g=5.0,
        added_sugar_g=3.0,
        total_fat_g=5.0,
        saturated_fat_g=2.0,
        trans_fat_g=0.0,
        sodium_mg=150.0,
    )
    assert req.serving_size == 30.0
    assert req.added_sugar_g == 3.0


def test_zero_serving_size_rejected() -> None:
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        NutritionAnalysisRequest(serving_size=0.0)


def test_negative_values_rejected() -> None:
    with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            protein_g=-5.0,
        )


def test_added_sugar_cannot_exceed_total_sugar() -> None:
    with pytest.raises(ValidationError, match="Added sugar .* cannot exceed total sugar"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            carbohydrates_g=20.0,
            total_sugar_g=5.0,
            added_sugar_g=8.0,
        )


def test_total_sugar_cannot_exceed_carbohydrates() -> None:
    with pytest.raises(ValidationError, match="Total sugar .* cannot exceed total carbohydrates"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            carbohydrates_g=10.0,
            total_sugar_g=15.0,
        )


def test_sub_fats_cannot_exceed_total_fat() -> None:
    with pytest.raises(ValidationError, match="cannot exceed total fat"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            total_fat_g=5.0,
            saturated_fat_g=4.0,
            trans_fat_g=2.0,
        )


def test_implausible_energy_relative_to_fat_rejected() -> None:
    with pytest.raises(ValidationError, match="biologically implausible"):
        NutritionAnalysisRequest(
            serving_size=30.0,
            total_fat_g=20.0,  # 20g fat provides min ~180 kcal
            energy_kcal=50.0,  # 50 kcal is impossible for 20g fat
        )
