import re
from urllib.parse import urlparse

from app.ingredients.loader import load_ingredient_reference
from scripts.verify_data_integrity import audit_ingredient_data


def test_additive_dataset_provenance_and_schema() -> None:
    # 1. Test loader loads properly and indexes
    ins_idx, alias_idx = load_ingredient_reference()
    assert len(ins_idx) > 0
    assert len(alias_idx) > 0

    all_entries = {entry.id: entry for entry in list(ins_idx.values()) + list(alias_idx.values())}
    assert len(all_entries) >= 8, f"Expected at least 8 additives, found {len(all_entries)}"

    for entry_id, entry in all_entries.items():
        assert entry.id, "Missing entry ID"
        assert entry.canonical_name, f"Missing canonical name for {entry_id}"
        assert len(entry.functional_classes) > 0, f"Missing functional classes for {entry_id}"
        assert "India" in entry.jurisdiction, f"Expected India jurisdiction for {entry_id}"

        # INS / E syntax validation
        if entry.ins_number:
            assert re.match(r"^INS\s+\d+[a-z]?(\([i|v|x]+\))?$", entry.ins_number, re.IGNORECASE), (
                f"Invalid INS format '{entry.ins_number}' in {entry_id}"
            )
        if entry.e_number:
            assert re.match(r"^E\s*\d+[a-z]?(\([i|v|x]+\))?$", entry.e_number, re.IGNORECASE), (
                f"Invalid E number format '{entry.e_number}' in {entry_id}"
            )

        # Scientific provenance
        assert entry.chemical_identity, f"Missing chemical identity in {entry_id}"
        assert entry.acceptable_daily_intake, f"Missing ADI in {entry_id}"
        assert entry.population_sensitivities, f"Missing population sensitivities in {entry_id}"

        # Source citations verification
        assert len(entry.sources) >= 2, (
            f"Expected at least 2 primary sources for {entry_id}, found {len(entry.sources)}"
        )
        orgs = [s.organization for s in entry.sources if s.organization]
        assert any("FSSAI" in org for org in orgs), (
            f"Missing FSSAI regulatory source for {entry_id}"
        )
        assert any(
            any(intl in org for intl in ("WHO", "JECFA", "FAO", "IARC", "Codex")) for org in orgs
        ), f"Missing international authority source (WHO/JECFA/Codex) for {entry_id}"

        for src in entry.sources:
            parsed = urlparse(src.url)
            assert parsed.scheme in ("http", "https") and parsed.netloc, (
                f"Invalid URL '{src.url}' in {entry_id}"
            )
            assert src.retrieval_date, f"Missing retrieval_date in {entry_id}"
            assert src.publication_date, f"Missing publication_date in {entry_id}"
            assert src.section_or_regulation, f"Missing section_or_regulation in {entry_id}"
            assert src.supported_claims, f"Missing supported_claims in {entry_id}"


def test_audit_ingredient_data_validator_passes() -> None:
    audit_results = audit_ingredient_data()
    assert audit_results["total_records"] >= 8
    assert audit_results["verified_count"] >= 8
    assert len(audit_results["completeness_errors"]) == 0
    assert len(audit_results["citation_errors"]) == 0
    assert len(audit_results["scientific_errors"]) == 0
    assert len(audit_results["regulatory_errors"]) == 0
    assert len(audit_results["all_errors"]) == 0
    assert len(audit_results["warnings"]) == 0


def test_aspartame_consumption_claim_regression() -> None:
    ins_idx, _ = load_ingredient_reference()
    aspartame = ins_idx.get("951")
    assert aspartame is not None
    ev = aspartame.health_effects_evidence

    # Regression: ensure the erroneous "12-36 cans" is never present
    assert "12–36" not in ev
    assert "12-36" not in ev

    # Regression: correct calculation for 60 kg adult at 40 mg/kg bw = 2,400 mg
    assert "2,400 mg" in ev
    # 200 mg/can -> 12 cans; 300 mg/can -> 8 cans
    assert "12 cans" in ev
    assert "8 cans" in ev
    # Reaching vs exceeding distinction
    assert "reaching the adi is not equivalent to exceeding it" in ev.lower()
    assert "more than" in ev.lower()

    # Check everyday explanation structure
    exp = aspartame.everyday_quantity_explanation
    assert exp is not None
    assert exp["original_value"] == 40.0
    assert exp["guidance_type"] == "acceptable_daily_intake"
    assert "2,400 mg" in exp["everyday_comparison"]
    assert "safety boundary" in exp["plain_language_summary"].lower()


def test_no_unsupported_absolute_safety_claims() -> None:
    ins_idx, alias_idx = load_ingredient_reference()
    all_entries = {entry.id: entry for entry in list(ins_idx.values()) + list(alias_idx.values())}

    prohibited = [
        "non-toxic at all",
        "non-toxic at permitted",
        "completely harmless",
        "zero risk under any condition",
    ]

    for entry_id, entry in all_entries.items():
        text = (entry.health_effects_evidence + " " + entry.regulatory_status).lower()
        for phrase in prohibited:
            assert phrase not in text, (
                f"Record '{entry_id}' contains unsupported absolute '{phrase}'"
            )
