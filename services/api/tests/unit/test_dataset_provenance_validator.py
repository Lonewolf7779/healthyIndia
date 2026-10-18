"""
Unit Test Suite: Dataset Provenance and Plausibility Validator.

Tests that validate_dataset.py strictly enforces:
1. Biological and physical plausibility constraints.
2. Rejection of empty-string SHA-256 placeholder hashes.
3. Separation of schema verification from physical image evidence.
4. Detection of false DOUBLE_VERIFIED claims when photographs are missing or invalid.
5. File existence, non-zero byte size, and cryptographic hash integrity on disk.
"""

import hashlib
import json

import pytest

from scripts.validate_dataset import (
    EMPTY_STRING_SHA256,
    validate_dataset,
    validate_image_provenance,
    validate_sample_plausibility,
)


@pytest.fixture
def minimal_valid_sample() -> dict:
    return {
        "sample_id": "TEST-001",
        "product_name": "Test Whole Grain Biscuits",
        "brand": "TestBrand",
        "category": "Biscuits & Cookies",
        "packaging_format": "wrapper",
        "image_filename": "TEST-001.jpg",
        "image_sha256": None,
        "capture_metadata": {
            "lighting_condition": "L1",
            "camera_angle": "A1",
            "framing": "F1",
            "packaging_state": "S1",
            "device_description": "Smartphone",
        },
        "ground_truth_nutrition": {
            "declaration_basis": "per_100g",
            "serving_size": 100.0,
            "serving_unit": "g",
            "food_form": "solid",
            "nutrients": {
                "energy_kcal": 450.0,
                "protein_g": 8.0,
                "carbohydrates_g": 65.0,
                "total_sugar_g": 15.0,
                "added_sugar_g": 12.0,
                "dietary_fiber_g": 6.0,
                "total_fat_g": 18.0,
                "saturated_fat_g": 7.0,
                "trans_fat_g": 0.05,
                "cholesterol_mg": None,
                "sodium_mg": 300.0,
            },
            "dual_column_values": None,
        },
        "ground_truth_ingredients_text": "Wheat flour, Sugar, Palm oil, Salt.",
        "verification": {
            "annotator_1": "ANN-1",
            "annotator_2": "ANN-2",
            "verified_date": "2026-10-18",
            "status": "SCHEMA_VERIFIED_EVIDENCE_PENDING",
        },
    }


def test_valid_plausibility_passes(minimal_valid_sample):
    errors = validate_sample_plausibility(minimal_valid_sample)
    assert len(errors) == 0


def test_sugar_hierarchy_violation(minimal_valid_sample):
    # Added sugar exceeds total sugar
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["added_sugar_g"] = 20.0
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["total_sugar_g"] = 15.0
    errors = validate_sample_plausibility(minimal_valid_sample)
    assert any("Added sugar (20.0g) exceeds Total sugar" in e for e in errors)


def test_fat_hierarchy_violation(minimal_valid_sample):
    # Saturated fat + trans fat exceeds total fat
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["total_fat_g"] = 10.0
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["saturated_fat_g"] = 11.0
    errors = validate_sample_plausibility(minimal_valid_sample)
    assert any("exceeds Total fat" in e for e in errors)


def test_mass_conservation_violation(minimal_valid_sample):
    # Macros exceed 105g per 100g
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["carbohydrates_g"] = 90.0
    minimal_valid_sample["ground_truth_nutrition"]["nutrients"]["total_fat_g"] = 30.0
    errors = validate_sample_plausibility(minimal_valid_sample)
    assert any("exceeds plausible physical limit" in e for e in errors)


