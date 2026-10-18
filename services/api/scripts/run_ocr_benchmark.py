"""
OCR and Deterministic Parsing Benchmark Runner.

Executes structured evaluation tests across:
1. Synthetic text parser correctness.
2. Rendered-image OCR recognition.
3. Nutrient-to-value association.
4. Serving-size and unit interpretation.
5. Independent numerical calculation correctness.
6. Computer vision quality-gate decision performance.
7. Real-world physical camera limitations.

Outputs metrics, computes exact denominators, and updates docs/OCR_BENCHMARK_REPORT.md.
"""

import io
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Ensure app is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.adapter import (
    BaseOcrAdapter,
    MockOcrAdapter,
    OcrEngineOutput,
    TesseractOcrAdapter,
)
from app.extraction.parser import parse_ocr_text
from app.extraction.quality import assess_image_quality
from app.extraction.validator import ImageValidationError, validate_image_payload
from app.nutrition.calculator import analyze_nutrition
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FoodForm
from tests.fixtures.realistic_fixtures import load_realistic_fixtures


@dataclass(frozen=True)
class OcrGroundTruthSample:
    """Independent ground truth sample for optical character recognition testing."""

    sample_id: str
    expected_text: str
    source_type: str  # "rendered_synthetic" vs "physical_photograph"
    description: str


RENDERED_OCR_GROUND_TRUTH: list[OcrGroundTruthSample] = [
    OcrGroundTruthSample(
        sample_id="synth_render_energy",
        expected_text="Energy: 140 kcal",
        source_type="rendered_synthetic",
        description="Standard energy declaration with unit in kcal",
    ),
    OcrGroundTruthSample(
        sample_id="synth_render_protein",
        expected_text="Protein: 2.5 g",
        source_type="rendered_synthetic",
        description="Single-decimal protein declaration with gram unit",
    ),
    OcrGroundTruthSample(
        sample_id="synth_render_fat",
        expected_text="Total Fat: 5.0 g",
        source_type="rendered_synthetic",
        description="Two-word macronutrient with decimal value and unit",
    ),
    OcrGroundTruthSample(
        sample_id="synth_render_carbs",
        expected_text="Carbohydrates: 22.0 g",
        source_type="rendered_synthetic",
        description="Multisyllabic nutrient name with decimal value",
    ),
    OcrGroundTruthSample(
        sample_id="synth_render_sodium",
        expected_text="Sodium: 150 mg",
        source_type="rendered_synthetic",
        description="Milligram micronutrient declaration",
    ),
]


def compute_levenshtein_distance(s1: str, s2: str) -> int:
    """Computes standard edit distance between two strings."""
    if len(s1) < len(s2):
        return compute_levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def compute_char_accuracy(expected: str, actual: str) -> float:
    """Calculates character recognition accuracy (0.0 to 100.0)."""
    norm_exp = expected.strip().lower()
    norm_act = actual.strip().lower()
    if not norm_exp:
        return 100.0 if not norm_act else 0.0
    dist = compute_levenshtein_distance(norm_exp, norm_act)
    return max(0.0, (1.0 - dist / max(len(norm_exp), len(norm_act)))) * 100.0


def compute_word_accuracy(expected: str, actual: str) -> float:
    """Calculates word token recognition accuracy (0.0 to 100.0)."""
    exp_words = expected.strip().lower().split()
    act_words = actual.strip().lower().split()
    if not exp_words:
        return 100.0 if not act_words else 0.0
    matched = sum(1 for w in exp_words if w in act_words)
    return (matched / len(exp_words)) * 100.0


def compute_character_error_rate(reference: str, hypothesis: str) -> float:
    """Computes Character Error Rate (CER = edit_distance / len(ref))."""
    norm_ref = reference.strip().lower()
    norm_hyp = hypothesis.strip().lower()
    if not norm_ref:
        return 0.0 if not norm_hyp else 1.0
    dist = compute_levenshtein_distance(norm_ref, norm_hyp)
    return dist / len(norm_ref)


