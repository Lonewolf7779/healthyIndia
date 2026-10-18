"""
Automated Test Suite for the Physical-Photograph OCR Benchmark Runner.

Verifies:
1. Exact numeric matches and decimal tolerances.
2. Field-specific tolerances (e.g. energy, protein, trans fat, sodium).
3. Unit conversion (g <-> mg) and incompatible unit rejection.
4. Serving basis mismatch detection.
5. Omission (declared but missed) vs unexpected (hallucinated) prediction tracking.
6. Unreadable/null ground-truth field exclusions.
7. Processing failure handling (graceful capture without crashing).
8. Empty dataset, duplicate sample ID, and invalid record detection.
9. Levenshtein Character Error Rate (CER) and Word Error Rate (WER).
10. Deterministic repeated execution.
11. Fail-closed UNMEASURED reporting when physical photographs are absent.
"""

from pathlib import Path

from app.extraction.adapter import BaseOcrAdapter, OcrEngineError, OcrEngineOutput
from app.extraction.benchmark import (
    compare_nutrient_field,
    compute_character_error_rate,
    compute_ingredient_completeness,
    compute_word_error_rate,
    evaluate_physical_dataset,
    evaluate_sample,
    validate_benchmark_dataset,
)
from app.extraction.models import ExtractedNutrientCandidate


class MockTestAdapter(BaseOcrAdapter):
    """Controllable mock OCR adapter for testing the benchmark runner."""

    def __init__(self, raw_text: str, confidence: float = 95.0, should_fail: bool = False):
        self.raw_text = raw_text
        self.confidence = confidence
        self.should_fail = should_fail

    def extract_text(self, image_bytes: bytes) -> OcrEngineOutput:
        if self.should_fail:
            raise OcrEngineError(code="TEST_FAILURE", message="Simulated engine failure")
        return OcrEngineOutput(raw_text=self.raw_text, confidence=self.confidence)


# ==============================================================================
# 1. NUMERIC MATCHES & FIELD-SPECIFIC TOLERANCES
# ==============================================================================
def test_exact_numeric_matches() -> None:
    """Exact numeric match requires difference <= 0.001."""
    cand = ExtractedNutrientCandidate(
        field_name="protein_g",
        raw_text="Protein: 8.5g",
        value=8.5,
        unit="g",
        column="per_100g",
    )
    res = compare_nutrient_field(
        field_name="protein_g",
        gt_value=8.5,
        gt_unit="g",
        candidate=cand,
        declaration_basis="per_100g",
    )
    assert res.is_declared_in_gt is True
    assert res.is_predicted is True
    assert res.is_exact_match is True
    assert res.is_tolerance_match is True
    assert res.absolute_error == 0.0
    assert res.relative_error == 0.0
    assert res.is_omission is False
    assert res.is_unexpected is False


def test_decimal_mismatches_within_and_exceeding_tolerance() -> None:
    """
    Field-specific tolerances:
    Protein has 0.2g tolerance.
    Trans fat has 0.05g strict tolerance.
    """
    # Protein: 8.5g GT vs 8.6g pred (diff 0.1g <= 0.2g tolerance)
    cand_within = ExtractedNutrientCandidate(
        field_name="protein_g",
        raw_text="Protein: 8.6g",
        value=8.6,
        unit="g",
        column="per_100g",
    )
    res_within = compare_nutrient_field(
        field_name="protein_g",
        gt_value=8.5,
        gt_unit="g",
        candidate=cand_within,
        declaration_basis="per_100g",
    )
    assert res_within.is_exact_match is False
    assert res_within.is_tolerance_match is True
    assert res_within.absolute_error == 0.1

    # Protein: 8.5g GT vs 9.0g pred (diff 0.5g > 0.2g tolerance)
    cand_exceed = ExtractedNutrientCandidate(
        field_name="protein_g",
        raw_text="Protein: 9.0g",
        value=9.0,
        unit="g",
        column="per_100g",
    )
    res_exceed = compare_nutrient_field(
        field_name="protein_g",
        gt_value=8.5,
        gt_unit="g",
        candidate=cand_exceed,
        declaration_basis="per_100g",
    )
    assert res_exceed.is_exact_match is False
    assert res_exceed.is_tolerance_match is False
    assert res_exceed.absolute_error == 0.5

    # Trans fat: 0.05g GT vs 0.15g pred (diff 0.10g > 0.05g tolerance)
    cand_trans = ExtractedNutrientCandidate(
        field_name="trans_fat_g",
        raw_text="Trans fat: 0.15g",
        value=0.15,
        unit="g",
        column="per_100g",
    )
    res_trans = compare_nutrient_field(
        field_name="trans_fat_g",
        gt_value=0.05,
        gt_unit="g",
        candidate=cand_trans,
        declaration_basis="per_100g",
    )
    assert res_trans.is_exact_match is False
    assert res_trans.is_tolerance_match is False


