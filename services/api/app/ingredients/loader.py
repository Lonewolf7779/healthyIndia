"""
Deterministic reference dataset loader and index builder.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from app.ingredients.models import AdditiveEntry, SourceReference


def normalize_lookup_token(token: str) -> str:
    """
    Normalizes a token for deterministic exact comparison:
    - lowercase
    - strip extra whitespace
    - unify hyphens/underscores
    - remove unnecessary wrapping punctuation
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


@lru_cache
def load_ingredient_reference() -> tuple[dict[str, AdditiveEntry], dict[str, AdditiveEntry]]:
    """
    Loads additives_v1.json and builds fast deterministic lookup indices:
    1. ins_index: maps normalized numerical codes (e.g. '621', '322i') to AdditiveEntry
    2. alias_index: maps normalized strings (e.g. 'msg', 'tartrazine') to AdditiveEntry
    """
    # Look for data directory relative to repository root or services/api
    potential_paths: Final[list[Path]] = [
        Path(__file__).resolve().parents[4] / "data" / "ingredient_reference" / "additives_v1.json",
        Path(__file__).resolve().parents[3] / "data" / "ingredient_reference" / "additives_v1.json",
        Path("data/ingredient_reference/additives_v1.json").resolve(),
    ]

    target_file = next((p for p in potential_paths if p.is_file()), None)
    if not target_file:
        raise FileNotFoundError(
            f"Ingredient reference dataset not found in expected locations: {potential_paths}"
        )

    with target_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    ins_index: dict[str, AdditiveEntry] = {}
    alias_index: dict[str, AdditiveEntry] = {}

    for item in data.get("additives", []):
        sources = [
            SourceReference(
                title=s.get("title", ""),
                url=s.get("url", ""),
                source_type=s.get("source_type", ""),
                retrieval_date=s.get("retrieval_date", ""),
            )
            for s in item.get("sources", [])
        ]

        entry = AdditiveEntry(
            id=item["id"],
            canonical_name=item["canonical_name"],
            ins_number=item.get("ins_number"),
            e_number=item.get("e_number"),
            functional_classes=item.get("functional_classes", []),
            aliases=item.get("aliases", []),
            sources=sources,
            jurisdiction=item.get("jurisdiction", "India (FSSAI) & Codex Alimentarius"),
            regulatory_status=item.get("regulatory_status", "unverified"),
            status_verification=item.get("status_verification", "unverified"),
            scope_limitations=item.get("scope_limitations", ""),
        )

        # Index by normalized INS code if present
        if entry.ins_number:
            norm_code = normalize_ins_code(entry.ins_number)
            ins_index[norm_code] = entry
            # Also register version with parentheses stripped if different
            norm_code_clean = re.sub(r"[()\s]", "", norm_code)
            ins_index[norm_code_clean] = entry

        if entry.e_number:
            norm_code_e = normalize_ins_code(entry.e_number)
            ins_index[norm_code_e] = entry

        # Index all declared aliases
        for alias in entry.aliases:
            norm_alias = normalize_lookup_token(alias)
            alias_index[norm_alias] = entry
            # If alias contains an INS number pattern, also register in ins_index
            if re.match(r"^(?:ins|e)?[\s\-_]*[0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?$", norm_alias):
                ins_index[normalize_ins_code(norm_alias)] = entry

    return ins_index, alias_index
