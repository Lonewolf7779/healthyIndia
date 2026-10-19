from fastapi.testclient import TestClient


def test_analyze_ingredients_api_success(client: TestClient) -> None:
    payload = {
        "ingredients_text": (
            "Ragi Flour, Mustard Oil, Black Salt, "
            "Flavour Enhancer (INS 621), Raising Agent (500(ii)), Preservative (INS 211)"
        )
    }
    response = client.post("/api/v1/ingredients/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_matched"] == 3
    assert len(data["matched_items"]) == 3
    assert len(data["unmatched_items"]) == 3  # Ragi Flour, Mustard Oil, Black Salt

    matched_ids = [item["additive"]["id"] for item in data["matched_items"]]
    assert "ins-621" in matched_ids
    assert "ins-500ii" in matched_ids
    assert "ins-211" in matched_ids

    # Verify provenance and limitation fields are delivered
    msg_item = next(i for i in data["matched_items"] if i["additive"]["id"] == "ins-621")
    assert "Flavour enhancer" in msg_item["additive"]["functional_classes"]
    assert len(msg_item["additive"]["sources"]) > 0
    reg_status = msg_item["additive"]["regulatory_status"].lower()
    assert "prohibited in foods intended for infants" in reg_status


def test_analyze_ingredients_api_empty_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/ingredients/analyze", json={"ingredients_text": ""})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
