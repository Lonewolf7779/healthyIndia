"""
Deterministic reference dataset loader and index builder.
Phase 4A: Extensible Ingredient Knowledge Base Foundation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final

from app.ingredients.models import (
    EvidenceProvenance,
    IngredientCategory,
    IngredientRecord,
    RecordStatus,
    SourceReference,
)


@dataclass
class IngredientKnowledgeBase:
    """In-memory deterministic index for rapid, collision-free ingredient lookup."""

    records_by_id: dict[str, IngredientRecord] = field(default_factory=dict)
    canonical_index: dict[str, IngredientRecord] = field(default_factory=dict)
    alias_index: dict[str, IngredientRecord] = field(default_factory=dict)
    ins_index: dict[str, IngredientRecord] = field(default_factory=dict)
    indian_alias_index: dict[str, IngredientRecord] = field(default_factory=dict)
    dataset_version: str = "2.0.0"


def normalize_lookup_token(token: str) -> str:
    """
    Normalizes a token for deterministic exact comparison:
    - lowercase
    - strip extra whitespace
    - unify hyphens/underscores
    - remove unnecessary wrapping punctuation while preserving internal words and Unicode
    """
    token = token.lower().strip()
    token = re.sub(r"[\s_]+", " ", token)
    return token.strip(" ,.;:()[]{}'\"")


def normalize_ins_code(code: str) -> str:
    """
    Normalizes INS / E numerical tokens for consistent matching:
    e.g. 'INS 322(i)' -> '322i', 'E-621' -> '621', '500(ii)' -> '500ii'
    """
    code = code.lower().strip()
    # Strip INS, E prefixes
    code = re.sub(r"^(ins|e)[\s\-_]*", "", code)
    # Remove outer and inner parentheses: 500(ii) -> 500ii
    code = re.sub(r"[()\s]", "", code)
    return code


def locate_ingredient_dataset_file() -> Path:
    """Finds the primary ingredient knowledge base file on disk."""
    base_dir = Path(__file__).resolve()
    potential_paths: Final[list[Path]] = [
        base_dir.parents[4] / "data" / "ingredient_reference" / "ingredients_v1.json",
        base_dir.parents[3] / "data" / "ingredient_reference" / "ingredients_v1.json",
        Path("data/ingredient_reference/ingredients_v1.json").resolve(),
        base_dir.parents[4] / "data" / "ingredient_reference" / "additives_v1.json",
        base_dir.parents[3] / "data" / "ingredient_reference" / "additives_v1.json",
        Path("data/ingredient_reference/additives_v1.json").resolve(),
    ]

    target = next((p for p in potential_paths if p.is_file()), None)
    if not target:
        raise FileNotFoundError(
            f"Ingredient reference dataset not found in expected locations: {potential_paths}"
        )
    return target


def parse_ingredient_raw_dict(item: dict) -> IngredientRecord:
    """Parses a dictionary into a validated IngredientRecord."""
    sources = [
        SourceReference(
            title=s.get("title", ""),
            url=s.get("url", ""),
            source_type=s.get("source_type", ""),
            retrieval_date=s.get("retrieval_date", ""),
            organization=s.get("organization", ""),
            publication_date=s.get("publication_date", ""),
            supported_claims=s.get("supported_claims", ""),
            section_or_regulation=s.get("section_or_regulation", ""),
            license=s.get("license", ""),
        )
        for s in item.get("sources", [])
    ]

    raw_prov = item.get("provenance", {})
    is_verified_status = item.get("status_verification") == "verified"
    default_jurisdiction = "India (FSSAI) & Codex Alimentarius"
    provenance = EvidenceProvenance(
        schema_valid=raw_prov.get("schema_valid", True),
        source_linked=raw_prov.get("source_linked", len(sources) > 0),
        source_checked=raw_prov.get("source_checked", is_verified_status),
        scientifically_reviewed=raw_prov.get("scientifically_reviewed", is_verified_status),
        regulatory_verified=raw_prov.get("regulatory_verified", is_verified_status),
        verification_level=raw_prov.get(
            "verification_level", item.get("status_verification", "unverified")
        ),
        jurisdiction=raw_prov.get("jurisdiction", item.get("jurisdiction", default_jurisdiction)),
        regulatory_act=raw_prov.get("regulatory_act", ""),
        notes=raw_prov.get("notes", ""),
    )

    # Category handling
    raw_cat = item.get("entity_type")
    if raw_cat:
        try:
            entity_type = IngredientCategory(raw_cat)
        except ValueError:
            entity_type = IngredientCategory.ORDINARY_INGREDIENT
    elif item.get("ins_number") or item.get("functional_classes"):
        entity_type = IngredientCategory.FOOD_ADDITIVE
    else:
        entity_type = IngredientCategory.ORDINARY_INGREDIENT

    categories: list[IngredientCategory] = []
    for c in item.get("categories", []):
        try:
            categories.append(IngredientCategory(c))
        except ValueError:
            pass
    if entity_type not in categories:
        categories.insert(0, entity_type)

    record_status_val = RecordStatus.ACTIVE
    raw_status = item.get("record_status")
    if raw_status:
        try:
            record_status_val = RecordStatus(raw_status)
        except ValueError:
            pass

    return IngredientRecord(
        id=item["id"],
        canonical_name=item["canonical_name"],
        entity_type=entity_type,
        categories=categories,
        aliases=item.get("aliases", []),
        indian_language_aliases=item.get("indian_language_aliases", {}),
        ins_number=item.get("ins_number"),
        e_number=item.get("e_number"),
        cas_number=item.get("cas_number"),
        functional_classes=item.get("functional_classes", []),
        parent_ingredient_id=item.get("parent_ingredient_id"),
        sub_ingredient_ids=item.get("sub_ingredient_ids", []),
        sources=sources,
        jurisdiction=item.get("jurisdiction", "India (FSSAI) & Codex Alimentarius"),
        regulatory_status=item.get("regulatory_status", "unverified"),
        status_verification=item.get("status_verification", "unverified"),
        scope_limitations=item.get("scope_limitations", ""),
        provenance=provenance,
        chemical_identity=item.get("chemical_identity", ""),
        health_effects_evidence=item.get("health_effects_evidence", ""),
        acceptable_daily_intake=item.get("acceptable_daily_intake", ""),
        population_sensitivities=item.get("population_sensitivities", ""),
        everyday_quantity_explanation=item.get("everyday_quantity_explanation"),
        known_limitations_and_uncertainty=item.get("known_limitations_and_uncertainty", ""),
        last_reviewed=item.get("last_reviewed", ""),
        dataset_version=item.get("dataset_version", "2.0.0"),
        record_status=record_status_val,
    )


@lru_cache
def load_knowledge_base(dataset_file: Path | None = None) -> IngredientKnowledgeBase:
    """
    Loads unified ingredient dataset (ingredients_v1.json or additives_v1.json)
    and constructs collision-guarded deterministic lookup indices.
    """
    target_file = dataset_file or locate_ingredient_dataset_file()
    with target_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    version = data.get("version", "2.0.0")
    items_list = data.get("ingredients") or data.get("additives") or []

    kb = IngredientKnowledgeBase(dataset_version=version)

    for raw_item in items_list:
        entry = parse_ingredient_raw_dict(raw_item)
        kb.records_by_id[entry.id] = entry

        # 1. Canonical Name Index
        norm_canonical = normalize_lookup_token(entry.canonical_name)
        kb.canonical_index[norm_canonical] = entry
        kb.alias_index[norm_canonical] = entry

        # 2. INS Number Index
        if entry.ins_number:
            norm_code = normalize_ins_code(entry.ins_number)
            kb.ins_index[norm_code] = entry
            norm_clean = re.sub(r"[()\s]", "", norm_code)
            kb.ins_index[norm_clean] = entry

        if entry.e_number:
            norm_code_e = normalize_ins_code(entry.e_number)
            kb.ins_index[norm_code_e] = entry

        # 3. Aliases Index
        for alias in entry.aliases:
            norm_alias = normalize_lookup_token(alias)
            kb.alias_index[norm_alias] = entry

            # If alias looks like an INS/E code pattern, register in ins_index as well
            if re.match(r"^(?:ins|e)?[\s\-_]*[0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?$", norm_alias):
                kb.ins_index[normalize_ins_code(norm_alias)] = entry

        # 4. Indian Language Aliases Index (e.g. Hindi Devanagari)
        for _lang, lang_aliases in entry.indian_language_aliases.items():
            for lang_alias in lang_aliases:
                norm_lang_alias = normalize_lookup_token(lang_alias)
                kb.alias_index[norm_lang_alias] = entry
                kb.indian_alias_index[norm_lang_alias] = entry

    return kb


@lru_cache
def load_ingredient_reference(
    dataset_file: Path | None = None,
) -> tuple[dict[str, IngredientRecord], dict[str, IngredientRecord]]:
    """
    Backwards compatibility loader specifically loading the curated additives reference dataset.
    Returns (ins_index, alias_index) for all audited food additives.
    """
    potential_additive_paths: Final[list[Path]] = [
        Path(__file__).resolve().parents[4] / "data" / "ingredient_reference" / "additives_v1.json",
        Path(__file__).resolve().parents[3] / "data" / "ingredient_reference" / "additives_v1.json",
        Path("data/ingredient_reference/additives_v1.json").resolve(),
    ]
    target = dataset_file or next((p for p in potential_additive_paths if p.is_file()), None)
    kb = load_knowledge_base(dataset_file=target)
    return kb.ins_index, kb.alias_index
