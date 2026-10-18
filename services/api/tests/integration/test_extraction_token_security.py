"""
Security Integration Test Suite: Extraction Token Authenticity & Session Binding.

Verifies that the OCR extraction token is cryptographically authenticated using
constant-time HMAC-SHA256, strictly bound to the extraction session ID, checks timestamp
expiry fail-closed, rejects missing, empty, or malformed extraction IDs, and prevents
replay, parameter tampering, and fabricated confirmation digests.
"""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import generate_extraction_token, verify_extraction_token
from app.main import app
from app.schemas.nutrition import compute_nutrition_values_hash


@pytest.fixture
def client():
    return TestClient(app)


def test_verify_extraction_token_unit_cases():
    """Direct unit tests for verify_extraction_token covering timing, formats, and keys."""
    mock_hmac_key = "mock_key_padding_" + "k" * 16
    session_id = str(uuid.uuid4())
    now = int(time.time())

    # 1. Valid token
    valid_token = generate_extraction_token(session_id, secret_key=mock_hmac_key, timestamp=now)
    ok, err = verify_extraction_token(
        valid_token, extraction_id=session_id, secret_key=mock_hmac_key
    )
    assert ok is True
    assert err == ""

    # 2. Rejection of missing/empty extraction_id in verify
    ok, err = verify_extraction_token(valid_token, extraction_id="", secret_key=mock_hmac_key)
    assert ok is False
    assert "required and cannot be empty" in err

    # 3. Rejection of malformed extraction_id in verify
    ok, err = verify_extraction_token(
        valid_token, extraction_id="not-a-valid-uuid-string", secret_key=mock_hmac_key
    )
    assert ok is False
    assert "Malformed extraction_id" in err

    # 4. Mismatched extraction_id with another valid UUID
    mismatched_uuid = str(uuid.uuid4())
    ok, err = verify_extraction_token(
        valid_token, extraction_id=mismatched_uuid, secret_key=mock_hmac_key
    )
    assert ok is False
    assert "does not match" in err

    # 5. Expired token (e.g. 4000 seconds old)
    old_token = generate_extraction_token(
        session_id, secret_key=mock_hmac_key, timestamp=now - 4000
    )
    ok, err = verify_extraction_token(
        old_token, extraction_id=session_id, secret_key=mock_hmac_key, max_age_seconds=3600
    )
    assert ok is False
    assert "expired" in err

    # 6. Future-dated token (e.g. 200 seconds into future)
    future_token = generate_extraction_token(
        session_id, secret_key=mock_hmac_key, timestamp=now + 200
    )
    ok, err = verify_extraction_token(
        future_token, extraction_id=session_id, secret_key=mock_hmac_key
    )
    assert ok is False
    assert "in the future" in err

    # 7. Wrong secret key
    ok, err = verify_extraction_token(
        valid_token, extraction_id=session_id, secret_key="wrong_key_padding_" + "w" * 16
    )
    assert ok is False
    assert "HMAC verification failed" in err

    # 8. Tampered signature
    parts = valid_token.split(".")
    tampered_sig = parts[3][:-4] + "ffff"
    tampered_token = f"{parts[0]}.{parts[1]}.{parts[2]}.{tampered_sig}"
    ok, err = verify_extraction_token(
        tampered_token, extraction_id=session_id, secret_key=mock_hmac_key
    )
    assert ok is False
    assert "HMAC verification failed" in err

    # 9. Malformed structure
    assert verify_extraction_token("not-a-token", extraction_id=session_id)[0] is False
    assert verify_extraction_token("v1.only.two", extraction_id=session_id)[0] is False
    assert verify_extraction_token("", extraction_id=session_id)[0] is False


def test_api_valid_ocr_payload_with_authentic_token_succeeds(client):
    """End-to-end: authentic signed token matching extraction_id is accepted (200 OK)."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    nutrients = {
        "added_sugar_g": 4.0,
        "carbohydrates_g": 24.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 1.2,
        "energy_kcal": 150.0,
        "protein_g": 3.0,
        "saturated_fat_g": 2.0,
        "sodium_mg": 180.0,
        "total_fat_g": 5.0,
        "total_sugar_g": 6.0,
        "trans_fat_g": 0.01,
    }
    digest = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **nutrients,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": token,
        "confirmed_values_hash": digest,
    }

    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "complete"


def test_api_rejects_missing_extraction_id_for_ocr(client):
    """OCR source omitting extraction_id must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": None,
        "extraction_token": token,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "OCR-derived data requires a valid, non-empty extraction_id" in res.text


