"""
Phase 4A: Comprehensive Ingredient Knowledge Base Foundation Test Suite.

Automated verification of:
1. Backward compatibility with the original eight food additive records.
2. Generalized ingredient entities across distinct categories (ordinary food, sweetener,
   fortificant, allergen, processing aid, nutritional component, compound).
3. Exact canonical and Indian-language (Hindi Devanagari) alias matching.
4. Occurrence tracking and repeated ingredient mention preservation.
5. Parentheses-aware compound ingredient and nested sub-ingredient parsing.
6. Ambiguous functional-class terms isolation without guessing.
7. False-positive resistance against bare numbers and short generic words.
8. Collision detection: duplicate canonical IDs, conflicting identifiers, alias collisions.
9. Suspiciously broad alias warnings and provenance validation.
10. Multi-track evidence independence and API contract compatibility.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.ingredients.loader import (
    load_ingredient_reference,
    load_knowledge_base,
)
from app.ingredients.matcher import analyze_ingredients
from app.ingredients.models import IngredientCategory, MatchType
from scripts.validate_ingredient_kb import validate_ingredient_dataset


# ==============================================================================
# 1. BACKWARD COMPATIBILITY WITH ORIGINAL EIGHT ADDITIVES
# ==============================================================================
def test_backward_compatibility_original_eight_additives() -> None:
    """Verifies all 8 audited additives from Phase 1-3 load and match seamlessly."""
    ins_index, alias_index = load_ingredient_reference()

    expected_eight = [
        ("ins-621", "Monosodium L-glutamate", "621"),
        ("ins-951", "Aspartame", "951"),
        ("ins-150d", "Caramel IV - sulphite ammonia caramel", "150d"),
        ("ins-322", "Lecithins", "322"),
        ("ins-211", "Sodium benzoate", "211"),
        ("ins-330", "Citric acid", "330"),
        ("ins-102", "Tartrazine", "102"),
        ("ins-500ii", "Sodium hydrogen carbonate", "500ii"),
    ]

    for aid, canonical_name, code in expected_eight:
        assert code in ins_index, f"INS code {code} missing from ins_index"
        entry = ins_index[code]
        assert entry.id == aid
        assert entry.canonical_name == canonical_name
        assert entry.entity_type == IngredientCategory.FOOD_ADDITIVE
        assert entry.provenance.regulatory_verified is True

        # Test .additive backwards-compatibility property
        res = analyze_ingredients(f"Additive ({code})")
        assert len(res.matched_items) == 1
        item = res.matched_items[0]
        assert item.additive.id == aid
        assert item.ingredient.id == aid
        assert item.additive.canonical_name == canonical_name


# ==============================================================================
# 2. GENERAL INGREDIENT CATEGORIES & EXTENDED KNOWLEDGE BASE
# ==============================================================================
def test_generalized_ingredient_categories_matching() -> None:
    """
    Verifies deterministic identification of non-additive categories:
    - Ordinary agricultural staples and spices (Turmeric)
    - Fortification compounds (Vitamin D2, Ferric Pyrophosphate)
    - Allergen derivatives (Soy Protein Isolate)
    - Non-nutritive sweeteners (Sucralose)
    - Processing aids (Papain)
    - Nutritional components (Inulin)
    """
    cases = [
        ("Turmeric", "ing-turmeric", IngredientCategory.ORDINARY_INGREDIENT),
        ("Ergocalciferol", "fort-vit-d2", IngredientCategory.FORTIFICATION_COMPOUND),
        (
            "Ferric Pyrophosphate",
            "fort-ferric-pyrophosphate",
            IngredientCategory.FORTIFICATION_COMPOUND,
        ),
        ("Soy Protein Isolate", "ing-soy-protein-isolate", IngredientCategory.ALLERGEN),
        ("Sucralose", "ins-955", IngredientCategory.SWEETENER),
        ("Papain", "proc-papain", IngredientCategory.PROCESSING_AID),
        ("Inulin", "nutr-inulin", IngredientCategory.NUTRITIONAL_COMPONENT),
    ]

    for raw_text, expected_id, expected_category in cases:
        res = analyze_ingredients(raw_text)
        assert len(res.matched_items) == 1, f"Failed matching: '{raw_text}'"
        match = res.matched_items[0]
        assert match.ingredient.id == expected_id
        assert match.ingredient.entity_type == expected_category
        assert match.ingredient.provenance.regulatory_verified is True


# ==============================================================================
# 3. INDIAN LANGUAGE ALIAS MATCHING (HINDI DEVANAGARI)
# ==============================================================================
def test_indian_language_hindi_alias_matching() -> None:
    """Verifies that verified Indian language aliases (Hindi Devanagari) match deterministically."""
    hindi_cases = [
        ("हल्दी", "ing-turmeric", MatchType.INDIAN_LANGUAGE_ALIAS),
        ("हल्दी पाउडर", "ing-turmeric", MatchType.INDIAN_LANGUAGE_ALIAS),
    ]

    for raw_hindi, expected_id, expected_match_type in hindi_cases:
        res = analyze_ingredients(raw_hindi)
        assert len(res.matched_items) == 1, f"Failed matching Hindi alias: '{raw_hindi}'"
        match = res.matched_items[0]
        assert match.ingredient.id == expected_id
        assert match.match_type == expected_match_type
        assert match.confidence == 1.0


# ==============================================================================
# 4. REPEATED INGREDIENTS & OCCURRENCE PRESERVATION
# ==============================================================================
def test_repeated_ingredients_occurrence_preservation() -> None:
    """
    When an ingredient appears multiple times in different parts of a label,
    its occurrence count and raw packaging mentions are preserved without
    inflating the reference record count in the summary.
    """
    text = "Turmeric, Salt, Turmeric Powder, Haldi, Black Pepper"
    res = analyze_ingredients(text)

    # Turmeric was mentioned 3 times (Turmeric, Turmeric Powder, Haldi)
    turmeric_matches = [m for m in res.matched_items if m.ingredient.id == "ing-turmeric"]
    assert len(turmeric_matches) == 1
    t_match = turmeric_matches[0]
    assert t_match.occurrences == 3
    assert "Turmeric" in t_match.raw_mentions
    assert "Turmeric Powder" in t_match.raw_mentions
    assert "Haldi" in t_match.raw_mentions

    # Salt and Black Pepper remain uncatalogued whole foods
    assert "Salt" in res.unmatched_items
    assert "Black Pepper" in res.unmatched_items


# ==============================================================================
# 5. COMPOUND INGREDIENT & NESTED SUB-INGREDIENT PARSING
# ==============================================================================
def test_compound_ingredient_and_nested_sub_ingredients() -> None:
    """
    Tests parentheses-aware compound parsing where both the parent compound
    and recognized sub-ingredients are deterministically resolved.
    """
    text = "Cocoa Butter Preparation (Turmeric, Soya Lecithin, Salt)"
    res = analyze_ingredients(text)

    # Compound parent was matched
    compound_matches = [m for m in res.matched_items if m.ingredient.id == "ing-cocoa-butter-prep"]
    assert len(compound_matches) == 1
    comp = compound_matches[0]
    assert comp.is_compound is True
    assert len(comp.sub_matches) >= 1

    # Recognized sub-ingredients are also indexed in matched_items
    matched_ids = [m.ingredient.id for m in res.matched_items]
    assert "ing-turmeric" in matched_ids
    assert "ins-322" in matched_ids

    # Unmatched sub-ingredients remain in unmatched_items
    assert "Salt" in res.unmatched_items


# ==============================================================================
# 6. AMBIGUOUS FUNCTIONAL-CLASS TERMS ISOLATION
# ==============================================================================
def test_ambiguous_functional_classes_not_guessed() -> None:
    """
    A bare functional-class keyword (e.g. 'Emulsifier' or 'Preservative') without
    a code or chemical name must NEVER be guessed as a specific additive.
    It must be isolated in ambiguous_items.
    """
    text = "Wheat Flour, Emulsifier, Preservative, Palm Oil"
    res = analyze_ingredients(text)

    assert len(res.matched_items) == 0
    assert "Emulsifier" in res.ambiguous_items
    assert "Preservative" in res.ambiguous_items
    assert "Emulsifier" in res.unmatched_items
    assert "Preservative" in res.unmatched_items


# ==============================================================================
# 7. FALSE-POSITIVE RESISTANCE: BARE NUMBERS & SHORT TOKENS
# ==============================================================================
def test_false_positive_resistance_bare_numbers() -> None:
    """
    Bare numbers from percentages or weights (e.g. '100g', '100%') must not
    falsely match an INS number unless in explicit additive context.
    """
    text = "100% Whole Wheat, Salt, Net Wt 500g"
    res = analyze_ingredients(text)

    # Neither 100 nor 500 should match an additive
    assert len(res.matched_items) == 0
    assert any("100% Whole Wheat" in u for u in res.unmatched_items)


# ==============================================================================
# 8. DATASET VALIDATION PIPELINE TESTS (FAIL-CLOSED INTEGRITY)
# ==============================================================================
def test_validator_detects_duplicate_canonical_ids(tmp_path: Path) -> None:
    """Validator detects and rejects duplicate canonical IDs."""
    data = {
        "version": "1.0.0",
        "ingredients": [
            {"id": "dup-01", "canonical_name": "Item A", "entity_type": "ordinary_ingredient"},
            {"id": "dup-01", "canonical_name": "Item B", "entity_type": "ordinary_ingredient"},
        ],
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    report = validate_ingredient_dataset(p)
    assert report["is_valid"] is False
    assert report["duplicate_ids_count"] == 1


def test_validator_detects_alias_collisions(tmp_path: Path) -> None:
    """Validator detects when two distinct records claim the same normalized alias."""
    data = {
        "version": "1.0.0",
        "ingredients": [
            {
                "id": "rec-01",
                "canonical_name": "Item One",
                "entity_type": "ordinary_ingredient",
                "aliases": ["shared_alias"],
            },
            {
                "id": "rec-02",
                "canonical_name": "Item Two",
                "entity_type": "ordinary_ingredient",
                "aliases": ["shared_alias"],
            },
        ],
    }
    p = tmp_path / "collision.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    report = validate_ingredient_dataset(p)
    assert report["is_valid"] is False
    assert report["alias_collisions_count"] >= 1


def test_validator_detects_conflicting_ins_identifiers(tmp_path: Path) -> None:
    """Validator detects when two distinct records claim the same normalized INS number."""
    data = {
        "version": "1.0.0",
        "ingredients": [
            {
                "id": "rec-01",
                "canonical_name": "Chemical A",
                "entity_type": "food_additive",
                "ins_number": "INS 322",
            },
            {
                "id": "rec-02",
                "canonical_name": "Chemical B",
                "entity_type": "food_additive",
                "ins_number": "322",
            },
        ],
    }
    p = tmp_path / "ins_conflict.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    report = validate_ingredient_dataset(p)
    assert report["is_valid"] is False
    assert report["conflicting_identifiers_count"] >= 1


def test_validator_flags_suspiciously_broad_aliases(tmp_path: Path) -> None:
    """Validator warns on overly broad generic tokens like 'food' or 'powder'."""
    data = {
        "version": "1.0.0",
        "ingredients": [
            {
                "id": "rec-01",
                "canonical_name": "Special Seasoning",
                "entity_type": "ordinary_ingredient",
                "aliases": ["powder", "spice"],
            },
        ],
    }
    p = tmp_path / "broad.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    report = validate_ingredient_dataset(p)
    assert report["broad_aliases_count"] == 2


# ==============================================================================
# 9. API CONTRACT COMPATIBILITY WITH NEW FIELDS
# ==============================================================================
def test_api_ingredient_analysis_rich_response(client: TestClient) -> None:
    """Verifies that FastAPI endpoint delivers rich metadata without breaking existing schema."""
    payload = {
        "ingredients_text": (
            "Turmeric Powder, Sucralose (INS 955), Flavour Enhancer (INS 621), "
            "Turmeric, Emulsifier, Salt"
        )
    }
    response = client.post("/api/v1/ingredients/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_matched"] == 3  # Turmeric, Sucralose, MSG
    assert "ins-621" in [m["additive"]["id"] for m in data["matched_items"]]
    assert "ins-955" in [m["additive"]["id"] for m in data["matched_items"]]
    assert "ing-turmeric" in [m["additive"]["id"] for m in data["matched_items"]]

    # Verify occurrence tracking in API response
    turmeric_item = next(m for m in data["matched_items"] if m["additive"]["id"] == "ing-turmeric")
    assert turmeric_item["occurrences"] == 2
    assert len(turmeric_item["raw_mentions"]) == 2

    # Verify ambiguous items
    assert "Emulsifier" in data["ambiguous_items"]

    # Verify category summary
    assert "ordinary_ingredient" in data["category_summary"]
    assert "food_additive" in data["category_summary"]
    assert "sweetener" in data["category_summary"]


# ==============================================================================
# 10. PHASE 4C: EVIDENCE AUDIT & PROVENANCE REGRESSION TESTS
# ==============================================================================
def test_bare_numbers_out_of_context_not_matched() -> None:
    """
    Bare numbers without INS prefix, parentheses, or functional class must NOT
    match food additives out of context (e.g. '621', '211', '330').
    """
    out_of_context_inputs = [
        "621",
        "211",
        "330",
        "102",
        "951",
        "Wheat Flour, 621, Salt",
        "Refined Oil, Net Wt 330g, Water",
        "Batch 102, Energy 621 kJ",
    ]
    for text in out_of_context_inputs:
        res = analyze_ingredients(text)
        # Additives like ins-621, ins-211, ins-330, ins-102 must NOT match bare numbers
        matched_additive_ids = [m.ingredient.id for m in res.matched_items]
        assert "ins-621" not in matched_additive_ids, f"Bare number matched MSG in: {text}"
        assert "ins-211" not in matched_additive_ids, f"Bare number matched Benzoate in: {text}"
        assert "ins-330" not in matched_additive_ids, f"Bare number matched Citric Acid in: {text}"
        assert "ins-102" not in matched_additive_ids, f"Bare number matched Tartrazine in: {text}"


def test_five_track_provenance_audit() -> None:
    """Verifies that all 16 reference records satisfy the 5 independent verification tracks."""
    kb = load_knowledge_base()
    assert len(kb.records_by_id) == 16

    for iid, record in kb.records_by_id.items():
        prov = record.provenance
        assert prov.schema_valid is True, f"{iid} schema_valid must be True"
        assert prov.source_url_recorded is True, f"{iid} source_url_recorded must be True"
        assert prov.source_url_accessible is True, f"{iid} source_url_accessible must be True"
        assert prov.source_content_checked is True, f"{iid} source_content_checked must be True"
        assert prov.scientific_claim_supported is True, (
            f"{iid} scientific_claim_supported must be True"
        )
        assert prov.regulatory_claim_verified is True, (
            f"{iid} regulatory_claim_verified must be True"
        )
        assert prov.audit_date == "2026-10-19", f"{iid} missing audit_date"
        assert prov.auditor_role != "", f"{iid} missing auditor_role"
        assert prov.claim_verification_notes != "", f"{iid} missing verification notes"


def test_turmeric_curcumin_cas_distinction() -> None:
    """Verifies that turmeric distinguishes whole agricultural spice CAS from curcumin CAS."""
    kb = load_knowledge_base()
    turmeric = kb.records_by_id["ing-turmeric"]
    assert turmeric.cas_number == "84775-52-0"
    assert "458-37-7" in turmeric.chemical_identity
    assert "curcumin" in turmeric.chemical_identity.lower()


def test_soy_allergen_statutory_citation() -> None:
    """Verifies that soy protein isolate cites FSSAI Regulation 5(3)(e)."""
    kb = load_knowledge_base()
    soy = kb.records_by_id["ing-soy-protein-isolate"]
    assert soy.cas_number == "9010-10-0"
    assert any("5(3)" in s.section_or_regulation for s in soy.sources)