def test_sodium_and_energy_tolerances() -> None:
    """
    Sodium allows 5.0mg or 2% relative tolerance.
    Energy allows 1.0 kcal or 1% relative tolerance.
    """
    # Sodium: 780.0 mg GT vs 784.0 mg pred (diff 4.0 mg <= 5.0 mg tolerance)
    cand_na = ExtractedNutrientCandidate(
        field_name="sodium_mg",
        raw_text="Sodium: 784mg",
        value=784.0,
        unit="mg",
        column="per_100g",
    )
    res_na = compare_nutrient_field(
        field_name="sodium_mg",
        gt_value=780.0,
        gt_unit="mg",
        candidate=cand_na,
        declaration_basis="per_100g",
    )
    assert res_na.is_tolerance_match is True
    assert res_na.absolute_error == 4.0

    # Energy: 450.0 kcal GT vs 454.0 kcal pred (diff 4.0 kcal <= 4.5 kcal (1% of 450))
    cand_energy = ExtractedNutrientCandidate(
        field_name="energy_kcal",
        raw_text="Energy: 454 kcal",
        value=454.0,
        unit="kcal",
        column="per_100g",
    )
    res_energy = compare_nutrient_field(
        field_name="energy_kcal",
        gt_value=450.0,
        gt_unit="kcal",
        candidate=cand_energy,
        declaration_basis="per_100g",
    )
    assert res_energy.is_tolerance_match is True


# ==============================================================================
# 2. UNIT CONVERSIONS & BASIS MISMATCHES
# ==============================================================================
def test_unit_conversion_and_incompatible_unit_rejection() -> None:
    """
    Converts compatible units (e.g. 0.78g sodium -> 780.0mg sodium).
    Rejects completely incompatible units (e.g. kcal for protein).
    """
    # Compatible: Pred 0.78 g sodium matches GT 780.0 mg sodium
    cand_na = ExtractedNutrientCandidate(
        field_name="sodium_mg",
        raw_text="Sodium: 0.78g",
        value=0.78,
        unit="g",
        column="per_100g",
    )
    res_na = compare_nutrient_field(
        field_name="sodium_mg",
        gt_value=780.0,
        gt_unit="mg",
        candidate=cand_na,
        declaration_basis="per_100g",
    )
    assert res_na.unit_mismatch is False
    assert res_na.predicted_value == 780.0
    assert res_na.is_exact_match is True

    # Incompatible: Pred kcal for protein
    cand_incompat = ExtractedNutrientCandidate(
        field_name="protein_g",
        raw_text="Protein: 15kcal",
        value=15.0,
        unit="kcal",
        column="per_100g",
    )
    res_incompat = compare_nutrient_field(
        field_name="protein_g",
        gt_value=15.0,
        gt_unit="g",
        candidate=cand_incompat,
        declaration_basis="per_100g",
    )
    assert res_incompat.unit_mismatch is True
    assert res_incompat.is_exact_match is False
    assert res_incompat.is_tolerance_match is False


def test_serving_basis_mismatch() -> None:
    """Detects when predicted column basis conflicts with GT declaration basis."""
    cand = ExtractedNutrientCandidate(
        field_name="carbohydrates_g",
        raw_text="Carbohydrates per serve: 15.0g",
        value=15.0,
        unit="g",
        column="per_serving",  # Explicitly per serving
    )
    res = compare_nutrient_field(
        field_name="carbohydrates_g",
        gt_value=75.0,
        gt_unit="g",
        candidate=cand,
        declaration_basis="per_100g",  # Expecting per 100g
    )
    assert res.basis_mismatch is True
    assert res.is_tolerance_match is False


