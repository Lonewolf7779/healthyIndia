"""
Validation Suite for the OCR and Deterministic Parsing Benchmark Runner.

Verifies that the benchmark runner itself is not a rubber stamp:
1. Detects deliberately introduced calculation errors and flags FAIL.
2. Detects deliberately introduced parser / nutrient association errors.
3. Detects false acceptances and false rejections in quality gate tests.
4. Never hardcodes PASS when metric thresholds are not met.
"""

from unittest.mock import patch

from app.extraction.models import ExtractedNutrientCandidate, OcrExtractionResult
from scripts.run_ocr_benchmark import (
    evaluate_calculation_correctness,
    evaluate_nutrient_association,
    evaluate_parser_correctness,
    evaluate_quality_gates,
)


def test_benchmark_detects_deliberate_calculation_error() -> None:
    """
    Mutates calculate output to introduce an erroneous protein value.
    The benchmark MUST detect the error, record error_count > 0, and drop success rate.
    """
    real_evaluate = evaluate_calculation_correctness()
    assert real_evaluate.status == "PASS"
    assert real_evaluate.error_count == 0

    from dataclasses import replace

    # Introduce deliberate mutation: alter analyze_nutrition to return incorrect per_100 numbers
    def buggy_analyze(input_data):
        from app.nutrition.calculator import analyze_nutrition

        res = analyze_nutrition(input_data)
        corrupted_per_100 = dict(res.per_100)
        corrupted_per_100["protein_g"] = 999.99
        return replace(res, per_100=corrupted_per_100)

    with patch("scripts.run_ocr_benchmark.analyze_nutrition", side_effect=buggy_analyze):
        mutated_metric = evaluate_calculation_correctness()
        assert mutated_metric.error_count > 0
        assert mutated_metric.correct_count < mutated_metric.evaluated_count
        assert mutated_metric.success_rate < 100.0


def test_benchmark_detects_deliberate_association_mismatch() -> None:
    """
    Mutates parser output so candidate values diverge from expected values.
    The benchmark MUST catch the error and not claim 100%.
    """
    fixtures = [
        {
            "raw_text": "Protein: 10g\nFat: 5g",
            "expected_parser": {
                "protein_g": 10.0,
                "total_fat_g": 5.0,
            },
        }
    ]

    # Deliberately return wrong parsed value
    def buggy_parse(raw_text):
        cand = ExtractedNutrientCandidate(
            field_name="protein_g",
            raw_text="Protein: 10g",
            value=2.0,  # Deliberately incorrect value (expected 10.0)
            unit="g",
        )
        return OcrExtractionResult(
            raw_text=raw_text,
            column_basis_detected="single_column",
            nutrition_lines=[],
            ingredients_text=None,
            nutrient_candidates={"protein_g": cand},
            per_100_candidates={},
            per_serving_candidates={},
            serving_size_candidate=None,
            serving_unit_candidate="g",
            overall_confidence=90.0,
            warnings=[],
            verification_required=True,
        )

    with patch("scripts.run_ocr_benchmark.parse_ocr_text", side_effect=buggy_parse):
        metric = evaluate_nutrient_association(fixtures)
        assert metric.error_count > 0
        assert metric.status == "FAIL"
        assert metric.success_rate < metric.threshold


def test_benchmark_detects_false_acceptance_in_quality_gates() -> None:
    """
    Mutates assess_image_quality to falsely accept a severe blur image.
    The benchmark MUST record false_acceptances > 0.
    """

    # Deliberately mock assess_image_quality to return gate_outcome='ACCEPT' on all images
    class FalselyAcceptingAssessment:
        gate_outcome = "ACCEPT"
        grade = "good"
        is_acceptable = True
        warnings = []

    with patch(
        "scripts.run_ocr_benchmark.assess_image_quality", return_value=FalselyAcceptingAssessment()
    ):
        metric = evaluate_quality_gates()
        # Several images were intended to be REJECT or WARN
        assert metric.details.get("false_acceptances", 0) > 0
        assert metric.status == "FAIL"
        assert metric.success_rate < 100.0


def test_benchmark_status_fails_when_threshold_unmet() -> None:
    """
    Verifies that the benchmark status is dynamically computed and never hardcoded to PASS.
    """
    fixtures = [{"raw_text": "Invalid text that yields no nutrients", "expected_parser": {}}]
    # Mock parse_ocr_text to return empty candidates
    with patch(
        "scripts.run_ocr_benchmark.parse_ocr_text",
        return_value=OcrExtractionResult(
            raw_text="empty",
            column_basis_detected="single_column",
            nutrition_lines=[],
            ingredients_text=None,
            nutrient_candidates={},  # Empty candidates triggers failure
            per_100_candidates={},
            per_serving_candidates={},
            serving_size_candidate=None,
            serving_unit_candidate="g",
            overall_confidence=0.0,
            warnings=[],
            verification_required=True,
        ),
    ):
        metric = evaluate_parser_correctness(fixtures)
        assert metric.success_rate == 0.0
        assert metric.status == "FAIL"
