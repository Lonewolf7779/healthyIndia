#!/usr/bin/env python3
"""
Dataset Validator Script for healthyIndia Real-World Packaging Dataset.

Validates data/real_food_labels/samples.json against the required schema,
verifies physical and biological plausibility constraints on ground truth
declarations, and rigorously audits physical image cryptographic provenance.

Enforces clear separation:
1. Schema and Biological Plausibility Validation.
2. Evidential Provenance Validation (physical packaging images on disk).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if REPO_ROOT.name == "services":
    REPO_ROOT = REPO_ROOT.parent
DEFAULT_DATASET_PATH = REPO_ROOT / "data" / "real_food_labels" / "samples.json"
DEFAULT_IMAGES_DIR = REPO_ROOT / "data" / "real_food_labels" / "images"

# Constants
EMPTY_STRING_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

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
VALID_VERIFICATION_STATUSES = {
    "DOUBLE_VERIFIED",
    "SCHEMA_VERIFIED_EVIDENCE_PENDING",
    "UNVERIFIED",
}


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


def validate_image_provenance(sample: dict, images_dir: Path) -> tuple[bool, str]:
    """
    Rigorously verifies physical photograph presence, non-zero file size,
    and SHA-256 digest integrity on disk.
    """
    sid = sample.get("sample_id", "UNKNOWN")
    img_filename = sample.get("image_filename")
    recorded_sha = sample.get("image_sha256")

    # Reject empty-string placeholder hash
    if recorded_sha == EMPTY_STRING_SHA256:
        return (
            False,
            f"[{sid}] Recorded image_sha256 is the hash of an empty byte string: "
            f"'{EMPTY_STRING_SHA256}'. Placeholder hashes are forbidden.",
        )

    if not img_filename:
        return False, f"[{sid}] Missing image_filename in sample record."

    img_path = images_dir / img_filename
    if not img_path.is_file():
        return False, f"[{sid}] Physical image file '{img_filename}' not found at '{images_dir}'."

    file_size = img_path.stat().st_size
    if file_size == 0:
        return False, f"[{sid}] Physical image file '{img_filename}' is 0 bytes (empty file)."

    if recorded_sha is None:
        return (
            False,
            f"[{sid}] Physical image exists on disk, but recorded image_sha256 is null in metadata.",
        )

    # Compute SHA-256 of physical image file
    hasher = hashlib.sha256()
    with open(img_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    computed_sha = hasher.hexdigest()

    if computed_sha.lower() != recorded_sha.lower():
        return (
            False,
            f"[{sid}] Cryptographic SHA-256 mismatch for '{img_filename}': "
            f"recorded '{recorded_sha}', computed '{computed_sha}'.",
        )

    return True, ""


def validate_dataset(
    filepath: Path,
    images_dir: Path | None = None,
    require_images: bool = False,
) -> tuple[bool, dict]:
    """
    Loads and validates dataset against all structural, plausibility, and provenance gates.

    Returns:
        tuple[success: bool, summary: dict]
    """
    if images_dir is None:
        images_dir = filepath.parent / "images"

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

    verified_images_count = 0
    pending_images_count = 0
    double_verified_count = 0
    schema_only_count = 0

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

        # Track missing nutrient omissions
        nutrients = gt.get("nutrients", {})
        for nut in expected_nutrients:
            if nutrients.get(nut) is None:
                missing_nutrient_counts[nut] = missing_nutrient_counts.get(nut, 0) + 1

        # Biological plausibility validation
        plaus_errors = validate_sample_plausibility(sample)
        all_errors.extend(plaus_errors)

        # Verification block validation
        verif = sample.get("verification", {})
        status = verif.get("status")
        if status not in VALID_VERIFICATION_STATUSES:
            all_errors.append(
                f"[{sid}] Invalid verification status '{status}'. Must be one of {sorted(VALID_VERIFICATION_STATUSES)}"
            )

        # Detect empty-string placeholder hash
        recorded_sha = sample.get("image_sha256")
        if recorded_sha == EMPTY_STRING_SHA256:
            all_errors.append(
                f"[{sid}] Sample contains empty-string SHA-256 placeholder hash ('{EMPTY_STRING_SHA256}'). "
                f"Use null when physical photographs are not bundled."
            )

        # Strict evidential provenance validation
        img_ok, img_err = validate_image_provenance(sample, images_dir)
        if img_ok:
            verified_images_count += 1
        else:
            pending_images_count += 1

        if status == "DOUBLE_VERIFIED":
            double_verified_count += 1
            # DOUBLE_VERIFIED strictly requires physical photograph on disk
            if not img_ok:
                all_errors.append(
                    f"[{sid}] Provenance Misrepresentation: Sample claims status 'DOUBLE_VERIFIED', "
                    f"but photographic evidence is invalid or missing on disk: {img_err}"
                )
        elif status == "SCHEMA_VERIFIED_EVIDENCE_PENDING":
            schema_only_count += 1
            if require_images and not img_ok:
                all_errors.append(
                    f"[{sid}] Strict provenance failure (--require-images active): {img_err}"
                )

    summary = {
        "total_samples": len(samples),
        "categories_covered": len(categories),
        "categories_list": sorted(categories),
        "packaging_formats": sorted(formats),
        "dual_column_count": dual_column_count,
        "missing_nutrient_counts": missing_nutrient_counts,
        "verified_images_count": verified_images_count,
        "pending_images_count": pending_images_count,
        "double_verified_count": double_verified_count,
        "schema_only_count": schema_only_count,
        "errors": all_errors,
        "schema_passed": len([e for e in all_errors if "Provenance" not in e and "Strict" not in e])
        == 0,
        "provenance_passed": verified_images_count == len(samples) if require_images else True,
    }
    is_success = len(all_errors) == 0
    return is_success, summary


def main():
    parser = argparse.ArgumentParser(
        description="Dataset Integrity & Provenance Validator for healthyIndia"
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to samples.json dataset file.",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=DEFAULT_IMAGES_DIR,
        help="Path to directory containing packaging photographs.",
    )
    parser.add_argument(
        "--require-images",
        action="store_true",
        help="Require physical photograph files on disk for all records (strict evaluation).",
    )
    args = parser.parse_args()

    print("=" * 75)
    print("healthyIndia Real-World Dataset Integrity & Provenance Validator")
    print(f"Dataset Target:   {args.dataset_path}")
    print(f"Images Directory: {args.images_dir}")
    print(f"Strict Images:    {'ENABLED' if args.require_images else 'DISABLED'}")
    print("=" * 75)

    success, summary = validate_dataset(
        filepath=args.dataset_path,
        images_dir=args.images_dir,
        require_images=args.require_images,
    )

    if not success and "error" in summary:
        print(f"FATAL ERROR: {summary['error']}")
        sys.exit(1)

    print(f"Total Samples Evaluated:      {summary['total_samples']}")
    print(f"Categories Represented:       {summary['categories_covered']}/10")
    print("Categories:")
    for cat in summary["categories_list"]:
        print(f"  - {cat}")
    print(f"Packaging Formats:            {', '.join(summary['packaging_formats'])}")
    print(f"Dual-Column Samples:          {summary['dual_column_count']}")
    print("\nMissing Nutrient Declarations Preserved (Physical label omissions):")
    for nut, count in sorted(summary["missing_nutrient_counts"].items()):
        print(f"  - {nut}: {count} sample(s) with missing (null) values")

    print("\n" + "-" * 75)
    print("EVIDENTIAL PROVENANCE AUDIT:")
    print(
        f"  - Double-Verified Samples (Image + Transcription): {summary['double_verified_count']}"
    )
    print(f"  - Schema-Verified / Evidence-Pending Samples:     {summary['schema_only_count']}")
    print(
        f"  - Physical Photographs Verified on Disk:          {summary['verified_images_count']}/{summary['total_samples']}"
    )
    print(
        f"  - Physical Photographs Pending / Not Bundled:     {summary['pending_images_count']}/{summary['total_samples']}"
    )
    print("-" * 75)

    if summary["errors"]:
        print("\nVALIDATION FAILURES DETECTED:")
        for err in summary["errors"]:
            print(f"  ❌ {err}")
        print("\n" + "=" * 75)
        print("RESULT: FAILED")
        print("=" * 75)
        sys.exit(1)
    else:
        print("\n" + "=" * 75)
        if summary["verified_images_count"] == summary["total_samples"]:
            print("RESULT: ALL SAMPLES PASSED SCHEMA, PLAUSIBILITY, AND EVIDENTIAL PROVENANCE")
            print("STATUS: DOUBLE_VERIFIED (Photographs cryptographically verified on disk)")
        else:
            print("RESULT: ALL SAMPLES PASSED SCHEMA & PLAUSIBILITY CONSTRAINTS")
            print(
                "STATUS: SCHEMA_VERIFIED_EVIDENCE_PENDING (Physical photographs not bundled in repo)"
            )
            print("NOTE: Real-world physical camera OCR recognition remains UNMEASURED.")
        print("=" * 75)
        sys.exit(0)


if __name__ == "__main__":
    main()