# ==============================================================================
# 3. OMISSIONS, UNEXPECTED PREDICTIONS & UNREADABLE FIELDS
# ==============================================================================
def test_missing_predictions_omission_rate() -> None:
    """Field declared in GT but missing in OCR prediction is an omission."""
    res = compare_nutrient_field(
        field_name="dietary_fiber_g",
        gt_value=4.5,
        gt_unit="g",
        candidate=None,
        declaration_basis="per_100g",
    )
    assert res.is_declared_in_gt is True
    assert res.is_predicted is False
    assert res.is_omission is True
    assert res.is_unexpected is False
    assert res.is_exact_match is False
    assert res.is_tolerance_match is False


def test_unexpected_predictions_hallucination_rate() -> None:
    """Field undeclared/unreadable in GT (None) but predicted by OCR is unexpected."""
    cand = ExtractedNutrientCandidate(
        field_name="cholesterol_mg",
        raw_text="Cholesterol: 10mg",
        value=10.0,
        unit="mg",
        column="per_100g",
    )
    res = compare_nutrient_field(
        field_name="cholesterol_mg",
        gt_value=None,  # Undeclared on physical packaging
        gt_unit="mg",
        candidate=cand,
        declaration_basis="per_100g",
    )
    assert res.is_declared_in_gt is False
    assert res.is_predicted is True
    assert res.is_omission is False
    assert res.is_unexpected is True
    assert res.is_exact_match is False
    assert res.is_tolerance_match is False


def test_unreadable_ground_truth_fields_properly_excluded() -> None:
    """When GT is None and candidate is None, neither omission nor unexpected."""
    res = compare_nutrient_field(
        field_name="cholesterol_mg",
        gt_value=None,
        gt_unit="mg",
        candidate=None,
        declaration_basis="per_100g",
    )
    assert res.is_declared_in_gt is False
    assert res.is_predicted is False
    assert res.is_omission is False
    assert res.is_unexpected is False


# ==============================================================================
# 4. PROCESSING FAILURES & ERROR HANDLING
# ==============================================================================
def test_failed_image_processing_handling() -> None:
    """Engine failures are caught gracefully and recorded without crashing."""
    sample = {
        "sample_id": "TEST-FAIL-01",
        "product_name": "Test Fail",
        "category": "Biscuits & Cookies",
        "packaging_format": "wrapper",
        "capture_metadata": {"lighting_condition": "L1"},
        "ground_truth_nutrition": {
            "declaration_basis": "per_100g",
            "nutrients": {"protein_g": 5.0},
        },
    }
    adapter = MockTestAdapter(raw_text="", should_fail=True)
    res = evaluate_sample(
        sample_data=sample,
        preloaded_image_bytes=b"fake_image_bytes_12345",
        adapter=adapter,
    )
    assert res.image_found is True
    assert res.processing_success is False
    assert "Simulated engine failure" in (res.processing_error or "")
    assert res.sample_passed is False


# ==============================================================================
# 5. DATASET VALIDATION (EMPTY, DUPLICATES, MALFORMED)
# ==============================================================================
def test_empty_datasets_detection() -> None:
    """Empty sample list is caught fail-closed."""
    is_valid, errors = validate_benchmark_dataset([])
    assert is_valid is False
    assert any("empty" in e.lower() for e in errors)


def test_duplicate_sample_ids_detection() -> None:
    """Duplicate sample IDs in dataset are detected."""
    samples = [
        {"sample_id": "RFL-001", "ground_truth_nutrition": {"nutrients": {}}},
        {"sample_id": "RFL-001", "ground_truth_nutrition": {"nutrients": {}}},
    ]
    is_valid, errors = validate_benchmark_dataset(samples)
    assert is_valid is False
    assert any("duplicate" in e.lower() for e in errors)


def test_invalid_dataset_records_handling() -> None:
    """Missing required structure in sample is caught."""
    samples = [
        {"sample_id": "RFL-001"},  # missing ground_truth_nutrition
    ]
    is_valid, errors = validate_benchmark_dataset(samples)
    assert is_valid is False
    assert any("missing or invalid 'ground_truth_nutrition'" in e.lower() for e in errors)