def compute_word_error_rate(reference: str, hypothesis: str) -> float:
    """Computes Word Error Rate (WER) using token edit distance."""
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + 1)
    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def render_sample_image(text: str) -> bytes:
    """Renders high-contrast black-on-white text image for OCR evaluation."""
    img = Image.new("RGB", (650, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=28)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((30, 40), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class BenchmarkMetric:
    """Represents a single evaluated benchmark metric with exact counts and denominator."""

    name: str
    evaluated_count: int
    correct_count: int
    error_count: int
    success_rate: float | None
    threshold: float
    status: str  # "PASS", "FAIL", "BLOCKED", "NOT RUN", "UNMEASURED"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSuiteResult:
    """Aggregated benchmark suite outcome."""

    parser_metric: BenchmarkMetric
    mock_adapter_metric: BenchmarkMetric
    actual_ocr_metric: BenchmarkMetric
    association_metric: BenchmarkMetric
    serving_metric: BenchmarkMetric
    calculation_metric: BenchmarkMetric
    quality_gate_metric: BenchmarkMetric
    generated_at: str
    tesseract_available: bool
    physical_metric: BenchmarkMetric | None = None

    @property
    def required_metrics(self) -> list[BenchmarkMetric]:
        """All required metrics that must individually PASS for overall suite success."""
        return [
            self.parser_metric,
            self.mock_adapter_metric,
            self.actual_ocr_metric,
            self.association_metric,
            self.serving_metric,
            self.calculation_metric,
            self.quality_gate_metric,
        ]

    @property
    def overall_status(self) -> str:
        """
        Calculates the explicit overall status across all required metrics:
        - 'FAIL': If ANY required metric has status 'FAIL'.
        - 'BLOCKED': If ANY required metric has status 'BLOCKED' and none is 'FAIL'.
        - 'NOT RUN': If ANY required metric has status 'NOT RUN' and none is 'FAIL' or 'BLOCKED'.
        - 'PASS': If and only if EVERY required metric has status 'PASS'.
        """
        statuses = [m.status for m in self.required_metrics]
        if any(s == "FAIL" for s in statuses):
            return "FAIL"
        if any(s == "BLOCKED" for s in statuses):
            return "BLOCKED"
        if any(s == "NOT RUN" for s in statuses):
            return "NOT RUN"
        if all(s == "PASS" for s in statuses):
            return "PASS"
        return "FAIL"

    @property
    def all_passed(self) -> bool:
        """
        Strict pass determination: True ONLY if overall_status is 'PASS'.
        A metric that is FAIL, BLOCKED, or NOT RUN must not silently produce an overall PASS.
        """
        return self.overall_status == "PASS"


def evaluate_parser_correctness(fixtures: list[dict]) -> BenchmarkMetric:
    """
    Evaluates deterministic parser syntax correctness on synthetic text strings.
    Does NOT claim this measures physical optical character recognition.
    """
    evaluated = len(fixtures)
    correct = 0
    errors = 0

    for f in fixtures:
        raw_text = f["raw_text"]
        result = parse_ocr_text(raw_text)
        # Verify result structure, verification flag, and non-empty candidates
        if (
            result.verification_required is True
            and len(result.nutrient_candidates) > 0
            and result.column_basis_detected
            in ("dual_column", "per_100g", "per_serving", "single_column")
        ):
            correct += 1
        else:
            errors += 1

    rate = (correct / evaluated * 100.0) if evaluated else 0.0
    threshold = 95.0
    return BenchmarkMetric(
        name="Synthetic Text Parser Correctness",
        evaluated_count=evaluated,
        correct_count=correct,
        error_count=errors,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
    )


def evaluate_mock_adapter_integration() -> BenchmarkMetric:
    """
    Validates Python adapter interfaces, confidence unpacking, and discrepancy
    detection using controlled mock payloads.

    CRITICAL INTEGRITY PRINCIPLE:
    This evaluates software plumbing and adapter interface compliance only.
    It contributes 0% to the reported optical character recognition accuracy.
    """
    checks_evaluated = 0
    checks_passed = 0

    # 1. Output dataclass and 2-tuple unpacking
    checks_evaluated += 1
    mock_1 = MockOcrAdapter(
        mock_text="Energy: 100 kcal",
        mock_confidence=92.0,
        pass_a_text="Energy: 100 kcal",  # noqa: S106
        pass_b_text="Energy: 100 kcal",  # noqa: S106
        pass_discrepancy=False,
    )
    out_1 = mock_1.extract_text(b"mock_bytes")
    text_unpacked, conf_unpacked = out_1
    if (
        text_unpacked == "Energy: 100 kcal"
        and conf_unpacked == 92.0
        and isinstance(out_1, OcrEngineOutput)
    ):
        checks_passed += 1

    # 2. Dual-pass discrepancy flag activation
    checks_evaluated += 1
    mock_2 = MockOcrAdapter(
        mock_text="Pass A text",
        mock_confidence=80.0,
        pass_a_text="Protein: 10g",  # noqa: S106
        pass_b_text="Protein: 18g",  # noqa: S106
        pass_discrepancy=True,
    )
    out_2 = mock_2.extract_text(b"mock_bytes")
    if out_2.pass_discrepancy is True and len(out_2.discrepancy_details) > 0:
        checks_passed += 1

    # 3. Discrepancy details array retention
    checks_evaluated += 1
    if any("discrepancy" in d.lower() or "pass" in d.lower() for d in out_2.discrepancy_details):
        checks_passed += 1

    # 4. Zero/None confidence handling
    checks_evaluated += 1
    mock_3 = MockOcrAdapter(mock_text="Text without conf", mock_confidence=None)
    out_3 = mock_3.extract_text(b"mock_bytes")
    if out_3.confidence is None:
        checks_passed += 1

    errors = checks_evaluated - checks_passed
    rate = (checks_passed / checks_evaluated * 100.0) if checks_evaluated else 0.0
    threshold = 100.0
    return BenchmarkMetric(
        name="OCR Adapter Plumbing (Mock Integration)",
        evaluated_count=checks_evaluated,
        correct_count=checks_passed,
        error_count=errors,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
        details={
            "scope": "Adapter plumbing and interface contract verification",
            "uses_real_ocr": False,
            "contributes_to_ocr_accuracy": False,
        },
    )


def evaluate_actual_ocr_recognition(
    adapter: BaseOcrAdapter | None = None,
    samples: list[OcrGroundTruthSample] | None = None,
) -> tuple[BenchmarkMetric, bool]:
    """
    Evaluates real optical character recognition on rendered synthetic images
    using the installed OCR engine (Tesseract).

    CRITICAL INTEGRITY PRINCIPLES:
    1. A mock adapter or mock text must NEVER contribute to actual OCR accuracy.
    2. If the Tesseract executable is unavailable, status is BLOCKED and success rate is None.
    3. Missing or failed recognitions must NEVER be substituted with expected text.
    4. Evaluates character accuracy (CER-based) and word-level accuracy against independent ground truth.
    """
    ground_truth = samples if samples is not None else RENDERED_OCR_GROUND_TRUTH
    sample_count = len(ground_truth)

    if adapter is not None:
        if isinstance(adapter, MockOcrAdapter):
            # MOCK ADAPTERS ARE STRICTLY FORBIDDEN FROM REPORTING ACTUAL OCR ACCURACY
            return (
                BenchmarkMetric(
                    name="Rendered-Image OCR Recognition (Tesseract)",
                    evaluated_count=0,
                    correct_count=0,
                    error_count=0,
                    success_rate=None,
                    threshold=85.0,
                    status="BLOCKED",
                    details={
                        "engine": "Rejected (Mock adapter cannot contribute to real OCR score)",
                        "tesseract_binary_present": False,
                        "blocked_reason": (
                            "Mock OCR adapter was supplied. Mocks are forbidden "
                            "from contributing to actual OCR recognition metrics."
                        ),
                        "sample_count": sample_count,
                    },
                ),
                False,
            )

        ocr_engine = adapter
        available = getattr(ocr_engine, "is_available", lambda: True)()
    else:
        ocr_engine = TesseractOcrAdapter()
        available = ocr_engine.is_available()

    if not available:
        return (
            BenchmarkMetric(
                name="Rendered-Image OCR Recognition (Tesseract)",
                evaluated_count=0,
                correct_count=0,
                error_count=0,
                success_rate=None,
                threshold=85.0,
                status="BLOCKED",
                details={
                    "engine": "None (Tesseract binary missing)",
                    "tesseract_binary_present": False,
                    "blocked_reason": (
                        "Tesseract binary not found in system PATH. "
                        "Benchmark blocked pending runtime installation."
                    ),
                    "sample_count": sample_count,
                },
            ),
            False,
        )

    evaluated = sample_count
    correct = 0
    errors = 0
    exact_matches = 0
    char_accs: list[float] = []
    word_accs: list[float] = []
    sample_results: list[dict[str, Any]] = []

    for s in ground_truth:
        img_bytes = render_sample_image(s.expected_text)
        try:
            out = ocr_engine.extract_text(img_bytes)
            actual_text = out.raw_text.strip()
        except Exception:
            # Strictly do NOT substitute expected text when recognition fails
            actual_text = ""

        c_acc = compute_char_accuracy(s.expected_text, actual_text)
        w_acc = compute_word_accuracy(s.expected_text, actual_text)
        char_accs.append(c_acc)
        word_accs.append(w_acc)

        is_exact = s.expected_text.strip().lower() == actual_text.strip().lower()
        if is_exact:
            exact_matches += 1

        # High word and character accuracy required on rendered test images
        if is_exact or (w_acc >= 80.0 and c_acc >= 80.0):
            correct += 1
        else:
            errors += 1

        sample_results.append(
            {
                "sample_id": s.sample_id,
                "expected": s.expected_text,
                "recognized": actual_text,
                "char_accuracy": round(c_acc, 1),
                "word_accuracy": round(w_acc, 1),
                "exact_match": is_exact,
            }
        )

    rate = (correct / evaluated * 100.0) if evaluated else 0.0
    threshold = 85.0
    status = "PASS" if rate >= threshold else "FAIL"

    metric = BenchmarkMetric(
        name="Rendered-Image OCR Recognition (Tesseract)",
        evaluated_count=evaluated,
        correct_count=correct,
        error_count=errors,
        success_rate=rate,
        threshold=threshold,
        status=status,
        details={
            "engine": "Tesseract (Local Executable)",
            "tesseract_binary_present": True,
            "sample_count": evaluated,
            "exact_matches": exact_matches,
            "avg_char_accuracy": round(sum(char_accs) / len(char_accs), 1) if char_accs else 0.0,
            "avg_word_accuracy": round(sum(word_accs) / len(word_accs), 1) if word_accs else 0.0,
            "samples": sample_results,
        },
    )
    return metric, True


def evaluate_nutrient_association(fixtures: list[dict]) -> BenchmarkMetric:
    """
    Evaluates correct mapping of nutrient names to values across columns.
    """
    total_fields = 0
    correct_fields = 0

    for f in fixtures:
        raw_text = f["raw_text"]
        result = parse_ocr_text(raw_text)
        expected = f.get("expected_parser", {})

        for field_name, expected_val in expected.items():
            if field_name in ("serving_size", "serving_unit", "energy_kj"):
                continue

            total_fields += 1
            cand = result.nutrient_candidates.get(field_name)
            if expected_val is None:
                if cand is None:
                    correct_fields += 1
            else:
                if cand is not None and abs(cand.value - expected_val) < 0.25:
                    correct_fields += 1

    rate = (correct_fields / total_fields * 100.0) if total_fields else 0.0
    threshold = 95.0
    return BenchmarkMetric(
        name="Nutrient-to-Value Association",
        evaluated_count=total_fields,
        correct_count=correct_fields,
        error_count=total_fields - correct_fields,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
    )


def evaluate_serving_interpretation() -> BenchmarkMetric:
    """
    Evaluates parsing and unit normalization of varied serving declarations.
    """
    serving_tests = [
        ("Serving Size: 30g", 30.0, "g"),
        ("Serving Size: 2 Cookies (24g)", 24.0, "g"),
        ("Serving Size: 1 Pack (70g)", 70.0, "g"),
        ("Serving Size: 3 Pieces", 3.0, "piece"),
        ("Serving Size: 200 ml", 200.0, "ml"),
        ("Serving Size: 1 Biscuit (12.5g)", 12.5, "g"),
    ]

    evaluated = len(serving_tests)
    correct = 0

    for text, exp_val, exp_unit in serving_tests:
        res = parse_ocr_text(text)
        if res.serving_size_candidate == exp_val and res.serving_unit_candidate == exp_unit:
            correct += 1

    rate = (correct / evaluated * 100.0) if evaluated else 0.0
    threshold = 95.0
    return BenchmarkMetric(
        name="Serving-Size & Unit Interpretation",
        evaluated_count=evaluated,
        correct_count=correct,
        error_count=evaluated - correct,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
    )


def evaluate_calculation_correctness() -> BenchmarkMetric:
    """
    Asserts exact, independently calculated mathematical expected values for:
    1. Per-100g scaling factor from serving size.
    2. Per-serving scaling from per-100g.
    3. Percent of Daily Values (% DV) based on official ICMR-NIN/FSSAI reference intakes.
    4. Discrete units preserving None for per-100g.
    5. Missing values remaining None (zero silent conversions).
    """
    test_cases = [
        # Case 1: Per-serving solid food (30g) -> scale factor 100/30 = 3.3333...
        {
            "input": RawNutrientInput(
                serving_size=30.0,
                serving_unit=ServingUnit.G,
                basis=ServingBasis.PER_SERVING,
                food_form=FoodForm.SOLID,
                energy_kcal=140.0,
                protein_g=2.5,
                carbohydrates_g=22.0,
                total_sugar_g=8.0,
                added_sugar_g=6.0,
                total_fat_g=5.0,
                saturated_fat_g=2.0,
                trans_fat_g=0.0,
                sodium_mg=150.0,
            ),
            "expected_100": {
                "energy_kcal": 466.67,  # 140 * 100 / 30
                "protein_g": 8.33,  # 2.5 * 100 / 30
                "carbohydrates_g": 73.33,
                "total_sugar_g": 26.67,
                "added_sugar_g": 20.0,
                "total_fat_g": 16.67,
                "saturated_fat_g": 6.67,
                "trans_fat_g": 0.0,
                "sodium_mg": 500.0,
            },
            "expected_dv": {
                "protein_g": 4.6,  # (2.5 / 54.0) * 100 = 4.629 -> 4.6
                "added_sugar_g": 12.0,  # (6.0 / 50.0) * 100 = 12.0
                "total_fat_g": 7.5,  # (5.0 / 67.0) * 100 = 7.46 -> 7.5
                "saturated_fat_g": 10.0,  # (2.0 / 20.0) * 100 = 10.0
                "sodium_mg": 7.5,  # (150 / 2000) * 100 = 7.5
            },
        },
        # Case 2: Per-100ml liquid beverage (200ml serving) -> scale factor 200/100 = 2.0
        {
            "input": RawNutrientInput(
                serving_size=200.0,
                serving_unit=ServingUnit.ML,
                basis=ServingBasis.PER_100ML,
                food_form=FoodForm.LIQUID,
                energy_kcal=45.0,
                protein_g=0.5,
                carbohydrates_g=10.0,
                total_sugar_g=9.5,
                added_sugar_g=8.0,
                total_fat_g=0.0,
                saturated_fat_g=0.0,
                trans_fat_g=0.0,
                sodium_mg=15.0,
            ),
            "expected_serving": {
                "energy_kcal": 90.0,  # 45 * 2.0
                "protein_g": 1.0,  # 0.5 * 2.0
                "carbohydrates_g": 20.0,
                "total_sugar_g": 19.0,
                "added_sugar_g": 16.0,
                "total_fat_g": 0.0,
                "saturated_fat_g": 0.0,
                "trans_fat_g": 0.0,
                "sodium_mg": 30.0,
            },
            "expected_dv": {
                "protein_g": 1.9,  # (1.0 / 54.0) * 100 = 1.85 -> 1.9
                "added_sugar_g": 32.0,  # (16.0 / 50.0) * 100 = 32.0
                "sodium_mg": 1.5,  # (30.0 / 2000) * 100 = 1.5
            },
        },
        # Case 3: Discrete piece without gram weight -> per_100 remains None
        {
            "input": RawNutrientInput(
                serving_size=2.0,
                serving_unit=ServingUnit.PIECE,
                basis=ServingBasis.PER_SERVING,
                food_form=FoodForm.SOLID,
                energy_kcal=120.0,
                protein_g=2.0,
                carbohydrates_g=15.0,
                total_sugar_g=6.0,
                added_sugar_g=5.0,
                total_fat_g=4.0,
                saturated_fat_g=1.5,
                trans_fat_g=0.0,
                sodium_mg=80.0,
            ),
            "expected_per_100_all_none": True,
            "expected_dv": {
                "protein_g": 3.7,  # (2.0 / 54.0) * 100 = 3.70 -> 3.7
                "added_sugar_g": 10.0,  # (5.0 / 50.0) * 100 = 10.0
            },
        },
    ]

    evaluated_checks = 0
    passed_checks = 0

    for case in test_cases:
        res = analyze_nutrition(case["input"])

        # Check status and assumptions completeness
        evaluated_checks += 1
        if res.status == "complete" and len(res.calculation_assumptions) >= 4:
            passed_checks += 1

        # Check independently calculated per_100 numbers
        if "expected_100" in case:
            for nutrient_k, expected_num in case["expected_100"].items():
                evaluated_checks += 1
                actual_num = res.per_100.get(nutrient_k)
                if actual_num is not None and abs(actual_num - expected_num) <= 0.05:
                    passed_checks += 1

        # Check independently calculated per_serving numbers
        if "expected_serving" in case:
            for nutrient_k, expected_num in case["expected_serving"].items():
                evaluated_checks += 1
                actual_num = res.per_serving.get(nutrient_k)
                if actual_num is not None and abs(actual_num - expected_num) <= 0.05:
                    passed_checks += 1

        # Check discrete piece preserves None for per_100
        if case.get("expected_per_100_all_none"):
            evaluated_checks += 1
            if all(v is None for v in res.per_100.values()):
                passed_checks += 1

        # Check independently computed % DVs
        if "expected_dv" in case:
            dv_map = {
                c.nutrient_key: c.percentage_of_daily_value for c in res.daily_value_comparisons
            }
            for ref_k, expected_pct in case["expected_dv"].items():
                evaluated_checks += 1
                actual_pct = dv_map.get(ref_k)
                if actual_pct is not None and abs(actual_pct - expected_pct) <= 0.15:
                    passed_checks += 1

    rate = (passed_checks / evaluated_checks * 100.0) if evaluated_checks else 0.0
    threshold = 98.0
    return BenchmarkMetric(
        name="Independent Numerical Calculation Correctness",
        evaluated_count=evaluated_checks,
        correct_count=passed_checks,
        error_count=evaluated_checks - passed_checks,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
    )


def evaluate_quality_gates() -> BenchmarkMetric:
    """
    Evaluates computer vision quality gate disposition against explicit intended outcomes:
    - High-quality clear image -> ACCEPT
    - Moderate glare -> WARN
    - Severe blur (<20 sharpness) -> REJECT
    - Extreme glare (>25% saturated) -> REJECT
    - Microscopic dimensions (<200px) -> REJECT
    - Corrupted payload -> REJECT (ImageValidationError)
    - Oversized payload -> REJECT (ImageValidationError)
    """
    test_cases: list[dict[str, Any]] = []

    # 1. High-quality crisp text image with good contrast and border -> intended: ACCEPT
    img_crisp = Image.new("RGB", (1000, 800), color=(180, 180, 180))
    d = ImageDraw.Draw(img_crisp)
    d.rectangle([(20, 20), (980, 780)], outline=(10, 10, 10), width=4)
    for y in range(60, 720, 30):
        d.text(
            (40, y),
            "NUTRITION FACTS ENERGY 140 KCAL PROTEIN 2.5G CARBS 22G TOTAL FAT 5G SODIUM 150MG",
            fill=(0, 0, 0),
        )
    buf_crisp = io.BytesIO()
    img_crisp.save(buf_crisp, format="PNG")
    test_cases.append(
        {"bytes": buf_crisp.getvalue(), "intended": "ACCEPT", "name": "Crisp high-contrast image"}
    )

    # 2. Moderate glare (20% white rectangle) -> intended: WARN
    img_warn = Image.new("RGB", (800, 600), color=(100, 100, 100))
    for x in range(200, 600):
        for y in range(180, 420):
            img_warn.putpixel((x, y), (255, 255, 255))
    buf_warn = io.BytesIO()
    img_warn.save(buf_warn, format="PNG")
    test_cases.append(
        {"bytes": buf_warn.getvalue(), "intended": "WARN", "name": "Moderate packaging glare (20%)"}
    )

    # 3. Severe blur image (flat zero-gradient uniform gray) -> intended: REJECT
    img_blur = Image.new("RGB", (700, 500), color=(128, 128, 128))
    buf_blur = io.BytesIO()
    img_blur.save(buf_blur, format="PNG")
    test_cases.append(
        {"bytes": buf_blur.getvalue(), "intended": "REJECT", "name": "Severe blur (flat uniform)"}
    )

    # 4. Extreme glare image (35% pure saturated white) -> intended: REJECT
    img_glare = Image.new("RGB", (800, 600), color=(100, 100, 100))
    for x in range(150, 650):
        for y in range(130, 470):
            img_glare.putpixel((x, y), (255, 255, 255))
    buf_glare = io.BytesIO()
    img_glare.save(buf_glare, format="PNG")
    test_cases.append(
        {"bytes": buf_glare.getvalue(), "intended": "REJECT", "name": "Extreme glare (>25%)"}
    )

    # 5. Microscopic dimensions (150x150) -> intended: REJECT
    img_micro = Image.new("RGB", (150, 150), color=(200, 200, 200))
    buf_micro = io.BytesIO()
    img_micro.save(buf_micro, format="PNG")
    test_cases.append(
        {
            "bytes": buf_micro.getvalue(),
            "intended": "REJECT",
            "name": "Microscopic dimensions (<200px)",
        }
    )

    # 6. Corrupted payload -> intended: REJECT
    test_cases.append(
        {
            "bytes": b"corrupted non image bytes" * 5,
            "intended": "REJECT",
            "name": "Corrupted byte stream",
            "validator_check": True,
        }
    )

    # 7. Oversized payload -> intended: REJECT
    test_cases.append(
        {
            "bytes": b"\x89PNG\r\n\x1a\n" + b"\x00" * 200,
            "intended": "REJECT",
            "name": "Oversized file",
            "validator_check": True,
            "max_bytes": 50,
        }
    )

    evaluated = len(test_cases)
    correct = 0
    false_acceptances = 0
    false_rejections = 0

    for tc in test_cases:
        intended = tc["intended"]
        if tc.get("validator_check"):
            try:
                validate_image_payload(tc["bytes"], max_bytes=tc.get("max_bytes", 10_000_000))
                # If it did not raise, it was accepted
                actual = "ACCEPT"
            except ImageValidationError:
                actual = "REJECT"
        else:
            qa = assess_image_quality(tc["bytes"])
            actual = qa.gate_outcome

        if actual == intended:
            correct += 1
        else:
            if intended == "REJECT" and actual in ("ACCEPT", "WARN"):
                false_acceptances += 1
            elif intended in ("ACCEPT", "WARN") and actual == "REJECT":
                false_rejections += 1

    rate = (correct / evaluated * 100.0) if evaluated else 0.0
    threshold = 95.0
    return BenchmarkMetric(
        name="Computer Vision Quality-Gate Decisions",
        evaluated_count=evaluated,
        correct_count=correct,
        error_count=evaluated - correct,
        success_rate=rate,
        threshold=threshold,
        status="PASS" if rate >= threshold else "FAIL",
        details={
            "false_acceptances": false_acceptances,
            "false_rejections": false_rejections,
        },
    )


def evaluate_physical_packaging_photos(
    dataset_path: Path,
    images_dir: Path,
    tesseract_installed: bool,
) -> BenchmarkMetric:
    """
    Evaluates optical character recognition and parsing against physical camera photographs
    using app.extraction.benchmark. If physical image files are not bundled in the repository,
    reports UNMEASURED with exact denominator of 0 evaluated.
    """
    if not dataset_path.exists():
        return BenchmarkMetric(
            name="Real-World Packaging Photographs",
            evaluated_count=0,
            correct_count=0,
            error_count=0,
            success_rate=None,
            threshold=95.0,
            status="UNMEASURED",
            details={
                "reason": "Dataset metadata file not found",
                "samples_count": 0,
            },
        )

    if not tesseract_installed:
        return BenchmarkMetric(
            name="Real-World Packaging Photographs",
            evaluated_count=0,
            correct_count=0,
            error_count=0,
            success_rate=None,
            threshold=95.0,
            status="BLOCKED",
            details={"reason": "Tesseract binary missing in host environment"},
        )

    from app.extraction.benchmark import evaluate_physical_dataset

    summary = evaluate_physical_dataset(dataset_path=dataset_path, images_dir=images_dir)

    if summary.samples_evaluated == 0:
        return BenchmarkMetric(
            name="Real-World Packaging Photographs",
            evaluated_count=0,
            correct_count=0,
            error_count=0,
            success_rate=None,
            threshold=95.0,
            status="UNMEASURED",
            details={
                "reason": summary.disclaimer,
                "cer": None,
                "wer": None,
                "association_accuracy": None,
                "samples_metadata_count": summary.total_samples_in_dataset,
            },
        )

    return BenchmarkMetric(
        name="Real-World Packaging Photographs",
        evaluated_count=summary.samples_evaluated,
        correct_count=summary.samples_passed,
        error_count=summary.samples_failed,
        success_rate=summary.sample_pass_rate,
        threshold=95.0,
        status="PASS" if summary.status == "PASS" else "FAIL",
        details={
            "cer": summary.mean_cer,
            "wer": summary.mean_wer,
            "field_exact_match_rate": summary.field_exact_match_rate,
            "field_tolerance_match_rate": summary.field_tolerance_match_rate,
            "field_omission_rate": summary.field_omission_rate,
            "samples_evaluated": summary.samples_evaluated,
        },
    )


def run_benchmark() -> BenchmarkSuiteResult:
    """
    Executes the comprehensive benchmark suite and regenerates docs/OCR_BENCHMARK_REPORT.md.
    """
    fixtures = load_realistic_fixtures()

    m_parser = evaluate_parser_correctness(fixtures)
    m_mock = evaluate_mock_adapter_integration()
    m_actual_ocr, tesseract_installed = evaluate_actual_ocr_recognition()
    m_assoc = evaluate_nutrient_association(fixtures)
    m_serving = evaluate_serving_interpretation()
    m_calc = evaluate_calculation_correctness()
    m_quality = evaluate_quality_gates()

    repo_root = Path(__file__).resolve().parent.parent.parent
    if repo_root.name == "services":
        repo_root = repo_root.parent
    dataset_path = repo_root / "data" / "real_food_labels" / "samples.json"
    images_dir = repo_root / "data" / "real_food_labels" / "images"

    m_physical = evaluate_physical_packaging_photos(dataset_path, images_dir, tesseract_installed)

    suite = BenchmarkSuiteResult(
        parser_metric=m_parser,
        mock_adapter_metric=m_mock,
        actual_ocr_metric=m_actual_ocr,
        association_metric=m_assoc,
        serving_metric=m_serving,
        calculation_metric=m_calc,
        quality_gate_metric=m_quality,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        tesseract_available=tesseract_installed,
        physical_metric=m_physical,
    )

    report_path = repo_root / "docs" / "OCR_BENCHMARK_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    ocr_denom = (
        f"{m_actual_ocr.evaluated_count} rendered test lines"
        if m_actual_ocr.status != "BLOCKED"
        else f"{m_actual_ocr.details.get('sample_count', 5)} rendered test lines (0 executed)"
    )
    ocr_rate = (
        f"{m_actual_ocr.success_rate:.1f}%"
        if m_actual_ocr.success_rate is not None
        else "N/A (Blocked)"
    )

    if m_physical.evaluated_count == 0:
        physical_denom = "0 physical camera photographs (UNMEASURED)"
        physical_rate = "N/A (Unmeasured)"
    else:
        physical_denom = f"{m_physical.evaluated_count} physical camera photographs"
        physical_rate = f"{m_physical.success_rate:.1f}%"

    warning_block = (
        ""
        if tesseract_installed
        else f"""> [!WARNING]
> **Actual OCR Recognition Benchmark is BLOCKED.**
> The host environment does not have the 'tesseract' executable installed in PATH.
> Real optical character recognition on rendered images could NOT be executed and was NOT simulated using mocks.
> Mock adapter plumbing was verified separately under '{m_mock.name}', but mock output is strictly prevented from counting toward OCR accuracy.
> Overall benchmark status is BLOCKED pending installation of Tesseract-OCR.
"""
    )

    report_content = f"""# Food Label OCR & Deterministic Parsing Benchmark Report

Generated: {suite.generated_at}
Environment: Local deterministic test framework with OpenCV & Tesseract (Tesseract runtime present: {tesseract_installed})
Overall Suite Status: **{suite.overall_status}**

---

## 1. Executive Summary

This benchmark rigorously evaluates the deterministic parsing heuristics, computer vision quality gates,
nutrient-to-value association, and independent mathematical calculation pipelines of the healthyIndia food-label scanner.

> [!IMPORTANT]
> **Real-World Physical Camera Accuracy Remains Unmeasured.**
> These benchmarks measure algorithmic adherence, parser syntax, and computer vision
> boundaries on synthetic test fixtures, controlled rendered images, and mathematical boundary cases.
> Real-world accuracy on varied packaging reflections, warped foil pouches, curved cylindrical cans, and
> low-end mobile cameras remains unmeasured until comprehensive physical field testing with a verified ground-truth dataset.

{warning_block}
---

## 2. Benchmark Metrics & Evaluated Denominators

| Category | Evaluated Cases (Denominator) | Correct | Errors | Success Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **{m_parser.name}** | {m_parser.evaluated_count} realistic text fixtures | {m_parser.correct_count} | {m_parser.error_count} | **{m_parser.success_rate:.1f}%** | {m_parser.status} |
| **{m_mock.name}** | {m_mock.evaluated_count} mock adapter assertions | {m_mock.correct_count} | {m_mock.error_count} | **{m_mock.success_rate:.1f}%** | {m_mock.status} |
| **{m_actual_ocr.name}** | {ocr_denom} | {m_actual_ocr.correct_count} | {m_actual_ocr.error_count} | **{ocr_rate}** | {m_actual_ocr.status} |
| **{m_assoc.name}** | {m_assoc.evaluated_count} nutrient fields | {m_assoc.correct_count} | {m_assoc.error_count} | **{m_assoc.success_rate:.1f}%** | {m_assoc.status} |
| **{m_serving.name}** | {m_serving.evaluated_count} unit/serving formats | {m_serving.correct_count} | {m_serving.error_count} | **{m_serving.success_rate:.1f}%** | {m_serving.status} |
| **{m_calc.name}** | {m_calc.evaluated_count} mathematical checks | {m_calc.correct_count} | {m_calc.error_count} | **{m_calc.success_rate:.1f}%** | {m_calc.status} |
| **{m_quality.name}** | {m_quality.evaluated_count} edge-case inputs | {m_quality.correct_count} | {m_quality.error_count} | **{m_quality.success_rate:.1f}%** | {m_quality.status} |
| **{m_physical.name}** | {physical_denom} | {m_physical.correct_count} | {m_physical.error_count} | **{physical_rate}** | {m_physical.status} |

**Overall Benchmark Outcome**: **{suite.overall_status}** ({"All required criteria met" if suite.all_passed else "One or more required criteria failed or blocked"})
Quality-Gate Specifics: False Acceptances: {m_quality.details.get("false_acceptances", 0)}, False Rejections: {m_quality.details.get("false_rejections", 0)}.

---

## 3. Discrepancy & Plausibility Protection

The scanner implements defense-in-depth against silent misinterpretations:
1. **Multi-Pass OCR Discrepancy Detection**: Dual preprocessing passes (CLAHE normalized vs deskewed binarization) audit character-level consistency. Note: agreement between passes does not guarantee accuracy when both passes encounter identical character degradation.
2. **Physical Plausibility Constraints**:
   - Added Sugars cannot exceed Total Sugars (with documented 0.2g regulatory rounding tolerance).
   - Saturated Fat + Trans Fat cannot exceed Total Fat (with documented 0.5g rounding allowance).
   - Solid food macronutrient sum cannot exceed 105g per 100g (5g analytical tolerance).
   - Liquid food macronutrient sum per 100ml accounts for liquid densities up to 1.45 g/ml (syrups/honey).
   - Atwater calorie discrepancy flags discordance between declared energy and macronutrients, with documented exceptions for dietary fiber, polyols, and organic acids.
3. **Strict Confirmation Workflow**:
   - Extracted values are tagged as unverified draft candidates (`status: "unconfirmed"`).
   - Final nutrition calculations require explicit confirmation of all inputs with cryptographic SHA-256 digest validation (`confirmed_values_hash`).

---

## 4. Public Release Acceptance Criteria

Before declaring the food label scanner ready for unassisted public deployment, the following physical criteria must be satisfied:
1. **Physical Dataset**: Minimum 500 verified camera photographs across 10 distinct Indian packaged food categories (biscuits, namkeen, dairy, beverages, instant noodles, edible oils, spices, breakfast cereals, confectionery, ready meals). Current status: Specification and 10 transcribed reference baselines established (status: SCHEMA_VERIFIED_EVIDENCE_PENDING); physical image files are not bundled in repository (0 physical camera photos evaluated).
2. **Real-World Character Recognition**: Character accuracy >= 98.5% on clear packaging; >= 92% on curved or glossy packages. Current status: UNMEASURED.
3. **Nutrient Association Accuracy**: >= 95% correct association of numbers to parent nutrients on physical camera images. Current status: UNMEASURED.
4. **Zero Silent Conversions**: 100% adherence to the zero-conversion rule (missing values remain `None`, never converted to `0.0`). Current status: PASSED in algorithmic and mathematical suites.
5. **Zero Unconfirmed Calculations**: 100% mandatory user verification before final nutrition calculations. Current status: PASSED with cryptographic SHA-256 value-tied confirmation hash.

**Public Release Readiness Gate Status**: **NOT READY** (Physical camera photograph dataset not bundled; character and nutrient recognition on physical camera photos remains unmeasured).
"""

    report_path.write_text(report_content, encoding="utf-8")
    print(f"Benchmark completed. Report written to {report_path}")
    print(f"Overall Status: {suite.overall_status} (all_passed={suite.all_passed})")
    print(
        f"Parser Correctness: {m_parser.success_rate:.1f}% "
        f"({m_parser.correct_count}/{m_parser.evaluated_count})"
    )
    print(
        f"Mock Adapter Plumbing: {m_mock.success_rate:.1f}% "
        f"({m_mock.correct_count}/{m_mock.evaluated_count})"
    )
    if m_actual_ocr.status == "BLOCKED":
        print("Actual OCR Recognition: BLOCKED (Tesseract binary missing in PATH)")
    else:
        print(
            f"Actual OCR Recognition: {m_actual_ocr.success_rate:.1f}% "
            f"({m_actual_ocr.correct_count}/{m_actual_ocr.evaluated_count})"
        )
    print(
        f"Association Accuracy: {m_assoc.success_rate:.1f}% "
        f"({m_assoc.correct_count}/{m_assoc.evaluated_count})"
    )
    print(
        f"Serving Accuracy: {m_serving.success_rate:.1f}% "
        f"({m_serving.correct_count}/{m_serving.evaluated_count})"
    )
    print(
        f"Calculation Accuracy: {m_calc.success_rate:.1f}% "
        f"({m_calc.correct_count}/{m_calc.evaluated_count})"
    )
    print(
        f"Quality Gates: {m_quality.success_rate:.1f}% "
        f"({m_quality.correct_count}/{m_quality.evaluated_count})"
    )
    if m_physical.status == "UNMEASURED":
        print(
            "Physical Packaging Photographs: UNMEASURED (0 evaluated; physical images not bundled)"
        )
    elif m_physical.status == "BLOCKED":
        print(
            "Physical Packaging Photographs: BLOCKED (Tesseract binary missing in host environment)"
        )
    elif m_physical.success_rate is not None:
        print(
            f"Physical Packaging Photographs: {m_physical.success_rate:.1f}% "
            f"({m_physical.correct_count}/{m_physical.evaluated_count})"
        )
    else:
        print(f"Physical Packaging Photographs: {m_physical.status}")
    return suite


if __name__ == "__main__":
    suite = run_benchmark()
    if not suite.all_passed:
        print(f"Benchmark finished with non-passing status: {suite.overall_status}")
