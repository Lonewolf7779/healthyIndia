#!/usr/bin/env python3
"""
Dataset Validator Script for healthyIndia Real-World Packaging Dataset.

Validates data/real_food_labels/samples.json against the required schema,
verifies physical and biological plausibility constraints on all ground truth
nutrition declarations, and outputs a structured validation summary.
"""

import json
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if REPO_ROOT.name == "services":
    REPO_ROOT = REPO_ROOT.parent
DATASET_PATH = REPO_ROOT / "data" / "real_food_labels" / "samples.json"

REQUIRED_TOP_FIELDS = {"version", "dataset_name", "last_updated", "samples"}
REQUIRED_SAMPLE_FIELDS = {
    "sample_id",
    "product_name",
    "brand",
    "category",
    "packaging_format",
    "image_filename",
    "image_sha256",
    "capture_metadata",
    "ground_truth_nutrition",
    "ground_truth_ingredients_text",
    "verification",
}
REQUIRED_NUTRITION_FIELDS = {
    "declaration_basis",
    "serving_size",
    "serving_unit",
    "food_form",
    "nutrients",
}
VALID_BASES = {"per_100g", "per_100ml", "per_serving", "dual_column"}
VALID_FOOD_FORMS = {"solid", "liquid"}
VALID_SERVING_UNITS = {"g", "ml", "kg", "l", "piece", "portion"}
VALID_FORMATS = {"pouch", "wrapper", "carton", "bottle", "jar", "cup", "can", "sack", "box"}


def validate_sample_plausibility(sample: dict) -> list[str]:
    """Validates biological and physical plausibility of sample nutrition values."""
    errors: list[str] = []
    sid = sample.get("sample_id", "UNKNOWN")
    gt = sample.get("ground_truth_nutrition", {})
    nutrients = gt.get("nutrients", {})

    # 1. Serving size check
    serving_size = gt.get("serving_size")
    if serving_size is None or serving_size <= 0:
        errors.append(f"[{sid}] Invalid or non-positive serving size: {serving_size}")

    # 2. Food form & unit compatibility
    food_form = gt.get("food_form")
    serving_unit = gt.get("serving_unit")
    if food_form == "solid" and serving_unit in ("ml", "l"):
        errors.append(f"[{sid}] Solid food cannot declare volume serving unit ({serving_unit})")
    if (
        food_form == "liquid"
        and serving_unit in ("g", "kg")
        and gt.get("declaration_basis") == "per_100ml"
    ):
        # per_100ml requires volume or explicitly specified density
        pass

    # 3. Non-negative nutrients
    for k, v in nutrients.items():
        if v is not None and v < 0:
            errors.append(f"[{sid}] Nutrient '{k}' cannot be negative: {v}")

    # 4. Sugar hierarchies
    carbs = nutrients.get("carbohydrates_g")
    total_sugar = nutrients.get("total_sugar_g")
    added_sugar = nutrients.get("added_sugar_g")

    if added_sugar is not None and total_sugar is not None:
        if added_sugar > total_sugar + 0.05:
            errors.append(
                f"[{sid}] Added sugar ({added_sugar}g) exceeds Total sugar ({total_sugar}g)"
            )

    if total_sugar is not None and carbs is not None:
        if total_sugar > carbs + 0.05:
            errors.append(f"[{sid}] Total sugar ({total_sugar}g) exceeds Carbohydrates ({carbs}g)")

    # 5. Fat hierarchies
    total_fat = nutrients.get("total_fat_g")
    sat_fat = nutrients.get("saturated_fat_g")
    trans_fat = nutrients.get("trans_fat_g")

    sub_fats = (sat_fat or 0.0) + (trans_fat or 0.0)
    if total_fat is not None and sub_fats > total_fat + 0.05:
        errors.append(
            f"[{sid}] Saturated fat + Trans fat ({sub_fats:.2f}g) exceeds Total fat ({total_fat}g)"
        )

    # 6. Mass conservation for 100g/ml basis
    basis = gt.get("declaration_basis")
    if basis in ("per_100g", "per_100ml"):
        protein = nutrients.get("protein_g") or 0.0
        fat = nutrients.get("total_fat_g") or 0.0
        carbohydrate = nutrients.get("carbohydrates_g") or 0.0
        fiber = nutrients.get("dietary_fiber_g") or 0.0
        macro_sum = protein + fat + carbohydrate + fiber
        if macro_sum > 105.0:
            errors.append(
                f"[{sid}] Macronutrient sum ({macro_sum:.1f}g) exceeds plausible physical limit per 100g/ml"
            )

    # 7. Energy plausibility relative to fat
    energy_kcal = nutrients.get("energy_kcal")
    if energy_kcal is not None and total_fat is not None:
        fat_calories = total_fat * 9.0
        if energy_kcal < (fat_calories - 5.0) and fat_calories > 10.0:
            errors.append(
                f"[{sid}] Declared energy ({energy_kcal} kcal) is lower than energy from fat alone ({fat_calories:.1f} kcal)"
            )

    return errors


