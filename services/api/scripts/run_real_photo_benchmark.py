#!/usr/bin/env python3
"""
CLI Runner for healthyIndia Physical-Photograph Food Label OCR Benchmark.

Evaluates local Tesseract OCR and deterministic parsing against real photographs
of packaged-food labels, computing field-level exact matches, tolerance-based matches,
omission rates, unexpected prediction rates, Levenshtein CER/WER, and condition breakdowns.

When physical images are not bundled in the repository, reports UNMEASURED fail-closed
with exact denominator 0 without fabricating synthetic accuracy claims.
"""

import argparse
import json
import sys
from pathlib import Path

# Add services/api to python path
API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.extraction.benchmark import (  # noqa: E402
    RealPhotoBenchmarkSummary,
    evaluate_physical_dataset,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if REPO_ROOT.name == "services":
    REPO_ROOT = REPO_ROOT.parent

DEFAULT_DATASET = REPO_ROOT / "data" / "real_food_labels" / "samples.json"
DEFAULT_IMAGES = REPO_ROOT / "data" / "real_food_labels" / "images"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "docs" / "real_photo_benchmark_results.json"


def print_terminal_report(summary: RealPhotoBenchmarkSummary) -> None:
    """Renders a clean, transparent terminal summary table."""
    print("=" * 80)
    print("healthyIndia Physical-Photo OCR & Deterministic Parsing Benchmark")
    print(f"Executed: {summary.execution_timestamp}")
    print(f"Overall Status: {summary.status}")
    print("=" * 80)
    print(f"Total Dataset Records:          {summary.total_samples_in_dataset}")
    print(f"Physical Images on Disk:        {summary.images_bundled_on_disk}")
    print(f"Samples Evaluated:              {summary.samples_evaluated}")
    print(f"Samples Passed:                 {summary.samples_passed}")
    print(f"Samples Failed:                 {summary.samples_failed}")

    if summary.samples_evaluated == 0:
        print("\n" + "-" * 80)
        print("EVIDENTIAL STATUS: UNMEASURED")
        print(f"Notice: {summary.disclaimer}")
        print("-" * 80)
        print("=" * 80)
        return

    print("\n" + "-" * 80)
    print("MACRO-LEVEL SUMMARY METRICS")
    print("-" * 80)
    print(
        f"Sample Pass Rate:               {summary.sample_pass_rate}% "
        f"({summary.samples_passed}/{summary.samples_evaluated})"
    )
    print(f"Image Processing Success Rate:  {summary.image_processing_success_rate}%")
    print(f"Total Declared Nutrient Fields: {summary.total_declared_fields}")
    print(
        f"Field Exact Match Rate:         {summary.field_exact_match_rate}% "
        f"({summary.field_exact_matches}/{summary.total_declared_fields})"
    )
    print(
        f"Field Tolerance Match Rate:     {summary.field_tolerance_match_rate}% "
        f"({summary.field_tolerance_matches}/{summary.total_declared_fields})"
    )
    print(
        f"Field Omission Rate:            {summary.field_omission_rate}% "
        f"({summary.field_omissions}/{summary.total_declared_fields})"
    )
    print(f"Unexpected Predictions:         {summary.unexpected_predictions}")
    print(f"Mean Character Error Rate (CER): {summary.mean_cer}")
    print(f"Mean Word Error Rate (WER):      {summary.mean_wer}")
    print(f"Mean Ingredient Completeness:   {summary.mean_ingredient_completeness}")

    print("\n" + "-" * 80)
    print("FIELD-LEVEL ACCURACY BREAKDOWN")
    print("-" * 80)
    header = f"{'Nutrient Field':<20} | {'Decl':>4} | {'Exact':>5} | {'Tol%':>6} | {'Omiss%':>6} | {'MAE':>7} | {'MRE':>7}"
    print(header)
    print("-" * len(header))
    for field_name, m in summary.metrics_by_nutrient.items():
        exact_s = f"{m.exact_matches}"
        tol_s = f"{m.tolerance_match_rate:.1f}%" if m.tolerance_match_rate is not None else "N/A"
        omiss_s = f"{m.omission_rate:.1f}%" if m.omission_rate is not None else "N/A"
        mae_s = f"{m.mean_absolute_error:.2f}" if m.mean_absolute_error is not None else "N/A"
        mre_s = f"{m.mean_relative_error:.2f}" if m.mean_relative_error is not None else "N/A"
        print(
            f"{field_name:<20} | {m.declared_in_gt_count:>4} | {exact_s:>5} | {tol_s:>6} | {omiss_s:>6} | {mae_s:>7} | {mre_s:>7}"
        )

    if summary.metrics_by_condition:
        print("\n" + "-" * 80)
        print("PERFORMANCE GROUPED BY CAPTURE CONDITION")
        print("-" * 80)
        for cond, cstats in sorted(summary.metrics_by_condition.items()):
            print(
                f"  {cond:<25}: {cstats['passed']}/{cstats['evaluated']} passed ({cstats['pass_rate']}%)"
            )

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="healthyIndia Physical-Photo OCR Benchmark Runner")
    parser.add_argument(
        "--dataset-path", type=Path, default=DEFAULT_DATASET, help="Path to samples.json"
    )
    parser.add_argument(
        "--images-dir", type=Path, default=DEFAULT_IMAGES, help="Path to images directory"
    )
    parser.add_argument(
        "--output-json", type=Path, default=DEFAULT_OUTPUT_JSON, help="Path for JSON output"
    )
    args = parser.parse_args()

    try:
        summary = evaluate_physical_dataset(
            dataset_path=args.dataset_path, images_dir=args.images_dir
        )
    except Exception as exc:
        print(f"Benchmark execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print_terminal_report(summary)

    # Export machine-readable results
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2)
        print(f"Exported machine-readable results to: {args.output_json}")

    # Return success (0) even if UNMEASURED (since 0 evaluated is honest disclosure)
    # Fail (1) only if images were evaluated and pass criteria failed
    if summary.status == "FAIL":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
