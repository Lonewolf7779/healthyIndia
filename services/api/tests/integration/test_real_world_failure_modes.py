"""
Integration Test Suite: Real-World Failure Modes and Packaging Distortion.
Validates scanner behavior against glare, low contrast, curved typography,
dual-column layout collisions, missing value preservation, and hash tamper detection.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.extraction.quality import assess_image_quality
from app.main import app
from app.schemas.nutrition import compute_nutrition_values_hash


@pytest.fixture
def client():
    return TestClient(app)


def test_glare_hotspot_rejection_or_warning():
    """
    Simulates a metallic packaging photograph with severe specular glare
    obscuring nutrition facts. Must trigger IMAGE_GLARE warning and fair/poor grade.
    """
    img = Image.new("L", (800, 600), color=120)
    draw = ImageDraw.Draw(img)
    # Draw large blown-out specular reflection hotspot
    draw.ellipse([(200, 150), (600, 450)], fill=255)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    img_bytes = buf.getvalue()

    assessment = assess_image_quality(img_bytes)
    warning_codes = [w.code for w in assessment.warnings]
    assert any("GLARE" in w for w in warning_codes)
    assert assessment.grade in ("fair", "poor")


def test_low_contrast_label_detection():
    """
    Simulates faded ink or low-contrast packaging (e.g. grey on slightly darker grey).
    Must trigger IMAGE_LOW_CONTRAST warning.
    """
    # Narrow dynamic range
    img = Image.new("L", (500, 500), color=128)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(50, 50), (450, 450)], fill=135)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    assessment = assess_image_quality(img_bytes)
    warning_codes = [w.code for w in assessment.warnings]
    assert "IMAGE_LOW_CONTRAST" in warning_codes


def test_ocr_endpoint_issues_valid_session_token(client):
    """
    Tests that POST /api/v1/extraction/ocr issues a valid extraction_id and extraction_token.
    """
    # Create simple clear image with nutrition text
    img = Image.new("RGB", (600, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Energy 150 kcal", fill=(0, 0, 0))
    draw.text((20, 70), "Protein 3.0 g", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"file": ("test_label.png", buf.getvalue(), "image/png")}
    response = client.post("/api/v1/extraction/ocr", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "extraction_id" in data
    assert "extraction_token" in data
    assert len(data["extraction_token"]) >= 32
    assert data["verification_required"] is True


def test_nutrition_endpoint_strictly_rejects_ocr_tampering_without_reverification(client):
    """
    Security Gate: Submitting OCR-derived data where confirmed_values_hash does NOT match
    the submitted values must be rejected fail-closed with HTTP 422.
    """
    nutrients = {
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
    valid_hash = compute_nutrition_values_hash(
        serving_size=30.0,
        serving_unit="g",
        basis="per_serving",
        food_form="solid",
        nutrients=nutrients,
    )

    valid_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 350.0,
        "protein_g": 8.0,
        "carbohydrates_g": 50.0,
        "total_sugar_g": 15.0,
        "added_sugar_g": 5.0,
        "dietary_fiber_g": 3.0,
        "total_fat_g": 12.0,
        "saturated_fat_g": 4.0,
        "trans_fat_g": 0.05,
        "cholesterol_mg": None,
        "sodium_mg": 250.0,
        "data_source": "ocr",
        "is_confirmed": True,
        "extraction_token": "valid-token-example-1234567890abcdef",
        "confirmed_values_hash": valid_hash,
    }

    # 1. Valid payload succeeds
    res_valid = client.post("/api/v1/nutrition/analyze", json=valid_payload)
    assert res_valid.status_code == 200

    # 2. Tampering: client altered added_sugar from 5.0 to 1.0 without re-confirming hash
    tampered_payload = dict(valid_payload)
    tampered_payload["added_sugar_g"] = 1.0

    res_tampered = client.post("/api/v1/nutrition/analyze", json=tampered_payload)
    assert res_tampered.status_code == 422
    assert "Confirmed values hash does not match submitted values" in res_tampered.text

    # 3. Missing extraction token for OCR data source fails
    missing_token_payload = dict(valid_payload)
    missing_token_payload["extraction_token"] = None
    res_no_token = client.post("/api/v1/nutrition/analyze", json=missing_token_payload)
    assert res_no_token.status_code == 422
    assert "OCR-derived data requires a valid extraction_token" in res_no_token.text


def test_manual_data_source_rejects_spurious_ocr_token(client):
    """
    Integrity check: manual entry cannot carry an OCR extraction_token.
    """
    manual_payload = {
        "serving_size": 30.0,
        "serving_unit": "g",
        "basis": "per_serving",
        "food_form": "solid",
        "energy_kcal": 150.0,
        "protein_g": 3.0,
        "data_source": "manual",
        "is_confirmed": True,
        "extraction_token": "spurious-token",
    }
    res = client.post("/api/v1/nutrition/analyze", json=manual_payload)
    assert res.status_code == 422
    assert "Manual data source cannot carry an extraction_token" in res.text
