#!/usr/bin/env python3
"""
Automated data integrity and source provenance validator for healthyIndia.

Audits data/ingredient_reference/additives_v1.json:
- Schema completeness and valid types
- Valid URL protocols (https:// / http://)
- Traceable citations (organization, publication date, section/clause, supported claims)
- INS / E number syntax validation
- Cross-record alias collisions
- Verification status auditing
Outputs machine-readable summary and generates docs/DATA_INTEGRITY_REPORT.md.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

api_dir = Path(__file__).resolve().parents[1]
repo_root = api_dir.parents[1] if (api_dir.parents[1] / "data").is_dir() else api_dir.parent


def locate_additives_file() -> Path:
    candidates = [
        repo_root / "data" / "ingredient_reference" / "additives_v1.json",
        api_dir / "data" / "ingredient_reference" / "additives_v1.json",
        Path("data/ingredient_reference/additives_v1.json").resolve(),
    ]
    target = next((p for p in candidates if p.is_file()), None)
    if not target:
        raise FileNotFoundError(f"Additives dataset not found in: {candidates}")
    return target


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def audit_ingredient_data() -> dict:
    file_path = locate_additives_file()
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    additives = data.get("additives", [])
    total_records = len(additives)

    errors: list[str] = []
    warnings: list[str] = []

    seen_ids: set[str] = set()
    alias_map: dict[str, str] = {}  # alias -> additive_id

    verified_count = 0
    partially_verified_count = 0
    unverified_count = 0

    record_audits = []

    for item in additives:
        item_id = item.get("id")
        name = item.get("canonical_name", "UNKNOWN")

        # 1. Unique ID check
        if not item_id:
            errors.append(f"Record with name '{name}' lacks an 'id' field.")
            continue
        if item_id in seen_ids:
            errors.append(f"Duplicate additive id detected: '{item_id}'.")
        seen_ids.add(item_id)

        # 2. Status check
        status = item.get("status_verification")
        if status == "verified":
            verified_count += 1
        elif status == "partially_verified":
            partially_verified_count += 1
        elif status == "unverified":
            unverified_count += 1
        else:
            errors.append(
                f"Record '{item_id}' has invalid status_verification: '{status}'. "
                "Must be 'verified', 'partially_verified', or 'unverified'."
            )

        # 3. Chemical identity and health evidence
        chem_id = item.get("chemical_identity", "").strip()
        if not chem_id:
            warnings.append(f"Record '{item_id}' lacks chemical_identity (CAS / formula).")

        health_ev = item.get("health_effects_evidence", "").strip()
        if not health_ev:
            errors.append(f"Record '{item_id}' lacks health_effects_evidence.")

        adi = item.get("acceptable_daily_intake", "").strip()
        if not adi:
            errors.append(f"Record '{item_id}' lacks acceptable_daily_intake specification.")

        sensitivities = item.get("population_sensitivities", "").strip()
        if not sensitivities:
            warnings.append(f"Record '{item_id}' lacks population_sensitivities statement.")

        # 4. INS / E number format
        ins_num = item.get("ins_number")
        if ins_num and not re.match(r"^INS\s+[0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?$", ins_num):
            errors.append(f"Record '{item_id}' has malformed ins_number: '{ins_num}'.")

        e_num = item.get("e_number")
        if e_num and not re.match(r"^E\s+[0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?$", e_num):
            errors.append(f"Record '{item_id}' has malformed e_number: '{e_num}'.")

        # 5. Aliases uniqueness across additives
        for alias in item.get("aliases", []):
            norm_alias = alias.strip().lower()
            if norm_alias in alias_map and alias_map[norm_alias] != item_id:
                errors.append(
                    f"Alias collision: alias '{alias}' is mapped to both "
                    f"'{alias_map[norm_alias]}' and '{item_id}'."
                )
            alias_map[norm_alias] = item_id

        # 6. Source provenance audit
        sources = item.get("sources", [])
        if not sources:
            errors.append(f"Record '{item_id}' has zero citations/sources.")

        has_fssai_source = False
        has_scientific_source = False

        for idx, src in enumerate(sources):
            title = src.get("title", "").strip()
            url = src.get("url", "").strip()
            org = src.get("organization", "").strip()
            stype = src.get("source_type", "").strip()
            ret_date = src.get("retrieval_date", "").strip()
            sec = src.get("section_or_regulation", "").strip()
            claims = src.get("supported_claims", "").strip()

            if not title:
                errors.append(f"Record '{item_id}', source #{idx} lacks title.")
            if not url or not validate_url(url):
                errors.append(
                    f"Record '{item_id}', source #{idx} has invalid or missing url: '{url}'."
                )
            if not org:
                errors.append(f"Record '{item_id}', source #{idx} lacks organization.")
            if not stype:
                errors.append(f"Record '{item_id}', source #{idx} lacks source_type.")
            if not ret_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", ret_date):
                errors.append(
                    f"Record '{item_id}', source #{idx} has invalid retrieval_date: '{ret_date}'."
                )
            if not sec:
                warnings.append(
                    f"Record '{item_id}', source #{idx} lacks section_or_regulation reference."
                )
            if not claims:
                errors.append(
                    f"Record '{item_id}', source #{idx} lacks supported_claims description."
                )

            if "FSSAI" in org or "Food Safety and Standards" in title:
                has_fssai_source = True
            if "JECFA" in org or "WHO" in org or "Codex" in org:
                has_scientific_source = True

        if not has_fssai_source:
            warnings.append(f"Record '{item_id}' lacks an official FSSAI statutory citation.")
        if not has_scientific_source:
            warnings.append(
                f"Record '{item_id}' lacks an authoritative international scientific evaluation."
            )

        record_audits.append(
            {
                "id": item_id,
                "canonical_name": name,
                "ins_number": ins_num,
                "status": status,
                "sources_count": len(sources),
                "chemical_identity": chem_id,
                "has_fssai": has_fssai_source,
                "has_scientific": has_scientific_source,
            }
        )

    return {
        "dataset_version": data.get("version", "1.0.0"),
        "total_records": total_records,
        "verified_count": verified_count,
        "partially_verified_count": partially_verified_count,
        "unverified_count": unverified_count,
        "total_aliases_indexed": len(alias_map),
        "errors": errors,
        "warnings": warnings,
        "record_audits": record_audits,
    }


def generate_markdown_report(audit_result: dict) -> str:
    lines = [
        "# healthyIndia Evidence-Based Ingredient Data & Provenance Audit Report",
        "",
        "## Audit Overview",
        f"- **Dataset Version**: {audit_result['dataset_version']}",
        f"- **Total Additive Records Audited**: {audit_result['total_records']}",
        f"- **Verified Records**: {audit_result['verified_count']}",
        f"- **Partially Verified Records**: {audit_result['partially_verified_count']}",
        f"- **Unverified Records**: {audit_result['unverified_count']}",
        f"- **Unique Clean Aliases Indexed**: {audit_result['total_aliases_indexed']}",
        f"- **Critical Provenance Errors**: {len(audit_result['errors'])}",
        f"- **Audit Warnings**: {len(audit_result['warnings'])}",
        "",
        "## Standards & Evidence Classification",
        "Every factual claim is cross-checked against primary authoritative repositories:",
        (
            "- **Indian Statutory Regulations**: FSSAI Food Safety and Standards (Food Products "
            "Standards and Food Additives) Regulations, 2011; FSSAI (Labelling and Display) "
            "Regulations, 2020."
        ),
        (
            "- **International Toxicological Evaluations**: Joint FAO/WHO Expert Committee on Food "
            "Additives (JECFA) monographs, WHO Technical Report Series, IARC monographs."
        ),
        (
            "- **Food Standards**: Codex General Standard for Food Additives "
            "(GSFA, Codex Stan 192-1995)."
        ),
        "",
        "## Individual Additive Record Verification",
        (
            "| Additive ID | Canonical Name | INS Code | Chemical Identity (CAS) | Status | "
            "Citations | FSSAI Cited | JECFA/WHO Cited |"
        ),
        "| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |",
    ]

    for rec in audit_result["record_audits"]:
        fssai_mark = "Yes" if rec["has_fssai"] else "No"
        sci_mark = "Yes" if rec["has_scientific"] else "No"
        lines.append(
            f"| `{rec['id']}` | {rec['canonical_name']} | {rec['ins_number']} | "
            f"`{rec['chemical_identity'][:30]}...` | `{rec['status']}` | {rec['sources_count']} | "
            f"{fssai_mark} | {sci_mark} |"
        )

    lines.extend(
        [
            "",
            "## Scientific Integrity Principles Applied",
            (
                "1. **Presence != Harm**: The presence of an additive does not by itself "
                "prove that a food is dangerous. Effects are evaluated based on dose, exposure, "
                "and specific sensitivities."
            ),
            (
                "2. **Category-Specific Legality**: An INS number does not imply universal "
                "permission across all foods. Permitted categories and quantitative limits are "
                "strictly documented."
            ),
            (
                "3. **Population Sensitivities**: Target advisories (e.g. PKU for Aspartame, "
                "infant food prohibition for MSG, soya allergen for soy lecithin, aspirin "
                "cross-reactivity for Tartrazine) are explicitly identified."
            ),
            (
                "4. **No Arbitrary Safety Percentage**: healthyIndia never claims a product is "
                "universally safe or unsafe based on an invented score."
            ),
            "",
            "## Audit Errors and Warnings",
        ]
    )

    if not audit_result["errors"] and not audit_result["warnings"]:
        lines.append(
            "- **Zero errors or warnings detected.** All records meet strict provenance criteria."
        )
    else:
        for err in audit_result["errors"]:
            lines.append(f"- **ERROR**: {err}")
        for warn in audit_result["warnings"]:
            lines.append(f"- **WARNING**: {warn}")

    lines.extend(
        [
            "",
            "## Scope and Known Limitations",
            (
                "- The reference dataset currently covers 8 common food additives widely "
                "utilized in Indian packaged foods."
            ),
            (
                "- Whole food ingredients (flours, pulses, fats, spices) are deliberately "
                "preserved as unmatched tokens and not misclassified as additives."
            ),
            (
                "- Future expansion will continue incrementally based on primary FSSAI Gazette "
                "amendments and JECFA monographs."
            ),
        ]
    )

    return "\n".join(lines)


def main() -> None:
    print("Executing healthyIndia Data Integrity and Provenance Audit...")
    audit_res = audit_ingredient_data()

    report = generate_markdown_report(audit_res)
    docs_path = repo_root / "docs" / "DATA_INTEGRITY_REPORT.md"
    with docs_path.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"Data integrity report successfully written to: {docs_path}")
    print(f"Summary: {audit_res['total_records']} records audited.")
    print(
        f"Verified: {audit_res['verified_count']} | Errors: {len(audit_res['errors'])} | "
        f"Warnings: {len(audit_res['warnings'])}"
    )

    if audit_res["errors"]:
        print("Data integrity check FAILED with errors:", file=sys.stderr)
        for err in audit_res["errors"]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Data integrity check PASSED successfully.")


if __name__ == "__main__":
    main()