def test_api_rejects_empty_extraction_id_for_ocr(client):
    """OCR source with empty or whitespace-only extraction_id must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": "   ",
        "extraction_token": token,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "OCR-derived data requires a valid, non-empty extraction_id" in res.text


def test_api_rejects_malformed_extraction_id_for_ocr(client):
    """OCR source with malformed (non-canonical UUID) extraction_id must fail closed with 422."""
    token = f"v1.not-a-valid-uuid.{int(time.time())}.dummy"
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": "not-a-valid-uuid",
        "extraction_token": token,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Malformed extraction_id" in res.text


def test_api_rejects_missing_extraction_token_for_ocr(client):
    """OCR source omitting extraction_token must fail closed with 422."""
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": str(uuid.uuid4()),
        "extraction_token": None,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "OCR-derived data requires a valid extraction_token" in res.text


def test_api_rejects_arbitrary_random_string_token(client):
    """OCR source passing an arbitrary string as token must fail closed with 422."""
    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": str(uuid.uuid4()),
        "extraction_token": "arbitrary-fake-token-12345",
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Extraction token authentication failed" in res.text


def test_api_rejects_tampered_token_signature(client):
    """OCR source with modified token signature must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)
    tampered = token[:-4] + "dead"

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": tampered,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "HMAC verification failed" in res.text


def test_api_rejects_expired_extraction_token(client):
    """OCR source carrying an expired extraction token (>3600s) must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    expired_time = int(time.time()) - 7200  # 2 hours ago
    expired_token = generate_extraction_token(extraction_id=extraction_id, timestamp=expired_time)

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": expired_token,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "expired" in res.text


def test_api_rejects_token_signed_with_different_secret(client):
    """OCR source token signed with wrong secret must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    mismatched_key = "unauthorized_mock_key_" + "u" * 16
    forged_token = generate_extraction_token(extraction_id=extraction_id, secret_key=mismatched_key)

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": forged_token,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "HMAC verification failed" in res.text


def test_api_rejects_extraction_id_mismatch(client):
    """Token generated for session A reused with payload for session B must fail closed with 422."""
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())
    token_a = generate_extraction_token(extraction_id=session_a)

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": session_b,  # Mismatched!
        "extraction_token": token_a,
        "confirmed_values_hash": "dummyhash",
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "does not match provided" in res.text


def test_api_rejects_altered_values_without_reconfirmation(client):
    """Altering a nutrient value without recomputing confirmation hash must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    initial_nutrients = {
        "added_sugar_g": 5.0,
        "carbohydrates_g": 30.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 2.0,
        "energy_kcal": 200.0,
        "protein_g": 5.0,
        "saturated_fat_g": 3.0,
        "sodium_mg": 200.0,
        "total_fat_g": 8.0,
        "total_sugar_g": 10.0,
        "trans_fat_g": 0.05,
    }
    initial_hash = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=initial_nutrients,
    )

    # Payload with altered energy_kcal (from 200 to 250) but old confirmation hash
    tampered_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **initial_nutrients,
        "energy_kcal": 250.0,  # Modified value!
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": token,
        "confirmed_values_hash": initial_hash,
    }
    res = client.post("/api/v1/nutrition/analyze", json=tampered_payload)
    assert res.status_code == 422
    assert "Confirmed values hash does not match submitted values" in res.text


def test_api_rejects_fabricated_confirmation_hash(client):
    """Submitting a fabricated, arbitrary confirmation hash must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "protein_g": 3.0,
        "carbohydrates_g": 20.0,
        "total_sugar_g": 5.0,
        "added_sugar_g": 2.0,
        "dietary_fiber_g": 1.0,
        "total_fat_g": 5.0,
        "saturated_fat_g": 2.0,
        "trans_fat_g": 0.0,
        "cholesterol_mg": None,
        "sodium_mg": 100.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": token,
        "confirmed_values_hash": "deadbeef" * 8,  # Arbitrary fabricated hash
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Confirmed values hash does not match submitted values" in res.text


def test_api_manual_submission_rejects_extraction_id_or_token(client):
    """Manual submission carrying extraction_id or extraction_token must fail closed with 422."""
    payload_token = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "manual",
        "is_confirmed": True,
        "extraction_token": "some-token",
    }
    res1 = client.post("/api/v1/nutrition/analyze", json=payload_token)
    assert res1.status_code == 422
    assert "Manual data source cannot carry" in res1.text

    payload_id = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "data_source": "manual",
        "is_confirmed": True,
        "extraction_id": str(uuid.uuid4()),
    }
    res2 = client.post("/api/v1/nutrition/analyze", json=payload_id)
    assert res2.status_code == 422
    assert "Manual data source cannot carry" in res2.text


def test_api_manual_submission_succeeds_without_extraction_provenance(client):
    """Manual submission without extraction_id or extraction_token succeeds normally (200 OK)."""
    manual_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "protein_g": 3.0,
        "carbohydrates_g": 20.0,
        "total_sugar_g": 5.0,
        "added_sugar_g": 2.0,
        "dietary_fiber_g": 1.0,
        "total_fat_g": 5.0,
        "saturated_fat_g": 2.0,
        "trans_fat_g": 0.0,
        "cholesterol_mg": None,
        "sodium_mg": 100.0,
        "data_source": "manual",
        "is_confirmed": True,
    }
    res = client.post("/api/v1/nutrition/analyze", json=manual_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "complete"