# ==============================================================================
# 6. TEXT ACCURACY METRICS (CER & WER)
# ==============================================================================
def test_character_and_word_error_rates() -> None:
    """Verifies Levenshtein CER and WER calculation."""
    gt = "Refined Wheat Flour, Sugar, Palm Oil"
    # Identical
    assert compute_character_error_rate(gt, gt) == 0.0
    assert compute_word_error_rate(gt, gt) == 0.0
    assert compute_ingredient_completeness(gt, gt) == 1.0

    # Minor typo: 'Flour' -> 'Floor' (1 char substitution out of 37 chars)
    hyp_typo = "Refined Wheat Floor, Sugar, Palm Oil"
    cer = compute_character_error_rate(gt, hyp_typo)
    assert 0.0 < cer < 0.05
    wer = compute_word_error_rate(gt, hyp_typo)
    assert 0.0 < wer < 0.25

    # Completely different
    cer_diff = compute_character_error_rate("Water", "Milk")
    assert cer_diff > 0.5


# ==============================================================================
# 7. DETERMINISTIC REPEATED RUNS
# ==============================================================================
def test_deterministic_repeated_runs() -> None:
    """Running evaluation twice on identical input produces identical outcomes."""
    sample = {
        "sample_id": "TEST-DET-01",
        "product_name": "Deterministic Snack",
        "category": "Savory Snacks & Extruded Namkeen",
        "packaging_format": "pouch",
        "capture_metadata": {"lighting_condition": "L1", "camera_angle": "A1"},
        "ground_truth_nutrition": {
            "declaration_basis": "per_100g",
            "serving_size": 100.0,
            "serving_unit": "g",
            "food_form": "solid",
            "nutrients": {
                "energy_kcal": 500.0,
                "protein_g": 8.0,
                "carbohydrates_g": 60.0,
                "total_fat_g": 25.0,
                "sodium_mg": 400.0,
            },
        },
        "ground_truth_ingredients_text": "Potato, Edible Vegetable Oil, Salt.",
    }
    raw_ocr = (
        "NUTRITIONAL INFORMATION per 100g\n"
        "Energy: 500 kcal\n"
        "Protein: 8.0 g\n"
        "Carbohydrate: 60.0 g\n"
        "Total Fat: 25.0 g\n"
        "Sodium: 400 mg\n"
        "Ingredients: Potato, Edible Vegetable Oil, Salt."
    )
    adapter = MockTestAdapter(raw_text=raw_ocr)
    dummy_bytes = b"deterministic_image_payload_bytes"

    run_1 = evaluate_sample(sample_data=sample, preloaded_image_bytes=dummy_bytes, adapter=adapter)
    run_2 = evaluate_sample(sample_data=sample, preloaded_image_bytes=dummy_bytes, adapter=adapter)

    assert run_1.sample_passed == run_2.sample_passed
    assert run_1.cer == run_2.cer
    assert run_1.wer == run_2.wer
    assert len(run_1.nutrient_comparisons) == len(run_2.nutrient_comparisons)
    for field_name in run_1.nutrient_comparisons:
        c1 = run_1.nutrient_comparisons[field_name]
        c2 = run_2.nutrient_comparisons[field_name]
        assert c1.is_exact_match == c2.is_exact_match
        assert c1.is_tolerance_match == c2.is_tolerance_match
        assert c1.absolute_error == c2.absolute_error


# ==============================================================================
# 8. HONEST UNMEASURED REPORTING WHEN PHYSICAL PHOTOS ARE ABSENT
# ==============================================================================
def test_unmeasured_reporting_when_physical_photos_absent(tmp_path: Path) -> None:
    """When images_dir is empty or missing, returns status UNMEASURED with 0 evaluated."""
    dataset_file = tmp_path / "samples.json"
    dataset_json = (
        '{"version": "1.0", "samples": [{"sample_id": "RFL-001", '
        '"ground_truth_nutrition": {"nutrients": {}}}]}'
    )
    dataset_file.write_text(dataset_json, encoding="utf-8")
    empty_images_dir = tmp_path / "images"
    empty_images_dir.mkdir()

    summary = evaluate_physical_dataset(dataset_path=dataset_file, images_dir=empty_images_dir)
    assert summary.status == "UNMEASURED"
    assert summary.samples_evaluated == 0
    assert summary.images_bundled_on_disk == 0
    assert summary.field_exact_matches == 0
    assert "UNMEASURED" in summary.disclaimer
