"""
Validation Suite for the OCR and Deterministic Parsing Benchmark Runner.

Verifies that the benchmark runner itself is not a rubber stamp:
1. Detects deliberately introduced calculation errors and flags FAIL.
2. Detects deliberately introduced parser / nutrient association errors.
3. Detects false acceptances and false rejections in quality gate tests.
4. Never hardcodes PASS when metric thresholds are not met.
"""

from pathlib import Path
from unittest.mock import patch

from app.extraction.adapter import BaseOcrAdapter, MockOcrAdapter, OcrEngineOutput
from app.extraction.models import ExtractedNutrientCandidate, OcrExtractionResult
from scripts.run_ocr_benchmark import (
    BenchmarkMetric,
    BenchmarkSuiteResult,
    evaluate_actual_ocr_recognition,
    evaluate_calculation_correctness,
    evaluate_mock_adapter_integration,
    evaluate_nutrient_association,
    evaluate_parser_correctness,
    evaluate_quality_gates,
    run_benchmark,
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


def test_mock_ocr_result_cannot_increase_real_ocr_score() -> None:
    """
    Proves that supplying a MockOcrAdapter cannot increase or contribute to the
    real OCR recognition accuracy score. The benchmark MUST flag BLOCKED and
    return None success rate.
    """
    mock_adapter = MockOcrAdapter(
        mock_text=(
            "Energy: 140 kcal\nProtein: 2.5 g\nTotal Fat: 5.0 g\n"
            "Carbohydrates: 22.0 g\nSodium: 150 mg"
        ),
        mock_confidence=100.0,
    )
    metric, is_available = evaluate_actual_ocr_recognition(adapter=mock_adapter)

    # Real OCR is NOT available when a mock is passed
    assert is_available is False
    assert metric.status == "BLOCKED"
    assert metric.status != "PASS"
    assert metric.evaluated_count == 0
    assert metric.correct_count == 0
    assert metric.success_rate is None
    assert "Mock OCR adapter was supplied" in metric.details.get("blocked_reason", "")

    # Mock plumbing is evaluated separately and does not contribute to OCR recognition accuracy
    mock_plumbing = evaluate_mock_adapter_integration()
    assert mock_plumbing.status == "PASS"
    assert mock_plumbing.details.get("contributes_to_ocr_accuracy") is False


def test_missing_tesseract_cannot_produce_ocr_pass() -> None:
    """
    Proves that when the Tesseract binary is missing from the system PATH,
    the actual OCR recognition benchmark cannot report PASS and must report BLOCKED.
    """
    with patch("scripts.run_ocr_benchmark.TesseractOcrAdapter.is_available", return_value=False):
        metric, is_available = evaluate_actual_ocr_recognition()
        assert is_available is False
        assert metric.status == "BLOCKED"
        assert metric.status != "PASS"
        assert metric.success_rate is None
        assert metric.correct_count == 0
        assert metric.evaluated_count == 0
        assert "Tesseract binary not found" in metric.details.get("blocked_reason", "")


def test_deliberately_incorrect_ocr_causes_measurable_failure() -> None:
    """
    Proves that if an OCR engine returns corrupted or mismatched text,
    the benchmark catches the mismatch, records error counts, and flags FAIL.
    """

    class BrokenOcrAdapter(BaseOcrAdapter):
        def is_available(self) -> bool:
            return True

        def extract_text(self, image_bytes: bytes) -> OcrEngineOutput:
            return OcrEngineOutput(
                raw_text="GARBAGE CORRUPTED CHARACTERS 9999 ??? !!!",
                confidence=15.0,
            )

    metric, is_available = evaluate_actual_ocr_recognition(adapter=BrokenOcrAdapter())
    assert is_available is True
    assert metric.status == "FAIL"
    assert metric.status != "PASS"
    assert metric.error_count == metric.evaluated_count
    assert metric.correct_count == 0
    assert metric.success_rate == 0.0
    assert metric.details.get("exact_matches") == 0


def test_ocr_failure_causes_overall_benchmark_to_fail_or_remain_blocked() -> None:
    """
    Proves that an OCR metric failure or blocked state prevents BenchmarkSuiteResult
    from silently reporting all_passed=True.
    """
    passing_metric = BenchmarkMetric(
        name="Passing Test",
        evaluated_count=10,
        correct_count=10,
        error_count=0,
        success_rate=100.0,
        threshold=90.0,
        status="PASS",
    )

    # 1. OCR metric is BLOCKED
    blocked_ocr = BenchmarkMetric(
        name="Actual OCR",
        evaluated_count=0,
        correct_count=0,
        error_count=0,
        success_rate=None,
        threshold=85.0,
        status="BLOCKED",
    )
    suite_blocked = BenchmarkSuiteResult(
        parser_metric=passing_metric,
        mock_adapter_metric=passing_metric,
        actual_ocr_metric=blocked_ocr,
        association_metric=passing_metric,
        serving_metric=passing_metric,
        calculation_metric=passing_metric,
        quality_gate_metric=passing_metric,
        generated_at="2026-10-18T00:00:00Z",
        tesseract_available=False,
    )
    assert suite_blocked.all_passed is False
    assert suite_blocked.overall_status == "BLOCKED"

    # 2. OCR metric is FAIL
    failing_ocr = BenchmarkMetric(
        name="Actual OCR",
        evaluated_count=5,
        correct_count=1,
        error_count=4,
        success_rate=20.0,
        threshold=85.0,
        status="FAIL",
    )
    suite_failed = BenchmarkSuiteResult(
        parser_metric=passing_metric,
        mock_adapter_metric=passing_metric,
        actual_ocr_metric=failing_ocr,
        association_metric=passing_metric,
        serving_metric=passing_metric,
        calculation_metric=passing_metric,
        quality_gate_metric=passing_metric,
        generated_at="2026-10-18T00:00:00Z",
        tesseract_available=True,
    )
    assert suite_failed.all_passed is False
    assert suite_failed.overall_status == "FAIL"


def test_failed_required_metric_cannot_be_omitted_from_pass_logic() -> None:
    """
    Exhaustively verifies that every single required metric is included in the
    overall pass logic. Fails each metric one by one and proves all_passed becomes False.
    """

    def make_metric(status: str) -> BenchmarkMetric:
        return BenchmarkMetric(
            name="Metric",
            evaluated_count=5,
            correct_count=5 if status == "PASS" else 0,
            error_count=0 if status == "PASS" else 5,
            success_rate=100.0 if status == "PASS" else (None if status == "BLOCKED" else 0.0),
            threshold=90.0,
            status=status,
        )

    required_keys = [
        "parser_metric",
        "mock_adapter_metric",
        "actual_ocr_metric",
        "association_metric",
        "serving_metric",
        "calculation_metric",
        "quality_gate_metric",
    ]

    # Baseline: all pass
    base_kwargs = {k: make_metric("PASS") for k in required_keys}
    base_suite = BenchmarkSuiteResult(
        **base_kwargs,
        generated_at="2026-10-18T00:00:00Z",
        tesseract_available=True,
    )
    assert base_suite.all_passed is True
    assert base_suite.overall_status == "PASS"

    # Now verify that omitting/failing ANY single required metric causes all_passed=False
    for key in required_keys:
        # Test FAIL state
        fail_kwargs = dict(base_kwargs)
        fail_kwargs[key] = make_metric("FAIL")
        suite_fail = BenchmarkSuiteResult(
            **fail_kwargs,
            generated_at="2026-10-18T00:00:00Z",
            tesseract_available=True,
        )
        assert suite_fail.all_passed is False, (
            f"Metric '{key}' was omitted from pass logic on FAIL!"
        )
        assert suite_fail.overall_status == "FAIL"

        # Test BLOCKED state
        blocked_kwargs = dict(base_kwargs)
        blocked_kwargs[key] = make_metric("BLOCKED")
        suite_blocked = BenchmarkSuiteResult(
            **blocked_kwargs,
            generated_at="2026-10-18T00:00:00Z",
            tesseract_available=True,
        )
        assert suite_blocked.all_passed is False, (
            f"Metric '{key}' was omitted from pass logic on BLOCKED!"
        )
        assert suite_blocked.overall_status == "BLOCKED"

        # Test NOT RUN state
        notrun_kwargs = dict(base_kwargs)
        notrun_kwargs[key] = make_metric("NOT RUN")
        suite_notrun = BenchmarkSuiteResult(
            **notrun_kwargs,
            generated_at="2026-10-18T00:00:00Z",
            tesseract_available=True,
        )
        assert suite_notrun.all_passed is False, (
            f"Metric '{key}' was omitted from pass logic on NOT RUN!"
        )
        assert suite_notrun.overall_status == "NOT RUN"


def test_report_accurately_reflects_executed_metrics() -> None:
    """
    Verifies that the generated markdown report accurately reflects the metrics
    actually executed, distinguishes mocks from real OCR, and explicitly notes
    unmeasured categories.
    """
    # 1. Test blocked environment report
    with patch("scripts.run_ocr_benchmark.TesseractOcrAdapter.is_available", return_value=False):
        suite_blocked = run_benchmark()
        assert suite_blocked.overall_status == "BLOCKED"

        report_path = Path(__file__).resolve().parents[4] / "docs" / "OCR_BENCHMARK_REPORT.md"
        content = report_path.read_text(encoding="utf-8")

        assert "Overall Suite Status: **BLOCKED**" in content
        assert "Actual OCR Recognition Benchmark is BLOCKED" in content
        assert "Rendered-Image OCR Recognition (Tesseract)" in content
        assert "OCR Adapter Plumbing (Mock Integration)" in content
        assert "Real-World Packaging Photographs" in content
        assert "N/A (Unmeasured)" in content
        assert "N/A (Blocked)" in content

    # 2. Re-run normal benchmark and verify report reflects actual state
    suite = run_benchmark()
    content = report_path.read_text(encoding="utf-8")
    assert f"Overall Suite Status: **{suite.overall_status}**" in content
    assert "OCR Adapter Plumbing (Mock Integration)" in content
    assert "Real-World Physical Camera Accuracy Remains Unmeasured" in content