def test_empty_string_sha256_rejected(tmp_path, minimal_valid_sample):
    """Placeholder hash of empty byte string must be rejected fail-closed."""
    minimal_valid_sample["image_sha256"] = EMPTY_STRING_SHA256
    dataset_file = tmp_path / "samples.json"
    dataset_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "dataset_name": "Test",
                "last_updated": "2026-10-18",
                "samples": [minimal_valid_sample],
            }
        ),
        encoding="utf-8",
    )
    ok, summary = validate_dataset(dataset_file, images_dir=tmp_path / "images")
    assert ok is False
    assert any("empty-string SHA-256 placeholder hash" in e for e in summary["errors"])


def test_false_double_verified_claim_fails(tmp_path, minimal_valid_sample):
    """Claiming DOUBLE_VERIFIED when no image file exists on disk must fail closed."""
    minimal_valid_sample["verification"]["status"] = "DOUBLE_VERIFIED"
    minimal_valid_sample["image_sha256"] = "a" * 64
    dataset_file = tmp_path / "samples.json"
    dataset_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "dataset_name": "Test",
                "last_updated": "2026-10-18",
                "samples": [minimal_valid_sample],
            }
        ),
        encoding="utf-8",
    )
    ok, summary = validate_dataset(dataset_file, images_dir=tmp_path / "images")
    assert ok is False
    assert any("Provenance Misrepresentation" in e for e in summary["errors"])


def test_zero_byte_image_file_rejected(tmp_path, minimal_valid_sample):
    """Empty 0-byte image file must be rejected."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    empty_file = images_dir / "TEST-001.jpg"
    empty_file.write_bytes(b"")

    minimal_valid_sample["image_sha256"] = EMPTY_STRING_SHA256
    ok, err = validate_image_provenance(minimal_valid_sample, images_dir)
    assert ok is False
    assert "Placeholder hashes are forbidden" in err


def test_sha256_mismatch_rejected(tmp_path, minimal_valid_sample):
    """Image file whose SHA-256 differs from recorded hash must be rejected."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    img_file = images_dir / "TEST-001.jpg"
    img_file.write_bytes(b"actual image bytes 123456789")

    minimal_valid_sample["image_sha256"] = "0" * 64
    ok, err = validate_image_provenance(minimal_valid_sample, images_dir)
    assert ok is False
    assert "Cryptographic SHA-256 mismatch" in err


def test_genuine_double_verified_passes_with_real_image(tmp_path, minimal_valid_sample):
    """Genuine image with matching SHA-256 digest on disk passes as DOUBLE_VERIFIED."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    img_bytes = b"real packaging photograph jpeg content simulation"
    actual_sha = hashlib.sha256(img_bytes).hexdigest()

    img_file = images_dir / "TEST-001.jpg"
    img_file.write_bytes(img_bytes)

    minimal_valid_sample["image_sha256"] = actual_sha
    minimal_valid_sample["verification"]["status"] = "DOUBLE_VERIFIED"

    dataset_file = tmp_path / "samples.json"
    dataset_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "dataset_name": "Test",
                "last_updated": "2026-10-18",
                "samples": [minimal_valid_sample],
            }
        ),
        encoding="utf-8",
    )

    ok, summary = validate_dataset(dataset_file, images_dir=images_dir, require_images=True)
    assert ok is True
    assert summary["verified_images_count"] == 1
    assert summary["double_verified_count"] == 1
    assert len(summary["errors"]) == 0


def test_schema_verified_evidence_pending_passes_without_image(tmp_path, minimal_valid_sample):
    """
    Reference sample with status SCHEMA_VERIFIED_EVIDENCE_PENDING and
    image_sha256=null passes schema audit.
    """
    dataset_file = tmp_path / "samples.json"
    dataset_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "dataset_name": "Test",
                "last_updated": "2026-10-18",
                "samples": [minimal_valid_sample],
            }
        ),
        encoding="utf-8",
    )

    ok, summary = validate_dataset(
        dataset_file, images_dir=tmp_path / "images", require_images=False
    )
    assert ok is True
    assert summary["schema_only_count"] == 1
    assert summary["pending_images_count"] == 1
    assert len(summary["errors"]) == 0
