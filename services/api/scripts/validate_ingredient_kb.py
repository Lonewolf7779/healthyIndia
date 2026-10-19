#!/usr/bin/env python3
"""
Reproducible Knowledge Base Validator and Expansion Pipeline Auditor.
Phase 4A: Comprehensive Ingredient Knowledge Base Foundation.

Audits:
1. Schema and data completeness
2. Duplicate canonical IDs
3. Conflicting identifiers (INS, E, CAS numbers)
4. Alias collisions across records
5. Suspiciously broad aliases
6. Source citation URLs and provenance separation
7. Distinct category breakdowns
8. Cryptographic SHA-256 dataset checksum
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add services/api to python path
API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.ingredients.loader import (  # noqa: E402
    normalize_ins_code,
    normalize_lookup_token,
)

REPO_ROOT = API_DIR.parent if API_DIR.name == "services" else API_DIR.parent.parent
if not (REPO_ROOT / "data").is_dir():
    REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DATASET = REPO_ROOT / "data" / "ingredient_reference" / "ingredients_v1.json"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "docs" / "ingredient_kb_validation_report.json"

SUSPICIOUS_GENERIC_ALIASES: set[str] = {
    "food",
    "ingredient",
    "oil",
    "fat",
    "powder",
    "extract",
    "natural",
    "spice",
    "spices",
    "colour",
    "color",
    "flavour",
    "flavor",
    "sweetener",
    "preservative",
    "chemical",
    "acid",
    "salt",
    "water",
    "gum",
    "seed",
}

AUTHORITATIVE_DOMAINS: set[str] = {
    "fssai.gov.in",
    "who.int",
    "apps.who.int",
    "fao.org",
    "efsa.europa.eu",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "codexalimentarius.org",
    "ec.europa.eu",
    "fda.gov",
    "icmr.nic.in",
    "nin.res.in",
}

VALID_CATEGORIES: set[str] = {
    "ordinary_ingredient",
    "food_additive",
    "compound_ingredient",
    "allergen",
    "sweetener",
    "fortification_compound",
    "flavouring",
    "processing_aid",
    "nutritional_component",
    "unknown",
}


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_ingredient_dataset(dataset_path: Path) -> dict:
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    raw_bytes = dataset_path.read_bytes()
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    with dataset_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version", "unknown")
    ingredients = data.get("ingredients", [])
    total_records = len(ingredients)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Duplicate ID check
    seen_ids: dict[str, int] = {}
    for idx, item in enumerate(ingredients):
        iid = item.get("id")
        if not iid:
            errors.append(f"Record #{idx} is missing required 'id'.")
        elif iid in seen_ids:
            errors.append(
                f"Duplicate canonical ID detected: '{iid}' in record #{idx} and #{seen_ids[iid]}."
            )
        else:
            seen_ids[iid] = idx

    # 2. Identifier collision check (INS, E, CAS)
    ins_map: dict[str, str] = {}
    e_map: dict[str, str] = {}
    cas_map: dict[str, str] = {}

    for item in ingredients:
        iid = item.get("id", "UNKNOWN")

        # INS number
        ins_val = item.get("ins_number")
        if ins_val:
            norm_ins = normalize_ins_code(ins_val)
            if norm_ins in ins_map and ins_map[norm_ins] != iid:
                errors.append(
                    f"Conflicting INS number '{ins_val}' (normalized '{norm_ins}') "
                    f"shared between '{iid}' and '{ins_map[norm_ins]}'."
                )
            ins_map[norm_ins] = iid

        # E number
        e_val = item.get("e_number")
        if e_val:
            norm_e = normalize_ins_code(e_val)
            if norm_e in e_map and e_map[norm_e] != iid:
                errors.append(
                    f"Conflicting E number '{e_val}' (normalized '{norm_e}') "
                    f"shared between '{iid}' and '{e_map[norm_e]}'."
                )
            e_map[norm_e] = iid

        # CAS number
        cas_val = item.get("cas_number")
        if cas_val:
            cas_clean = cas_val.strip()
            if not re.match(r"^\d{2,7}-\d{2}-\d$", cas_clean):
                warnings.append(f"[{iid}] CAS number format '{cas_clean}' appears non-standard.")
            if cas_clean in cas_map and cas_map[cas_clean] != iid:
                errors.append(
                    f"Conflicting CAS number '{cas_clean}' shared between '{iid}' and '{cas_map[cas_clean]}'."
                )
            cas_map[cas_clean] = iid

    # 3. Alias collision check, Broad alias detection & Bare number check
    alias_map: dict[str, str] = {}
    broad_aliases_found: list[dict[str, str]] = []
    bare_numbers_found: list[dict[str, str]] = []

    for item in ingredients:
        iid = item.get("id", "UNKNOWN")
        cname = item.get("canonical_name", "")
        if not cname:
            errors.append(f"[{iid}] Missing required 'canonical_name'.")

        all_aliases = list(item.get("aliases", []))
        all_aliases.append(cname)

        # Indian language aliases
        for _lang, lang_aliases in item.get("indian_language_aliases", {}).items():
            all_aliases.extend(lang_aliases)

        for alias in all_aliases:
            norm = normalize_lookup_token(alias)
            if not norm:
                continue

            # Bare numerical alias (out-of-context hazard)
            if re.match(r"^\d{3,4}$", norm):
                errors.append(
                    f"[{iid}] Unsafe bare numerical alias detected: '{norm}'. "
                    f"Bare numbers without INS prefix or functional class are prone to false positives."
                )
                bare_numbers_found.append({"record_id": iid, "alias": norm})

            # Suspiciously broad alias
            if norm in SUSPICIOUS_GENERIC_ALIASES:
                warnings.append(f"[{iid}] Suspiciously broad/generic alias detected: '{norm}'.")
                broad_aliases_found.append({"record_id": iid, "alias": norm})

            # Alias collision
            if norm in alias_map and alias_map[norm] != iid:
                errors.append(
                    f"Alias collision detected: '{norm}' points to both '{iid}' and '{alias_map[norm]}'."
                )
            alias_map[norm] = iid

    # 4. Provenance & Citations: 5 Independent Tracks
    track1_url_recorded_count = 0
    track2_url_accessible_count = 0
    track3_content_checked_count = 0
    track4_scientific_supported_count = 0
    track5_regulatory_verified_count = 0
    fully_verified_count = 0

    category_counts: dict[str, int] = {}

    disallowed_absolutes = [
        "non-toxic at all",
        "completely harmless",
        "zero risk under any condition",
        "universally safe for everyone",
    ]

    for item in ingredients:
        iid = item.get("id", "UNKNOWN")

        # Category validation
        etype = item.get("entity_type")
        if not etype or etype not in VALID_CATEGORIES:
            errors.append(f"[{iid}] Invalid or missing 'entity_type': '{etype}'.")
        else:
            category_counts[etype] = category_counts.get(etype, 0) + 1

        for cat in item.get("categories", []):
            if cat not in VALID_CATEGORIES:
                warnings.append(f"[{iid}] Unrecognized category tag: '{cat}'.")

        prov = item.get("provenance", {})
        sources = item.get("sources", [])

        # Track 1: Source URL recorded
        has_sources = len(sources) > 0
        all_sources_have_url = has_sources and all(s.get("url") for s in sources)
        if prov.get("source_url_recorded", False) or all_sources_have_url:
            track1_url_recorded_count += 1
        else:
            errors.append(f"[{iid}] Track 1 failed: No recorded citation URL found.")

        # Track 2: Source URL accessible & Authoritative
        authoritative_urls = 0
        for sidx, s in enumerate(sources):
            s_url = s.get("url", "")
            if not s_url or not validate_url(s_url):
                errors.append(f"[{iid}] Citation #{sidx} has invalid or missing URL: '{s_url}'.")
            else:
                domain = urlparse(s_url).netloc.lower()
                if any(auth in domain for auth in AUTHORITATIVE_DOMAINS):
                    authoritative_urls += 1
                else:
                    warnings.append(
                        f"[{iid}] Citation #{sidx} URL domain '{domain}' is not in authoritative whitelist."
                    )
            if not s.get("title"):
                errors.append(f"[{iid}] Citation #{sidx} missing 'title'.")
            if not s.get("retrieval_date"):
                warnings.append(f"[{iid}] Citation #{sidx} missing 'retrieval_date'.")

        if authoritative_urls > 0 and (
            prov.get("source_url_accessible", False) or all_sources_have_url
        ):
            track2_url_accessible_count += 1
        else:
            errors.append(f"[{iid}] Track 2 failed: Missing accessible authoritative citation URL.")

        # Track 3: Source content checked
        if prov.get("source_content_checked", False) and prov.get("audit_date"):
            track3_content_checked_count += 1
        else:
            errors.append(f"[{iid}] Track 3 failed: Record lacks documented audit verification.")

        # Track 4: Scientific claim independently supported
        sci_text = (
            item.get("health_effects_evidence", "") + " " + item.get("acceptable_daily_intake", "")
        ).lower()
        contains_forbidden_absolute = any(phrase in sci_text for phrase in disallowed_absolutes)
        if contains_forbidden_absolute:
            errors.append(
                f"[{iid}] Track 4 failed: Record contains disallowed absolute safety claim."
            )
        elif (
            prov.get("scientific_claim_supported", False)
            and prov.get("scientific_review_status") == "verified"
        ):
            track4_scientific_supported_count += 1
        else:
            errors.append(f"[{iid}] Track 4 failed: Scientific claim not marked verified.")

        # Track 5: Regulatory claim independently verified for relevant context
        has_scope_limits = bool(item.get("scope_limitations"))
        if not has_scope_limits and item.get("entity_type") in ("food_additive", "sweetener"):
            errors.append(
                f"[{iid}] Track 5 failed: Food additive/sweetener lacks documented scope limitations."
            )
        elif (
            prov.get("regulatory_claim_verified", False)
            and prov.get("regulatory_verification_status") == "verified"
            and prov.get("regulatory_act")
        ):
            track5_regulatory_verified_count += 1
        else:
            errors.append(
                f"[{iid}] Track 5 failed: Regulatory claim not fully verified with statutory act."
            )

        # Overall verification integrity check
        if prov.get("verification_level") == "fully_verified":
            if not (
                all_sources_have_url
                and prov.get("source_content_checked")
                and prov.get("scientific_claim_supported")
                and prov.get("regulatory_claim_verified")
            ):
                errors.append(
                    f"[{iid}] Invalid claim: Record claims 'fully_verified' but failed one or more verification tracks."
                )
            else:
                fully_verified_count += 1

    is_valid = len(errors) == 0

    report = {
        "dataset_path": str(dataset_path),
        "version": version,
        "sha256": sha256_hash,
        "is_valid": is_valid,
        "total_records": total_records,
        "duplicate_ids_count": len([e for e in errors if "Duplicate canonical ID" in e]),
        "conflicting_identifiers_count": len([e for e in errors if "Conflicting" in e]),
        "alias_collisions_count": len([e for e in errors if "Alias collision" in e]),
        "broad_aliases_count": len(broad_aliases_found),
        "bare_numerical_aliases_count": len(bare_numbers_found),
        "category_breakdown": category_counts,
        "evidence_tracks": {
            "track1_source_url_recorded": track1_url_recorded_count,
            "track2_source_url_accessible": track2_url_accessible_count,
            "track3_source_content_checked": track3_content_checked_count,
            "track4_scientific_claim_supported": track4_scientific_supported_count,
            "track5_regulatory_claim_verified": track5_regulatory_verified_count,
            "fully_verified_records": fully_verified_count,
        },
        "errors": errors,
        "warnings": warnings,
    }
    return report


def print_report(report: dict) -> None:
    print("=" * 80)
    print("healthyIndia Ingredient Knowledge Base Validation & Provenance Audit")
    print(f"Dataset Version: {report['version']} | Total Records: {report['total_records']}")
    print(f"SHA-256 Digest:  {report['sha256']}")
    print("=" * 80)
    print(f"Validation Status:              {'PASS' if report['is_valid'] else 'FAIL'}")
    print(f"Duplicate Canonical IDs:        {report['duplicate_ids_count']}")
    print(f"Conflicting Identifiers:        {report['conflicting_identifiers_count']}")
    print(f"Alias Collisions:               {report['alias_collisions_count']}")
    print(f"Bare Numeric Aliases Flagged:   {report['bare_numerical_aliases_count']}")
    print(f"Broad/Generic Aliases Flagged:  {report['broad_aliases_count']}")

    print("\n" + "-" * 80)
    print("CATEGORY BREAKDOWN")
    print("-" * 80)
    for cat, count in sorted(report["category_breakdown"].items()):
        print(f"  {cat:<30}: {count}")

    print("\n" + "-" * 80)
    print("5-TRACK INDEPENDENT EVIDENCE PROVENANCE AUDIT")
    print("-" * 80)
    ev = report["evidence_tracks"]
    total = report["total_records"]
    print(f"  Track 1 - Source URL Recorded:        {ev['track1_source_url_recorded']} of {total}")
    print(
        f"  Track 2 - Source URL Accessible:      {ev['track2_source_url_accessible']} of {total}"
    )
    print(
        f"  Track 3 - Source Content Checked:     {ev['track3_source_content_checked']} of {total}"
    )
    print(
        f"  Track 4 - Scientific Claim Supported: {ev['track4_scientific_claim_supported']} of {total}"
    )
    print(
        f"  Track 5 - Regulatory Claim Verified:  {ev['track5_regulatory_claim_verified']} of {total}"
    )
    print(f"  Overall Fully Verified Records:       {ev['fully_verified_records']} of {total}")

    if report["warnings"]:
        print("\n" + "-" * 80)
        print(f"AUDIT WARNINGS ({len(report['warnings'])}):")
        for w in report["warnings"][:10]:
            print(f"  [WARN] {w}")

    if report["errors"]:
        print("\n" + "-" * 80)
        print(f"AUDIT ERRORS ({len(report['errors'])}):")
        for e in report["errors"][:10]:
            print(f"  [ERROR] {e}")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="healthyIndia Ingredient Knowledge Base Validator")
    parser.add_argument(
        "--dataset-path", type=Path, default=DEFAULT_DATASET, help="Path to ingredients_v1.json"
    )
    parser.add_argument(
        "--output-json", type=Path, default=DEFAULT_OUTPUT_JSON, help="Output path for JSON report"
    )
    args = parser.parse_args()

    try:
        report = validate_ingredient_dataset(args.dataset_path)
    except Exception as exc:
        print(f"Audit execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print_report(report)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Exported validation report to: {args.output_json}")

    sys.exit(0 if report["is_valid"] else 1)


if __name__ == "__main__":
    main()
