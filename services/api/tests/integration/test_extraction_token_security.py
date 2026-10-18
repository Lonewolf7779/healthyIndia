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

from app.core.security import (
    generate_confirmation_token,
    generate_extraction_token,
    verify_confirmation_token,
    verify_extraction_token,
)
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


def test_verify_confirmation_token_unit_cases():
    """Direct unit tests for verify_confirmation_token covering formats, digests, and bounds."""
    mock_hmac_key = "mock_key_padding_" + "c" * 16
    session_id = str(uuid.uuid4())
    digest = "a" * 64
    now = int(time.time())

    # 1. Valid token
    valid_token = generate_confirmation_token(
        session_id, values_digest=digest, secret_key=mock_hmac_key, timestamp=now
    )
    ok, err = verify_confirmation_token(
        valid_token,
        extraction_id=session_id,
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is True
    assert err == ""

    # 2. Missing extraction_id
    ok, err = verify_confirmation_token(
        valid_token, extraction_id="", expected_digest=digest, secret_key=mock_hmac_key
    )
    assert ok is False
    assert "required and cannot be empty" in err

    # 3. Malformed extraction_id
    ok, err = verify_confirmation_token(
        valid_token,
        extraction_id="not-a-uuid",
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "Malformed extraction_id" in err

    # 4. Mismatched extraction_id
    other_uuid = str(uuid.uuid4())
    ok, err = verify_confirmation_token(
        valid_token,
        extraction_id=other_uuid,
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "does not match provided" in err

    # 5. Digest mismatch (client altered values)
    different_digest = "b" * 64
    ok, err = verify_confirmation_token(
        valid_token,
        extraction_id=session_id,
        expected_digest=different_digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "digest does not match submitted values" in err

    # 6. Expired token (> 3600 seconds)
    expired_token = generate_confirmation_token(
        session_id, values_digest=digest, secret_key=mock_hmac_key, timestamp=now - 4000
    )
    ok, err = verify_confirmation_token(
        expired_token,
        extraction_id=session_id,
        expected_digest=digest,
        secret_key=mock_hmac_key,
        max_age_seconds=3600,
    )
    assert ok is False
    assert "expired" in err

    # 7. Future-dated token (> 60 seconds)
    future_token = generate_confirmation_token(
        session_id, values_digest=digest, secret_key=mock_hmac_key, timestamp=now + 200
    )
    ok, err = verify_confirmation_token(
        future_token,
        extraction_id=session_id,
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "in the future" in err

    # 8. Unkeyed SHA-256 hash passed as token
    ok, err = verify_confirmation_token(
        digest,
        extraction_id=session_id,
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "Unkeyed SHA-256 hash or malformed token detected" in err

    # 9. Tampered HMAC signature
    parts = valid_token.split(".")
    tampered_sig = parts[4][:-4] + "dead"
    tampered_token = f"{parts[0]}.{parts[1]}.{parts[2]}.{parts[3]}.{tampered_sig}"
    ok, err = verify_confirmation_token(
        tampered_token,
        extraction_id=session_id,
        expected_digest=digest,
        secret_key=mock_hmac_key,
    )
    assert ok is False
    assert "HMAC verification failed" in err


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
    conf_token = generate_confirmation_token(
        extraction_id=extraction_id,
        values_digest=digest,
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
        "confirmed_values_hash": conf_token,
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
    """
    Altering a nutrient value without recomputing confirmation token must fail closed with 422.
    """
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
    initial_conf_token = generate_confirmation_token(
        extraction_id=extraction_id,
        values_digest=initial_hash,
    )

    # Payload with altered energy_kcal (from 200 to 250) but old confirmation token
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
        "confirmed_values_hash": initial_conf_token,
    }
    res = client.post("/api/v1/nutrition/analyze", json=tampered_payload)
    assert res.status_code == 422
    assert "Confirmation integrity check failed" in res.text
    assert "digest does not match submitted values" in res.text


def test_api_rejects_altered_values_with_recomputed_ordinary_sha256(client):
    """
    CRITICAL ADVERSARIAL TEST:
    A client modifies a nutrient value and recomputes the ordinary unkeyed SHA-256 hash.
    Because an unkeyed SHA-256 cannot prove server-side confirmation or session binding,
    the API must strictly reject this with 422 fail-closed.
    """
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    nutrients = {
        "added_sugar_g": 0.0,  # Fabricated low-sugar claim
        "carbohydrates_g": 10.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 2.0,
        "energy_kcal": 50.0,  # Fabricated low-calorie claim
        "protein_g": 5.0,
        "saturated_fat_g": 0.0,
        "sodium_mg": 50.0,
        "total_fat_g": 1.0,
        "total_sugar_g": 0.0,
        "trans_fat_g": 0.0,
    }
    # Client computes the unkeyed SHA-256 hash of the modified values
    ordinary_sha256 = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )

    adversarial_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **nutrients,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": token,
        "confirmed_values_hash": ordinary_sha256,  # Unkeyed SHA-256 hash!
    }
    res = client.post("/api/v1/nutrition/analyze", json=adversarial_payload)
    assert res.status_code == 422
    assert "Confirmation integrity check failed" in res.text
    assert "Unkeyed SHA-256 hash or malformed token detected" in res.text


def test_api_accepts_legitimate_user_corrections_via_confirmation_endpoint(client):
    """
    LEGITIMATE CORRECTION WORKFLOW:
    User inspects OCR results, corrects an OCR misread error (e.g. 74.0g sugar -> 14.0g sugar),
    confirms the reviewed values via /api/v1/extraction/confirm, receives a server-keyed
    confirmation token, and successfully analyzes the corrected values (200 OK).
    """
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    # User-reviewed values with correction (14.0g instead of OCR misread 74.0g)
    corrected_nutrients = {
        "added_sugar_g": 8.0,
        "carbohydrates_g": 25.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 1.5,
        "energy_kcal": 160.0,
        "protein_g": 4.0,
        "saturated_fat_g": 2.5,
        "sodium_mg": 150.0,
        "total_fat_g": 6.0,
        "total_sugar_g": 14.0,  # User-corrected value!
        "trans_fat_g": 0.02,
    }

    # Step 1: User clicks "Confirm Values" in UI, calling server confirmation endpoint
    confirm_req = {
        "extraction_id": extraction_id,
        "extraction_token": token,
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **corrected_nutrients,
    }
    confirm_res = client.post("/api/v1/extraction/confirm", json=confirm_req)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "confirmed"
    assert confirm_data["extraction_id"] == extraction_id
    server_token = confirm_data["confirmed_values_hash"]
    assert server_token.startswith("c1.")

    # Step 2: User runs nutrition analysis with the server-authenticated confirmation token
    analyze_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **corrected_nutrients,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": extraction_id,
        "extraction_token": token,
        "confirmed_values_hash": server_token,
    }
    analyze_res = client.post("/api/v1/nutrition/analyze", json=analyze_payload)
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert analyze_data["status"] == "complete"
    assert analyze_data["per_serving"]["total_sugar_g"] == 14.0


def test_api_rejects_mismatched_extraction_id_in_confirmation_token(client):
    """Confirmation token issued for Session A reused for Session B must fail closed with 422."""
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())
    token_b = generate_extraction_token(extraction_id=session_b)

    nutrients = {
        "added_sugar_g": 2.0,
        "carbohydrates_g": 20.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 1.0,
        "energy_kcal": 120.0,
        "protein_g": 3.0,
        "saturated_fat_g": 1.0,
        "sodium_mg": 100.0,
        "total_fat_g": 4.0,
        "total_sugar_g": 5.0,
        "trans_fat_g": 0.0,
    }
    digest = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )
    conf_token_a = generate_confirmation_token(extraction_id=session_a, values_digest=digest)

    payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        **nutrients,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_id": session_b,  # Session B
        "extraction_token": token_b,
        "confirmed_values_hash": conf_token_a,  # Token issued for Session A!
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Confirmation integrity check failed" in res.text
    assert "does not match provided" in res.text


def test_api_rejects_expired_confirmation_token(client):
    """Confirmation token older than 3600 seconds must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    nutrients = {
        "added_sugar_g": 2.0,
        "carbohydrates_g": 20.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 1.0,
        "energy_kcal": 120.0,
        "protein_g": 3.0,
        "saturated_fat_g": 1.0,
        "sodium_mg": 100.0,
        "total_fat_g": 4.0,
        "total_sugar_g": 5.0,
        "trans_fat_g": 0.0,
    }
    digest = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )
    old_conf_token = generate_confirmation_token(
        extraction_id=extraction_id,
        values_digest=digest,
        timestamp=int(time.time()) - 4000,  # 4000 seconds ago
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
        "confirmed_values_hash": old_conf_token,
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Confirmation integrity check failed" in res.text
    assert "expired" in res.text


def test_api_rejects_tampered_confirmation_signature(client):
    """Confirmation token with forged or tampered signature must fail closed with 422."""
    extraction_id = str(uuid.uuid4())
    token = generate_extraction_token(extraction_id=extraction_id)

    nutrients = {
        "added_sugar_g": 2.0,
        "carbohydrates_g": 20.0,
        "cholesterol_mg": None,
        "dietary_fiber_g": 1.0,
        "energy_kcal": 120.0,
        "protein_g": 3.0,
        "saturated_fat_g": 1.0,
        "sodium_mg": 100.0,
        "total_fat_g": 4.0,
        "total_sugar_g": 5.0,
        "trans_fat_g": 0.0,
    }
    digest = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )
    valid_conf_token = generate_confirmation_token(
        extraction_id=extraction_id,
        values_digest=digest,
    )
    tampered_conf_token = valid_conf_token[:-4] + "dead"

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
        "confirmed_values_hash": tampered_conf_token,
    }
    res = client.post("/api/v1/nutrition/analyze", json=payload)
    assert res.status_code == 422
    assert "Confirmation integrity check failed" in res.text
    assert "HMAC verification failed" in res.text


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
    assert "Confirmation integrity check failed" in res.text


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