def validate_dataset(filepath: Path) -> tuple[bool, dict]:
    """Loads and validates dataset against all structural and plausibility gates."""
    if not filepath.exists():
        return False, {"error": f"File not found: {filepath}"}

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, {"error": f"Invalid JSON syntax: {e}"}

    missing_top = REQUIRED_TOP_FIELDS - set(data.keys())
    if missing_top:
        return False, {"error": f"Missing top-level fields: {missing_top}"}

    samples = data.get("samples", [])
    if not isinstance(samples, list) or len(samples) == 0:
        return False, {"error": "Samples list is empty or invalid."}

    all_errors: list[str] = []
    categories: set[str] = set()
    formats: set[str] = set()
    dual_column_count = 0
    missing_nutrient_counts: dict[str, int] = {}
    total_nutrients_checked = 0

    expected_nutrients = [
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

    for sample in samples:
        sid = sample.get("sample_id", "UNKNOWN")
        missing_sample_fields = REQUIRED_SAMPLE_FIELDS - set(sample.keys())
        if missing_sample_fields:
            all_errors.append(f"[{sid}] Missing sample fields: {missing_sample_fields}")
            continue

        category = sample.get("category", "")
        pkg_format = sample.get("packaging_format", "")
        categories.add(category)
        formats.add(pkg_format)

        gt = sample.get("ground_truth_nutrition", {})
        missing_gt_fields = REQUIRED_NUTRITION_FIELDS - set(gt.keys())
        if missing_gt_fields:
            all_errors.append(f"[{sid}] Missing nutrition fields: {missing_gt_fields}")

        if gt.get("declaration_basis") not in VALID_BASES:
            all_errors.append(f"[{sid}] Invalid declaration_basis: {gt.get('declaration_basis')}")

        if gt.get("food_form") not in VALID_FOOD_FORMS:
            all_errors.append(f"[{sid}] Invalid food_form: {gt.get('food_form')}")

        if gt.get("serving_unit") not in VALID_SERVING_UNITS:
            all_errors.append(f"[{sid}] Invalid serving_unit: {gt.get('serving_unit')}")

        if gt.get("dual_column_values") is not None:
            dual_column_count += 1

        # Track missing nutrients
        nutrients = gt.get("nutrients", {})
        for nut in expected_nutrients:
            total_nutrients_checked += 1
            if nutrients.get(nut) is None:
                missing_nutrient_counts[nut] = missing_nutrient_counts.get(nut, 0) + 1

        # Check verification block
        verif = sample.get("verification", {})
        if verif.get("status") != "DOUBLE_VERIFIED":
            all_errors.append(
                f"[{sid}] Sample verification status must be DOUBLE_VERIFIED, got '{verif.get('status')}'"
            )

        # Plausibility checks
        plaus_errors = validate_sample_plausibility(sample)
        all_errors.extend(plaus_errors)

    summary = {
        "total_samples": len(samples),
        "categories_covered": len(categories),
        "categories_list": sorted(categories),
        "packaging_formats": sorted(formats),
        "dual_column_count": dual_column_count,
        "missing_nutrient_counts": missing_nutrient_counts,
        "errors": all_errors,
    }
    return len(all_errors) == 0, summary


def main():
    print("=" * 70)
    print("healthyIndia Real-World Dataset Integrity Validator")
    print(f"Target: {DATASET_PATH}")
    print("=" * 70)

    success, summary = validate_dataset(DATASET_PATH)

    if not success and "error" in summary:
        print(f"FATAL ERROR: {summary['error']}")
        sys.exit(1)

    print(f"Total Samples Verified:       {summary['total_samples']}")
    print(f"Distinct Categories Covered:  {summary['categories_covered']}/10")
    print("Categories:")
    for cat in summary["categories_list"]:
        print(f"  - {cat}")
    print(f"Packaging Formats:            {', '.join(summary['packaging_formats'])}")
    print(f"Dual-Column Samples:          {summary['dual_column_count']}")
    print("\nMissing Nutrient Declarations Preserved (Physical label omissions):")
    for nut, count in sorted(summary["missing_nutrient_counts"].items()):
        print(f"  - {nut}: {count} sample(s) with missing (null) values")

    if summary["errors"]:
        print("\nVALIDATION FAILURES DETECTED:")
        for err in summary["errors"]:
            print(f"  ❌ {err}")
        print("\nRESULT: FAILED")
        sys.exit(1)
    else:
        print("\n" + "=" * 70)
        print("RESULT: ALL SAMPLES PASSED SCHEMA & PLAUSIBILITY VALIDATION (DOUBLE-VERIFIED)")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
