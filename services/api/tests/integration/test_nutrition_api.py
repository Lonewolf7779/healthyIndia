from fastapi.testclient import TestClient


def test_analyze_endpoint_complete_data(client: TestClient) -> None:
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 140.0,
        "protein_g": 3.0,
        "carbohydrates_g": 20.0,
        "total_sugar_g": 10.0,
        "added_sugar_g": 8.0,
        "dietary_fiber_g": 2.0,
        "total_fat_g": 6.0,
        "saturated_fat_g": 3.0,
        "trans_fat_g": 0.0,
        "cholesterol_mg": 0.0,
        "sodium_mg": 240.0,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "complete"
    assert data["is_complete"] is True
    assert data["serving_size"] == 30.0
    assert len(data["missing_nutrients"]) == 0

    # 8g added sugar per 30g serving = ~26.67g per 100g -> triggers high_added_sugar
    assert any(flag["id"] == "high_added_sugar" for flag in data["flags"])

    # Verify daily value comparison exists
    added_sugar_comp = next(
        c for c in data["daily_value_comparisons"] if c["nutrient_key"] == "added_sugar_g"
    )
    assert added_sugar_comp["status"] == "calculated"
    assert added_sugar_comp["percentage_of_daily_value"] == 16.0  # 8g / 50g * 100 = 16%


def test_analyze_endpoint_incomplete_data(client: TestClient) -> None:
    payload = {
        "serving_size": 50.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 200.0,
        "protein_g": 5.0,
        # Added sugar, trans fat, sodium omitted
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "incomplete_data"
    assert data["is_complete"] is False
    assert "added_sugar_g" in data["missing_nutrients"]
    assert "trans_fat_g" in data["missing_nutrients"]
    assert "sodium_mg" in data["missing_nutrients"]

    # Values in response must be None (null in JSON)
    assert data["per_serving"]["added_sugar_g"] is None
    assert data["per_100"]["added_sugar_g"] is None


def test_analyze_endpoint_validation_error(client: TestClient) -> None:
    # Negative protein and serving size 0
    payload = {
        "serving_size": 0.0,
        "protein_g": -5.0,
    }
    response = client.post("/api/v1/nutrition/analyze", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert len(data["error"]["details"]) > 0
