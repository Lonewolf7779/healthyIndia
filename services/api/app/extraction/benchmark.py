"""
Evidence-based benchmark evaluator for physical food-label photographs and local OCR.

Evaluates real optical character recognition performance against verified ground truth.
Defines explicit field-level tolerances, unit normalization, serving-basis checking,
Levenshtein error rates (CER/WER), omissions, unexpected predictions, and processing failures.
Does NOT fabricate accuracy claims or treat plausible predictions as correct without comparison.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from app.extraction.adapter import (
    BaseOcrAdapter,
    OcrEngineError,
    OcrEngineOutput,
    TesseractOcrAdapter,
)
from app.extraction.models import ExtractedNutrientCandidate, OcrExtractionResult
from app.extraction.parser import parse_ocr_text

# ==============================================================================
# 1. FIELD-SPECIFIC TOLERANCE DEFINITIONS
# ==============================================================================
# (absolute_tolerance, relative_tolerance_ratio)
# Exact match requires abs(pred - gt) <= 0.001.
# Tolerance match allows field-specific physical and rounding margins.
#
# REGULATORY SOURCING & PROVISIONAL POLICY AUDIT:
# - `trans_fat_g`: Traceable to FSSAI (Labeling and Display) Regulations, 2020.
#   Products claiming "trans-fat free" must contain < 0.2g per 100g. A strict
#   tolerance of 0.05g is set to avoid classification flips across this boundary.
# - `energy_kcal`: Sourced partially from FSSAI Schedule II rounding rules permitting
#   energy declaration to nearest 1 kcal. 1.0 kcal or 1% relative is provisional.
# - All other nutrient tolerances (`protein_g`, `carbohydrates_g`, `total_sugar_g`,
#   `added_sugar_g`, `dietary_fiber_g`, `total_fat_g`, `saturated_fat_g`, `cholesterol_mg`,
#   `sodium_mg`): Designated as PROVISIONAL BENCHMARK POLICIES. They are engineering
#   tolerances designed to absorb acceptable consumer-label rounding variations without
#   masking genuine OCR misreads. They remain fully configurable.
PROVISIONAL_FIELD_TOLERANCES: Final[dict[str, tuple[float, float]]] = {
    # Energy: 1.0 kcal absolute or 1% relative, whichever is larger
    "energy_kcal": (1.0, 0.01),
    # Standard macronutrients: 0.2g absolute or 2% relative
    "protein_g": (0.2, 0.02),
    "carbohydrates_g": (0.2, 0.02),
    "total_sugar_g": (0.2, 0.02),
    "added_sugar_g": (0.2, 0.02),
    "dietary_fiber_g": (0.2, 0.02),
    "total_fat_g": (0.2, 0.02),
    "saturated_fat_g": (0.2, 0.02),
    # Trans fat: strict 0.05g absolute (FSSAI 0.2g regulatory claim boundary)
    "trans_fat_g": (0.05, 0.05),
    # Cholesterol: 1.0 mg absolute or 2% relative
    "cholesterol_mg": (1.0, 0.02),
    # Sodium: 5.0 mg absolute or 2% relative (reflects integer scale e.g. 780mg vs 785mg)
    "sodium_mg": (5.0, 0.02),
}

# Alias for backwards compatibility
FIELD_TOLERANCES: Final[dict[str, tuple[float, float]]] = PROVISIONAL_FIELD_TOLERANCES

ALL_EVALUATED_NUTRIENTS: Final[list[str]] = [
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "total_sugar_g",
    "added_sugar_g",
    "dietary_fiber_g",
    "total_fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "cholesterol_mg",
    "sodium_mg",
]


# ==============================================================================
# 2. STRING DISTANCE ALGORITHMS (CER / WER / INGREDIENT METRICS)
# ==============================================================================
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


def compute_character_error_rate(reference: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Computes standard Character Error Rate (CER):
        CER = Levenshtein(reference, hypothesis) / len(reference)

    By standard definition, this metric is UNCAPPED and may exceed 1.0 when hypothesis
    contains insertions exceeding the length of the reference.

    Normalization (when normalize=True):
    - Trims leading and trailing whitespace.
    - Converts text to lowercase.
    - Collapses consecutive whitespace sequences into a single space.

    Edge cases:
    - If reference and hypothesis are both empty: returns 0.0 (perfect match).
    - If reference is empty and hypothesis is non-empty: returns float(len(hypothesis))
      (all hypothesis characters are pure insertions relative to empty reference).
    """
    if normalize:
        ref = re.sub(r"\s+", " ", reference.strip().lower())
        hyp = re.sub(r"\s+", " ", hypothesis.strip().lower())
    else:
        ref = reference
        hyp = hypothesis

    if not ref:
        return 0.0 if not hyp else float(len(hyp))

    dist = compute_levenshtein_distance(ref, hyp)
    return dist / len(ref)


