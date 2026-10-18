"""
Phase 6: Adversarial End-to-End API Integration Tests.
Exhaustively tests API boundary validation, fail-closed unconfirmed execution,
physical/biological constraints, mass vs volume rejection, metric scaling,
and missing-value preservation.
"""

from fastapi.testclient import TestClient


def test_unconfirmed_request_rejected_fail_closed(client: TestClient) -> None:
    """
    Validates that unconfirmed requests (is_confirmed=False) fail closed with HTTP 422.
    """
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 140.0,
        "protein_g": 2.5,
        "is_confirmed": False,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422
    err_body = response.json()
    assert "confirmation" in str(err_body).lower()


def test_incompatible_unit_rejection_without_density(client: TestClient) -> None:
    """
    Validates physical laws: solid cannot use volume (ml/l), liquid cannot use mass (g/kg).
    """
    # 1. Solid food declaring ml
    res1 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 50.0,
            "serving_unit": "ml",
            "basis": "per_serving",
            "food_form": "solid",
            "energy_kcal": 100.0,
            "is_confirmed": True,
        },
    )
    assert res1.status_code == 422
    assert "density" in str(res1.json()).lower()

    # 2. Solid food declaring l
    res2 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 0.5,
            "serving_unit": "l",
            "basis": "per_serving",
            "food_form": "solid",
            "energy_kcal": 100.0,
            "is_confirmed": True,
        },
    )
    assert res2.status_code == 422

    # 3. Solid food declaring per_100ml basis
    res3 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 30.0,
            "serving_unit": "g",
            "basis": "per_100ml",
            "food_form": "solid",
            "energy_kcal": 100.0,
            "is_confirmed": True,
        },
    )
    assert res3.status_code == 422

    # 4. Liquid food declaring g
    res4 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 200.0,
            "serving_unit": "g",
            "basis": "per_serving",
            "food_form": "liquid",
            "energy_kcal": 90.0,
            "is_confirmed": True,
        },
    )
    assert res4.status_code == 422
    assert "density" in str(res4.json()).lower()

    # 5. Liquid food declaring kg
    res5 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 0.2,
            "serving_unit": "kg",
            "basis": "per_serving",
            "food_form": "liquid",
            "energy_kcal": 90.0,
            "is_confirmed": True,
        },
    )
    assert res5.status_code == 422

    # 6. Liquid food declaring per_100g basis
    res6 = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "serving_size": 200.0,
            "serving_unit": "ml",
            "basis": "per_100g",
            "food_form": "liquid",
            "energy_kcal": 90.0,
            "is_confirmed": True,
        },
    )
    assert res6.status_code == 422


def test_macronutrient_sum_exceeds_physical_limit_rejected(client: TestClient) -> None:
    """
    Validates that per_100g macronutrient sum exceeding 105g is rejected with HTTP 422.
    """
    payload = {
        "serving_size": 100.0,
        "serving_unit": "g",
        "basis": "per_100g",
        "food_form": "solid",
        "protein_g": 40.0,
        "carbohydrates_g": 50.0,
        "total_fat_g": 30.0,  # 40 + 50 + 30 = 120g > 105g limit
        "is_confirmed": True,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422
    assert "105g" in str(response.json())


def test_saturated_fat_exceeding_total_fat_rejected(client: TestClient) -> None:
    """
    Validates that saturated fat > total fat fails validation.
    """
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "total_fat_g": 4.0,
        "saturated_fat_g": 6.0,  # 6.0 > 4.0
        "is_confirmed": True,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422
    assert "saturated fat" in str(response.json()).lower()


def test_added_sugar_exceeding_total_sugar_rejected(client: TestClient) -> None:
    """
    Validates that added sugar > total sugar fails validation.
    """
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "total_sugar_g": 5.0,
        "added_sugar_g": 8.0,  # 8.0 > 5.0
        "is_confirmed": True,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422
    assert "added sugar" in str(response.json()).lower()


def test_negative_nutrient_values_rejected(client: TestClient) -> None:
    """
    Validates that negative nutrient amounts are rejected fail-closed.
    """
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": -100.0,
        "is_confirmed": True,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422


def test_metric_scaling_kg_and_l(client: TestClient) -> None:
    """
    Validates that kg scales by 1000 to g, and l scales by 1000 to ml.
    """
    # 1. Solid food with kg serving unit
    kg_payload = {
        "serving_size": 0.05,  # 0.05 kg = 50 g
        "serving_unit": "kg",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 200.0,
        "protein_g": 5.0,
        "is_confirmed": True,
    }
    kg_res = client.post("/api/v1/nutrition/analyze", json=kg_payload)
    assert kg_res.status_code == 200
    kg_data = kg_res.json()
    assert kg_data["serving_size"] == 0.05
    assert kg_data["serving_unit"] == "kg"
    # Per serving energy is 200, so per 100g should be 200 * (100 / 50) = 400
    assert kg_data["per_100"]["energy_kcal"] == 400.0

    # 2. Liquid food with l serving unit
    l_payload = {
        "serving_size": 0.25,  # 0.25 l = 250 ml
        "serving_unit": "l",
        "basis": "per_serving",
        "food_form": "liquid",
        "energy_kcal": 100.0,
        "is_confirmed": True,
    }
    l_res = client.post("/api/v1/nutrition/analyze", json=l_payload)
    assert l_res.status_code == 200
    l_data = l_res.json()
    assert l_data["serving_size"] == 0.25
    assert l_data["serving_unit"] == "l"
    # Per serving energy is 100, so per 100ml should be 100 * (100 / 250) = 40
    assert l_data["per_100"]["energy_kcal"] == 40.0


def test_missing_values_strictly_preserved_as_null(client: TestClient) -> None:
    """
    Validates that omitted nutrients remain None and are never silently defaulted to zero.
    """
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 120.0,
        "protein_g": 2.0,
        "is_confirmed": True,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["per_serving"]["added_sugar_g"] is None
    assert data["per_serving"]["sodium_mg"] is None
    assert data["per_serving"]["dietary_fiber_g"] is None
    assert data["per_100"]["added_sugar_g"] is None
    assert data["per_100"]["sodium_mg"] is None
    assert "added_sugar_g" in data["missing_nutrients"]
    assert "sodium_mg" in data["missing_nutrients"]