def compute_word_error_rate(reference: str, hypothesis: str, normalize: bool = True) -> float:
    """
    Computes standard Word Error Rate (WER):
        WER = (Substitutions + Deletions + Insertions) / N_reference

    By standard definition, this metric is UNCAPPED and may exceed 1.0 when hypothesis
    contains extra words exceeding the reference word count.

    Normalization (when normalize=True):
    - Trims and lowercases both strings.
    - Tokenizes by whitespace into word tokens.

    Edge cases:
    - If reference and hypothesis have 0 words: returns 0.0.
    - If reference has 0 words and hypothesis has non-empty words: returns float(len(hyp_words))
      (all words are pure insertions).
    """
    if normalize:
        ref_words = reference.strip().lower().split()
        hyp_words = hypothesis.strip().lower().split()
    else:
        ref_words = reference.split()
        hyp_words = hypothesis.split()

    if not ref_words:
        return 0.0 if not hyp_words else float(len(hyp_words))

    len_ref = len(ref_words)
    len_hyp = len(hyp_words)

    # Dynamic programming matrix for token-level Levenshtein distance
    dp = [[0] * (len_hyp + 1) for _ in range(len_ref + 1)]
    for i in range(len_ref + 1):
        dp[i][0] = i
    for j in range(len_hyp + 1):
        dp[0][j] = j

    for i in range(1, len_ref + 1):
        for j in range(1, len_hyp + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(
                    dp[i - 1][j] + 1,  # deletion
                    dp[i][j - 1] + 1,  # insertion
                    dp[i - 1][j - 1] + 1,  # substitution
                )
    return dp[len_ref][len_hyp] / len_ref


def _tokenize_ingredient_text(text: str) -> set[str]:
    """
    Normalizes and extracts unique alphanumeric ingredient tokens.
    Strips brackets, punctuation, percentages, and capitalization.
    """
    cleaned = text.lower()
    tokens = re.findall(r"\b[a-z0-9\-]+\b", cleaned)
    return set(tokens)


def compute_ingredient_recall(reference: str, hypothesis: str) -> float:
    """
    Measures ingredient token recovery rate (Recall):
        Recall = |Reference_Tokens ∩ Hypothesis_Tokens| / |Reference_Tokens|

    Measures what proportion of genuine ground-truth ingredient words were detected.
    Returns 1.0 if reference is empty (and hypothesis empty), 0.0 if reference has
    tokens but none were recovered.
    """
    ref_tokens = _tokenize_ingredient_text(reference)
    hyp_tokens = _tokenize_ingredient_text(hypothesis)
    if not ref_tokens:
        return 1.0 if not hyp_tokens else 0.0
    overlap = ref_tokens.intersection(hyp_tokens)
    return len(overlap) / len(ref_tokens)


def compute_ingredient_precision(reference: str, hypothesis: str) -> float:
    """
    Measures ingredient token precision:
        Precision = |Reference_Tokens ∩ Hypothesis_Tokens| / |Hypothesis_Tokens|

    Measures what proportion of predicted ingredient tokens actually belong to the ground truth.
    Returns 1.0 if hypothesis is empty (and reference empty), 0.0 if hypothesis has
    tokens but none match ground truth.
    """
    ref_tokens = _tokenize_ingredient_text(reference)
    hyp_tokens = _tokenize_ingredient_text(hypothesis)
    if not hyp_tokens:
        return 1.0 if not ref_tokens else 0.0
    overlap = ref_tokens.intersection(hyp_tokens)
    return len(overlap) / len(hyp_tokens)


def compute_ingredient_jaccard_similarity(reference: str, hypothesis: str) -> float:
    """
    Measures true Jaccard similarity between ingredient token sets:
        Jaccard = |Reference_Tokens ∩ Hypothesis_Tokens| / |Reference_Tokens ∪ Hypothesis_Tokens|

    Penalizes both missed ingredients (false negatives) and spurious tokens (false positives).
    """
    ref_tokens = _tokenize_ingredient_text(reference)
    hyp_tokens = _tokenize_ingredient_text(hypothesis)
    if not ref_tokens and not hyp_tokens:
        return 1.0
    union = ref_tokens.union(hyp_tokens)
    if not union:
        return 1.0
    overlap = ref_tokens.intersection(hyp_tokens)
    return len(overlap) / len(union)


def compute_ingredient_completeness(reference: str, hypothesis: str) -> float:
    """
    Preserved for backwards compatibility. Alias for compute_ingredient_recall().
    Note: Reflects token recovery (Recall), not Jaccard intersection-over-union.
    """
    return compute_ingredient_recall(reference, hypothesis)


# ==============================================================================
# 3. DATA STRUCTURES
# ==============================================================================
@dataclass
class NutrientComparisonResult:
    """Detailed evaluation outcome for an individual nutrient field."""

    field_name: str
    ground_truth_value: float | None
    ground_truth_unit: str | None
    predicted_value: float | None
    predicted_unit: str | None
    is_declared_in_gt: bool
    is_predicted: bool
    is_exact_match: bool
    is_tolerance_match: bool
    is_omission: bool  # Declared in GT but missed by OCR
    is_unexpected: bool  # Absent/unreadable in GT but predicted by OCR
    unit_mismatch: bool
    basis_mismatch: bool
    absolute_error: float | None
    relative_error: float | None


@dataclass
class SampleBenchmarkResult:
    """Evaluation outcome for a single packaged food photo sample."""

    sample_id: str
    product_name: str
    category: str
    packaging_format: str
    capture_metadata: dict[str, str]
    image_found: bool
    processing_success: bool
    processing_error: str | None
    processing_time_seconds: float
    raw_ocr_text: str
    cer: float | None
    wer: float | None
    ingredient_completeness: float | None
    ingredient_recall: float | None = None
    ingredient_precision: float | None = None
    ingredient_jaccard: float | None = None
    nutrient_comparisons: dict[str, NutrientComparisonResult] = field(default_factory=dict)
    sample_passed: bool = False


@dataclass
class FieldBenchmarkMetric:
    """Aggregated statistics for a specific nutrient across all evaluated samples."""

    field_name: str
    declared_in_gt_count: int
    predicted_count: int
    exact_matches: int
    tolerance_matches: int
    omissions: int
    unexpected_predictions: int
    unit_mismatches: int
    basis_mismatches: int
    exact_match_rate: float | None
    tolerance_match_rate: float | None
    omission_rate: float | None
    mean_absolute_error: float | None
    mean_relative_error: float | None


@dataclass
class RealPhotoBenchmarkSummary:
    """Comprehensive, machine-readable summary of physical photo benchmark."""

    total_samples_in_dataset: int
    images_bundled_on_disk: int
    samples_pending_evidence: int
    samples_evaluated: int
    samples_passed: int
    samples_failed: int
    sample_pass_rate: float | None
    image_processing_success_rate: float | None
    total_declared_fields: int
    field_exact_matches: int
    field_tolerance_matches: int
    field_exact_match_rate: float | None
    field_tolerance_match_rate: float | None
    field_omissions: int
    field_omission_rate: float | None
    unexpected_predictions: int
    mean_cer: float | None
    mean_wer: float | None
    mean_ingredient_completeness: float | None
    mean_ingredient_recall: float | None = None
    mean_ingredient_precision: float | None = None
    mean_ingredient_jaccard: float | None = None
    metrics_by_nutrient: dict[str, FieldBenchmarkMetric] = field(default_factory=dict)
    metrics_by_condition: dict[str, dict[str, Any]] = field(default_factory=dict)
    execution_timestamp: str = ""
    status: str = "UNMEASURED"  # "PASS", "FAIL", "UNMEASURED", "BLOCKED"
    disclaimer: str = ""
    sample_results: list[SampleBenchmarkResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts summary to dictionary suitable for JSON serialization."""
        return asdict(self)


# ==============================================================================
# 4. FIELD-LEVEL COMPARISON LOGIC
# ==============================================================================
def normalize_unit_and_value(
    pred_val: float,
    pred_unit: str | None,
    gt_unit: str | None,
) -> tuple[float | None, bool]:
    """
    Normalizes predicted value to ground truth units if compatible (e.g. g <-> mg).
    Returns (normalized_value, unit_mismatch_flag).
    """
    if gt_unit is None or pred_unit is None:
        return pred_val, False

    u_pred = pred_unit.strip().lower()
    u_gt = gt_unit.strip().lower()

    if u_pred == u_gt:
        return pred_val, False

    # Metric mass conversion
    if u_gt == "g" and u_pred == "mg":
        return round(pred_val / 1000.0, 4), False
    if u_gt == "mg" and u_pred == "g":
        return round(pred_val * 1000.0, 1), False

    # Non-convertible incompatible units (e.g. g vs kcal, ml vs g for solid)
    return None, True


def compare_nutrient_field(
    field_name: str,
    gt_value: float | None,
    gt_unit: str | None,
    candidate: ExtractedNutrientCandidate | None,
    declaration_basis: str,
    tolerances: dict[str, tuple[float, float]] | None = None,
) -> NutrientComparisonResult:
    """
    Rigorously compares a predicted nutrient candidate against ground truth.
    Respects unreadable/omitted GT values, unit normalization, and field tolerances.
    Tolerances are configurable; defaults to PROVISIONAL_FIELD_TOLERANCES.
    """
    is_declared = gt_value is not None
    is_pred = candidate is not None and candidate.value is not None

    # Case 1: Ground truth field was unreadable or undeclared on package
    if not is_declared:
        return NutrientComparisonResult(
            field_name=field_name,
            ground_truth_value=None,
            ground_truth_unit=gt_unit,
            predicted_value=candidate.value if candidate else None,
            predicted_unit=candidate.unit if candidate else None,
            is_declared_in_gt=False,
            is_predicted=is_pred,
            is_exact_match=False,
            is_tolerance_match=False,
            is_omission=False,
            is_unexpected=is_pred,  # OCR hallucinated a value for an absent field
            unit_mismatch=False,
            basis_mismatch=False,
            absolute_error=None,
            relative_error=None,
        )

    # Case 2: Ground truth declared, but OCR failed to predict it (omission)
    if not is_pred or candidate is None or candidate.value is None:
        return NutrientComparisonResult(
            field_name=field_name,
            ground_truth_value=gt_value,
            ground_truth_unit=gt_unit,
            predicted_value=None,
            predicted_unit=None,
            is_declared_in_gt=True,
            is_predicted=False,
            is_exact_match=False,
            is_tolerance_match=False,
            is_omission=True,
            is_unexpected=False,
            unit_mismatch=False,
            basis_mismatch=False,
            absolute_error=None,
            relative_error=None,
        )

    # Case 3: Both ground truth and prediction are present -> evaluate numeric match
    pred_val = candidate.value
    pred_unit = candidate.unit or gt_unit

    # Check serving basis compatibility
    basis_mismatch = False
    cand_col = candidate.column
    if cand_col:
        if declaration_basis in ("per_100g", "per_100ml") and cand_col == "per_serving":
            basis_mismatch = True
        elif declaration_basis == "per_serving" and cand_col == "per_100g":
            basis_mismatch = True

    # Check unit compatibility and normalize
    norm_val, unit_mismatch = normalize_unit_and_value(pred_val, pred_unit, gt_unit)
    if unit_mismatch or norm_val is None or basis_mismatch:
        return NutrientComparisonResult(
            field_name=field_name,
            ground_truth_value=gt_value,
            ground_truth_unit=gt_unit,
            predicted_value=pred_val,
            predicted_unit=pred_unit,
            is_declared_in_gt=True,
            is_predicted=True,
            is_exact_match=False,
            is_tolerance_match=False,
            is_omission=False,
            is_unexpected=False,
            unit_mismatch=unit_mismatch,
            basis_mismatch=basis_mismatch,
            absolute_error=None,
            relative_error=None,
        )

    abs_err = round(abs(norm_val - gt_value), 4)
    rel_err = round(abs_err / gt_value, 4) if gt_value > 0 else (0.0 if abs_err == 0.0 else 1.0)

    # Exact match: abs_err <= 0.001
    is_exact = abs_err <= 0.001

    # Tolerance match: configurable field-specific policy
    active_tolerances = tolerances if tolerances is not None else PROVISIONAL_FIELD_TOLERANCES
    abs_tol, rel_tol = active_tolerances.get(field_name, (0.2, 0.02))
    allowed_tolerance = max(abs_tol, gt_value * rel_tol if gt_value > 0 else abs_tol)
    is_tol = abs_err <= (allowed_tolerance + 1e-9)

    return NutrientComparisonResult(
        field_name=field_name,
        ground_truth_value=gt_value,
        ground_truth_unit=gt_unit,
        predicted_value=norm_val,
        predicted_unit=gt_unit,
        is_declared_in_gt=True,
        is_predicted=True,
        is_exact_match=is_exact,
        is_tolerance_match=is_tol,
        is_omission=False,
        is_unexpected=False,
        unit_mismatch=False,
        basis_mismatch=False,
        absolute_error=abs_err,
        relative_error=rel_err,
    )


# ==============================================================================
# 5. SAMPLE EVALUATOR
# ==============================================================================
def evaluate_sample(
    sample_data: dict[str, Any],
    images_dir: Path | None = None,
    adapter: BaseOcrAdapter | None = None,
    preloaded_image_bytes: bytes | None = None,
    tolerances: dict[str, tuple[float, float]] | None = None,
) -> SampleBenchmarkResult:
    """
    Evaluates a single food label sample against the local OCR pipeline.
    Accepts preloaded image bytes or resolves the file in images_dir.
    """
    sample_id = sample_data.get("sample_id", "UNKNOWN")
    product_name = sample_data.get("product_name", "Unknown Product")
    category = sample_data.get("category", "Unknown Category")
    pkg_format = sample_data.get("packaging_format", "unknown")
    capture_meta = sample_data.get("capture_metadata", {})

    # Image retrieval
    img_bytes: bytes | None = preloaded_image_bytes
    img_found = False

    if img_bytes is None and images_dir is not None:
        img_name = sample_data.get("image_filename")
        if img_name:
            img_path = images_dir / img_name
            if img_path.is_file():
                img_bytes = img_path.read_bytes()
                img_found = True
    elif img_bytes is not None:
        img_found = True

    if not img_found or img_bytes is None:
        return SampleBenchmarkResult(
            sample_id=sample_id,
            product_name=product_name,
            category=category,
            packaging_format=pkg_format,
            capture_metadata=capture_meta,
            image_found=False,
            processing_success=False,
            processing_error="Physical photograph file not found on disk",
            processing_time_seconds=0.0,
            raw_ocr_text="",
            cer=None,
            wer=None,
            ingredient_completeness=None,
            ingredient_recall=None,
            ingredient_precision=None,
            ingredient_jaccard=None,
            nutrient_comparisons={},
            sample_passed=False,
        )

    # Execute local OCR
    ocr_adapter = adapter or TesseractOcrAdapter()
    start_time = time.perf_counter()
    try:
        ocr_output: OcrEngineOutput = ocr_adapter.extract_text(img_bytes)
        raw_text = ocr_output.raw_text
        parsed: OcrExtractionResult = parse_ocr_text(raw_text, ocr_output.confidence)
        duration = round(time.perf_counter() - start_time, 3)
        proc_success = True
        proc_error = None
    except OcrEngineError as exc:
        duration = round(time.perf_counter() - start_time, 3)
        return SampleBenchmarkResult(
            sample_id=sample_id,
            product_name=product_name,
            category=category,
            packaging_format=pkg_format,
            capture_metadata=capture_meta,
            image_found=True,
            processing_success=False,
            processing_error=f"OCR Engine Failure: {exc.message}",
            processing_time_seconds=duration,
            raw_ocr_text="",
            cer=None,
            wer=None,
            ingredient_completeness=None,
            ingredient_recall=None,
            ingredient_precision=None,
            ingredient_jaccard=None,
            nutrient_comparisons={},
            sample_passed=False,
        )
    except Exception as exc:
        duration = round(time.perf_counter() - start_time, 3)
        return SampleBenchmarkResult(
            sample_id=sample_id,
            product_name=product_name,
            category=category,
            packaging_format=pkg_format,
            capture_metadata=capture_meta,
            image_found=True,
            processing_success=False,
            processing_error=f"Processing Exception: {str(exc)}",
            processing_time_seconds=duration,
            raw_ocr_text="",
            cer=None,
            wer=None,
            ingredient_completeness=None,
            ingredient_recall=None,
            ingredient_precision=None,
            ingredient_jaccard=None,
            nutrient_comparisons={},
            sample_passed=False,
        )

    # Evaluate ingredient text metrics
    gt_ing = sample_data.get("ground_truth_ingredients_text")
    pred_ing = parsed.ingredients_text or ""
    cer = compute_character_error_rate(gt_ing, pred_ing) if gt_ing else None
    wer = compute_word_error_rate(gt_ing, pred_ing) if gt_ing else None
    ing_recall = compute_ingredient_recall(gt_ing, pred_ing) if gt_ing else None
    ing_prec = compute_ingredient_precision(gt_ing, pred_ing) if gt_ing else None
    ing_jacc = compute_ingredient_jaccard_similarity(gt_ing, pred_ing) if gt_ing else None
    ing_comp = ing_recall  # alias for backwards compatibility

    # Evaluate nutrients
    gt_nutr = sample_data.get("ground_truth_nutrition", {})
    gt_basis = gt_nutr.get("declaration_basis", "per_100g")
    nutrients_map = gt_nutr.get("nutrients", {})

    comparisons: dict[str, NutrientComparisonResult] = {}
    sample_all_matched = True

    for field_name in ALL_EVALUATED_NUTRIENTS:
        gt_val = nutrients_map.get(field_name)

        # Select candidate: check column basis specific candidates first
        cand = None
        if gt_basis in ("per_100g", "per_100ml"):
            cand = parsed.per_100_candidates.get(field_name)
        elif gt_basis == "per_serving":
            cand = parsed.per_serving_candidates.get(field_name)

        if cand is None:
            cand = parsed.nutrient_candidates.get(field_name)

        # Infer standard unit
        expected_unit = (
            "mg"
            if field_name.endswith("_mg")
            else ("kcal" if field_name.endswith("_kcal") else "g")
        )

        res = compare_nutrient_field(
            field_name=field_name,
            gt_value=gt_val,
            gt_unit=expected_unit,
            candidate=cand,
            declaration_basis=gt_basis,
            tolerances=tolerances,
        )
        comparisons[field_name] = res

        if res.is_declared_in_gt and not res.is_tolerance_match:
            sample_all_matched = False

    # Sample-level pass criteria:
    # 1. Processing succeeded
    # 2. All declared nutrients meet tolerance match
    # 3. If ingredient text declared, CER <= 0.20
    sample_passed = proc_success and sample_all_matched
    if cer is not None and cer > 0.20:
        sample_passed = False

    return SampleBenchmarkResult(
        sample_id=sample_id,
        product_name=product_name,
        category=category,
        packaging_format=pkg_format,
        capture_metadata=capture_meta,
        image_found=True,
        processing_success=proc_success,
        processing_error=proc_error,
        processing_time_seconds=duration,
        raw_ocr_text=raw_text,
        cer=cer,
        wer=wer,
        ingredient_completeness=ing_comp,
        ingredient_recall=ing_recall,
        ingredient_precision=ing_prec,
        ingredient_jaccard=ing_jacc,
        nutrient_comparisons=comparisons,
        sample_passed=sample_passed,
    )


# ==============================================================================
# 6. DATASET VALIDATION & AGGREGATION
# ==============================================================================
def validate_benchmark_dataset(samples: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """
    Defensively validates benchmark dataset structure before execution.
    Checks for empty dataset, duplicate IDs, and malformed records.
    """
    errors: list[str] = []
    if not samples:
        errors.append("Dataset is empty. At least one sample is required.")
        return False, errors

    seen_ids: set[str] = set()
    for idx, s in enumerate(samples):
        sid = s.get("sample_id")
        if not sid or not isinstance(sid, str):
            errors.append(f"Sample at index {idx} is missing a valid 'sample_id'.")
            continue
        if sid in seen_ids:
            errors.append(f"Duplicate sample_id '{sid}' detected at index {idx}.")
        seen_ids.add(sid)

        gt_nutr = s.get("ground_truth_nutrition")
        if not isinstance(gt_nutr, dict):
            errors.append(f"[{sid}] Missing or invalid 'ground_truth_nutrition' object.")
        elif not isinstance(gt_nutr.get("nutrients"), dict):
            errors.append(f"[{sid}] Missing or invalid 'nutrients' map in ground_truth_nutrition.")

    return len(errors) == 0, errors


def evaluate_physical_dataset(
    dataset_path: Path,
    images_dir: Path,
    adapter: BaseOcrAdapter | None = None,
    field_tolerances: dict[str, tuple[float, float]] | None = None,
) -> RealPhotoBenchmarkSummary:
    """
    Executes benchmark over the complete real packaged food dataset.
    If physical image files are not bundled on disk, honestly reports UNMEASURED.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    if not dataset_path.is_file():
        return RealPhotoBenchmarkSummary(
            total_samples_in_dataset=0,
            images_bundled_on_disk=0,
            samples_pending_evidence=0,
            samples_evaluated=0,
            samples_passed=0,
            samples_failed=0,
            sample_pass_rate=None,
            image_processing_success_rate=None,
            total_declared_fields=0,
            field_exact_matches=0,
            field_tolerance_matches=0,
            field_exact_match_rate=None,
            field_tolerance_match_rate=None,
            field_omissions=0,
            field_omission_rate=None,
            unexpected_predictions=0,
            mean_cer=None,
            mean_wer=None,
            mean_ingredient_completeness=None,
            mean_ingredient_recall=None,
            mean_ingredient_precision=None,
            mean_ingredient_jaccard=None,
            metrics_by_nutrient={},
            metrics_by_condition={},
            execution_timestamp=timestamp,
            status="UNMEASURED",
            disclaimer="Dataset file not found.",
        )

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    samples: list[dict[str, Any]] = data.get("samples", [])

    is_valid, validation_errors = validate_benchmark_dataset(samples)
    if not is_valid:
        raise ValueError(f"Benchmark dataset validation failed: {'; '.join(validation_errors)}")

    # Check for available physical images
    available_image_count = 0
    if images_dir.is_dir():
        available_image_count = len(
            [
                p
                for p in images_dir.iterdir()
                if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            ]
        )

    # When 0 physical image files exist on disk, report UNMEASURED fail-closed
    if available_image_count == 0:
        return RealPhotoBenchmarkSummary(
            total_samples_in_dataset=len(samples),
            images_bundled_on_disk=0,
            samples_pending_evidence=len(samples),
            samples_evaluated=0,
            samples_passed=0,
            samples_failed=0,
            sample_pass_rate=None,
            image_processing_success_rate=None,
            total_declared_fields=0,
            field_exact_matches=0,
            field_tolerance_matches=0,
            field_exact_match_rate=None,
            field_tolerance_match_rate=None,
            field_omissions=0,
            field_omission_rate=None,
            unexpected_predictions=0,
            mean_cer=None,
            mean_wer=None,
            mean_ingredient_completeness=None,
            mean_ingredient_recall=None,
            mean_ingredient_precision=None,
            mean_ingredient_jaccard=None,
            metrics_by_nutrient={},
            metrics_by_condition={},
            execution_timestamp=timestamp,
            status="UNMEASURED",
            disclaimer=(
                "Physical food label photograph files are not bundled on disk in "
                "data/real_food_labels/images/. Real optical character recognition "
                "performance remains strictly UNMEASURED (0 evaluated). Synthetic "
                "fixture tests and schema validations must not be substituted for "
                "physical evidence."
            ),
        )

    # Evaluate each sample that has an image present on disk
    sample_results: list[SampleBenchmarkResult] = []
    for s in samples:
        img_name = s.get("image_filename")
        if not img_name or not (images_dir / img_name).is_file():
            continue
        res = evaluate_sample(
            s,
            images_dir=images_dir,
            adapter=adapter,
            tolerances=field_tolerances,
        )
        sample_results.append(res)

    evaluated_count = len(sample_results)
    if evaluated_count == 0:
        return RealPhotoBenchmarkSummary(
            total_samples_in_dataset=len(samples),
            images_bundled_on_disk=available_image_count,
            samples_pending_evidence=len(samples),
            samples_evaluated=0,
            samples_passed=0,
            samples_failed=0,
            sample_pass_rate=None,
            image_processing_success_rate=None,
            total_declared_fields=0,
            field_exact_matches=0,
            field_tolerance_matches=0,
            field_exact_match_rate=None,
            field_tolerance_match_rate=None,
            field_omissions=0,
            field_omission_rate=None,
            unexpected_predictions=0,
            mean_cer=None,
            mean_wer=None,
            mean_ingredient_completeness=None,
            mean_ingredient_recall=None,
            mean_ingredient_precision=None,
            mean_ingredient_jaccard=None,
            metrics_by_nutrient={},
            metrics_by_condition={},
            execution_timestamp=timestamp,
            status="UNMEASURED",
            disclaimer=(
                "Images present on disk did not match any sample image filenames in samples.json."
            ),
        )

    # Aggregate sample-level metrics
    proc_success_count = sum(1 for r in sample_results if r.processing_success)
    samples_passed = sum(1 for r in sample_results if r.sample_passed)
    samples_failed = evaluated_count - samples_passed

    cers = [r.cer for r in sample_results if r.cer is not None]
    wers = [r.wer for r in sample_results if r.wer is not None]
    comps = [
        r.ingredient_completeness for r in sample_results if r.ingredient_completeness is not None
    ]
    recalls = [r.ingredient_recall for r in sample_results if r.ingredient_recall is not None]
    precisions = [
        r.ingredient_precision for r in sample_results if r.ingredient_precision is not None
    ]
    jaccards = [r.ingredient_jaccard for r in sample_results if r.ingredient_jaccard is not None]

    mean_cer = round(sum(cers) / len(cers), 3) if cers else None
    mean_wer = round(sum(wers) / len(wers), 3) if wers else None
    mean_comp = round(sum(comps) / len(comps), 3) if comps else None
    mean_recall = round(sum(recalls) / len(recalls), 3) if recalls else None
    mean_precision = round(sum(precisions) / len(precisions), 3) if precisions else None
    mean_jaccard = round(sum(jaccards) / len(jaccards), 3) if jaccards else None

    # Aggregate field-level metrics across all evaluated samples
    total_declared_fields = 0
    total_exact_matches = 0
    total_tolerance_matches = 0
    total_omissions = 0
    total_unexpected = 0

    nutrient_stats: dict[str, dict[str, Any]] = {
        k: {
            "declared": 0,
            "predicted": 0,
            "exact": 0,
            "tolerance": 0,
            "omissions": 0,
            "unexpected": 0,
            "unit_mismatch": 0,
            "basis_mismatch": 0,
            "abs_errors": [],
            "rel_errors": [],
        }
        for k in ALL_EVALUATED_NUTRIENTS
    }

    # Grouping by condition: lighting, angle, state
    condition_stats: dict[str, dict[str, int]] = {}

    for r in sample_results:
        # Grouping tracker
        for cond_key, cond_val in r.capture_metadata.items():
            composite_key = f"{cond_key}:{cond_val}"
            if composite_key not in condition_stats:
                condition_stats[composite_key] = {"evaluated": 0, "passed": 0}
            condition_stats[composite_key]["evaluated"] += 1
            if r.sample_passed:
                condition_stats[composite_key]["passed"] += 1

        for nut_field, comp in r.nutrient_comparisons.items():
            if nut_field not in nutrient_stats:
                continue
            st = nutrient_stats[nut_field]
            if comp.is_declared_in_gt:
                st["declared"] += 1
                total_declared_fields += 1
                if comp.is_predicted:
                    st["predicted"] += 1
                if comp.is_exact_match:
                    st["exact"] += 1
                    total_exact_matches += 1
                if comp.is_tolerance_match:
                    st["tolerance"] += 1
                    total_tolerance_matches += 1
                if comp.is_omission:
                    st["omissions"] += 1
                    total_omissions += 1
                if comp.unit_mismatch:
                    st["unit_mismatch"] += 1
                if comp.basis_mismatch:
                    st["basis_mismatch"] += 1
                if comp.absolute_error is not None:
                    st["abs_errors"].append(comp.absolute_error)
                if comp.relative_error is not None:
                    st["rel_errors"].append(comp.relative_error)
            elif comp.is_unexpected:
                st["unexpected"] += 1
                total_unexpected += 1

    # Build FieldBenchmarkMetric structures
    metrics_by_nutrient: dict[str, FieldBenchmarkMetric] = {}
    for nut_field, st in nutrient_stats.items():
        decl = st["declared"]
        exact_rate = round(st["exact"] / decl * 100.0, 1) if decl else None
        tol_rate = round(st["tolerance"] / decl * 100.0, 1) if decl else None
        omiss_rate = round(st["omissions"] / decl * 100.0, 1) if decl else None
        mae = round(sum(st["abs_errors"]) / len(st["abs_errors"]), 3) if st["abs_errors"] else None
        mre = round(sum(st["rel_errors"]) / len(st["rel_errors"]), 3) if st["rel_errors"] else None

        metrics_by_nutrient[nut_field] = FieldBenchmarkMetric(
            field_name=nut_field,
            declared_in_gt_count=decl,
            predicted_count=st["predicted"],
            exact_matches=st["exact"],
            tolerance_matches=st["tolerance"],
            omissions=st["omissions"],
            unexpected_predictions=st["unexpected"],
            unit_mismatches=st["unit_mismatch"],
            basis_mismatches=st["basis_mismatch"],
            exact_match_rate=exact_rate,
            tolerance_match_rate=tol_rate,
            omission_rate=omiss_rate,
            mean_absolute_error=mae,
            mean_relative_error=mre,
        )

    # Condition breakdown dict
    metrics_by_condition: dict[str, dict[str, Any]] = {}
    for ck, cv in condition_stats.items():
        ev = cv["evaluated"]
        ps = cv["passed"]
        metrics_by_condition[ck] = {
            "evaluated": ev,
            "passed": ps,
            "pass_rate": round(ps / ev * 100.0, 1) if ev else 0.0,
        }

    sample_pass_rate = round(samples_passed / evaluated_count * 100.0, 1)
    proc_success_rate = round(proc_success_count / evaluated_count * 100.0, 1)
    field_exact_rate = (
        round(total_exact_matches / total_declared_fields * 100.0, 1)
        if total_declared_fields
        else None
    )
    field_tol_rate = (
        round(total_tolerance_matches / total_declared_fields * 100.0, 1)
        if total_declared_fields
        else None
    )
    field_omiss_rate = (
        round(total_omissions / total_declared_fields * 100.0, 1) if total_declared_fields else None
    )

    overall_status = "PASS" if sample_pass_rate >= 80.0 else "FAIL"

    return RealPhotoBenchmarkSummary(
        total_samples_in_dataset=len(samples),
        images_bundled_on_disk=available_image_count,
        samples_pending_evidence=max(0, len(samples) - evaluated_count),
        samples_evaluated=evaluated_count,
        samples_passed=samples_passed,
        samples_failed=samples_failed,
        sample_pass_rate=sample_pass_rate,
        image_processing_success_rate=proc_success_rate,
        total_declared_fields=total_declared_fields,
        field_exact_matches=total_exact_matches,
        field_tolerance_matches=total_tolerance_matches,
        field_exact_match_rate=field_exact_rate,
        field_tolerance_match_rate=field_tol_rate,
        field_omissions=total_omissions,
        field_omission_rate=field_omiss_rate,
        unexpected_predictions=total_unexpected,
        mean_cer=mean_cer,
        mean_wer=mean_wer,
        mean_ingredient_completeness=mean_comp,
        mean_ingredient_recall=mean_recall,
        mean_ingredient_precision=mean_precision,
        mean_ingredient_jaccard=mean_jaccard,
        metrics_by_nutrient=metrics_by_nutrient,
        metrics_by_condition=metrics_by_condition,
        execution_timestamp=timestamp,
        status=overall_status,
        disclaimer=(
            "Benchmark scores reflect offline Tesseract OCR and deterministic "
            "parsing against real packaging photos. Field tolerances and CER/WER "
            "are computed with strict separation between declared ground truth and omissions."
        ),
        sample_results=sample_results,
    )
