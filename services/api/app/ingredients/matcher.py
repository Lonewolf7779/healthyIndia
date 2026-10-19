"""
Deterministic ingredient parser and extensible knowledge base matcher.
Phase 4A: Extensible Ingredient Knowledge Base Foundation.

Guiding Principles:
1. Pure deterministic exact and regex matching.
2. No generative-AI, heuristic fuzzy guessing, or unverified probabilistic assignment.
3. Matching priorities:
   - Priority 1: Exact canonical name match.
   - Priority 2: Exact normalized alias match (including Indian language / Hindi aliases).
   - Priority 3: Verified INS/E identifier match.
   - Priority 4: Constrained context-aware and compound sub-ingredient matching.
   - Priority 5: Otherwise, preserve the term as unknown or ambiguous.
4. Occurrences and original label mentions are preserved without duplicate reference entries.
5. Identification of an ingredient indicates its detected presence; it does not constitute
   an evaluation of product safety, nor does the presence of an INS code imply blanket
   authorization in all food categories under FSSAI regulations.
"""

from __future__ import annotations

import re
from typing import Final

from app.ingredients.loader import (
    IngredientKnowledgeBase,
    load_knowledge_base,
    normalize_ins_code,
    normalize_lookup_token,
)
from app.ingredients.models import (
    IngredientAnalysisResult,
    IngredientCategory,
    MatchedIngredient,
    MatchType,
)

DISCLAIMER: Final[str] = (
    "healthyIndia ingredient matching is deterministic and based on exact verified aliases, "
    "INS numbers, and official standards. Identification of an ingredient does not constitute "
    "an evaluation of product safety, nor does statutory permission in one category imply "
    "blanket authorization across all food categories under FSSAI regulations."
)

# Common functional class prefix keywords used in Indian packaging
FUNCTIONAL_PREFIXES_REGEX: Final[str] = (
    r"(?:flavour enhancer|flavor enhancer|emulsifier|sweetener|preservative|colour|color|"
    r"raising agent|acidity regulator|stabilizer|antioxidant|thickener|glazing agent|"
    r"anticaking agent|firming agent|humectant|flour treatment agent|dough conditioner)"
)

GENERIC_FUNCTIONAL_CLASSES: Final[set[str]] = {
    "flavour enhancer",
    "flavor enhancer",
    "emulsifier",
    "sweetener",
    "preservative",
    "colour",
    "color",
    "raising agent",
    "acidity regulator",
    "stabilizer",
    "antioxidant",
    "thickener",
    "glazing agent",
    "anticaking agent",
    "firming agent",
    "humectant",
    "dough conditioner",
}


def split_ingredients_list(text: str) -> list[str]:
    """
    Splits an ingredient string on commas, semicolons, or bullets while
    strictly respecting nested parentheses and brackets.
    """
    tokens: list[str] = []
    current: list[str] = []
    depth = 0

    for char in text:
        if char in "([{\u27e8":
            depth += 1
            current.append(char)
        elif char in ")]}\u27e9":
            if depth > 0:
                depth -= 1
            current.append(char)
        elif char in ",;\u2022\n\r" and depth == 0:
            token = "".join(current).strip()
            if token:
                tokens.append(token)
            current = []
        else:
            current.append(char)

    last_token = "".join(current).strip()
    if last_token:
        tokens.append(last_token)

    return tokens


def clean_raw_token(token: str) -> str:
    """
    Removes leading numbers/bullets and trailing percentage indications.
    e.g. '1. Wheat Flour (65%)' -> 'Wheat Flour (65%)'
    """
    token = token.strip()
    # Strip leading bullets or list numbering: '1.', '2)', '*'
    token = re.sub(r"^[\s*\-•\d]+[.)]\s*", "", token)
    return token.strip()


def extract_ins_pattern(token: str) -> str | None:
    """
    Detects INS or E number references within a token:
    1. Explicit prefix: 'INS 322', 'E-621', 'INS. 500(ii)', 'INS-500ii'
    2. Functional wrapper with numeric code: 'Emulsifier (322)', 'Preservative (211)'
    3. Trailing parenthesized code: '(621)', '(500(ii))'
    4. Standalone code token: '500(ii)', '621'
    """
    # 1. Explicit INS or E prefix
    explicit_match = re.search(
        r"(?:\b|^)(?:ins|e)\.?[\s\-_]*([0-9]{3,4}[a-z0-9]*(?:\([a-z0-9]+\))?)",
        token,
        re.IGNORECASE,
    )
    if explicit_match:
        return explicit_match.group(1)

    # 2. Functional prefix with parenthesized code
    pattern = (
        FUNCTIONAL_PREFIXES_REGEX
        + r"\s*\(\s*(?:ins\s*)?([0-9]{3,4}[a-z0-9]*(?:\([a-z0-9]+\))?)\s*\)"
    )
    functional_match = re.search(pattern, token, re.IGNORECASE)
    if functional_match:
        return functional_match.group(1)

    # 3. Trailing parenthesized 3-4 digit code e.g. '(621)'
    paren_code_match = re.search(
        r"\(\s*([0-9]{3,4}[a-z0-9]*(?:\([a-z0-9]+\))?)\s*\)",
        token,
    )
    if paren_code_match:
        return paren_code_match.group(1)

    # 4. Standalone code token e.g. '500(ii)', '621'
    standalone_code = re.match(
        r"^([0-9]{3,4}[a-z0-9]*(?:\([a-z0-9]+\))?)$",
        token.strip(),
        re.IGNORECASE,
    )
    if standalone_code:
        return standalone_code.group(1)

    return None


def match_single_token(
    raw_token: str,
    kb: IngredientKnowledgeBase,
) -> MatchedIngredient | None:
    """
    Attempts deterministic match in strict priority order:
    1. Exact canonical name match
    2. Indian language alias match (e.g. Hindi Devanagari)
    3. Exact normalized alias match
    4. INS / E number extraction
    5. Inner parenthetical content matching
    """
    norm_token = normalize_lookup_token(raw_token)

    # Guard: Generic functional class keyword alone must not identify a specific substance
    if norm_token in GENERIC_FUNCTIONAL_CLASSES:
        return None

    # Priority 1: Try INS / E number extraction (e.g. 'INS 322(i)', 'E-621', '500(ii)')
    ins_code = extract_ins_pattern(raw_token)
    if ins_code:
        norm_ins = normalize_ins_code(ins_code)
        if norm_ins in kb.ins_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.INS_NUMBER,
                confidence=1.0,
                ingredient=kb.ins_index[norm_ins],
            )

    # Priority 2: Exact canonical name match
    if norm_token in kb.canonical_index:
        entry = kb.canonical_index[norm_token]
        return MatchedIngredient(
            raw_text=raw_token,
            match_type=MatchType.EXACT_CANONICAL,
            confidence=1.0,
            ingredient=entry,
        )

    # Priority 3: Indian language alias match (e.g. Hindi Devanagari)
    if norm_token in kb.indian_alias_index:
        entry = kb.indian_alias_index[norm_token]
        return MatchedIngredient(
            raw_text=raw_token,
            match_type=MatchType.INDIAN_LANGUAGE_ALIAS,
            confidence=1.0,
            ingredient=entry,
        )

    # Priority 4: Exact normalized alias match
    if norm_token in kb.alias_index:
        entry = kb.alias_index[norm_token]
        return MatchedIngredient(
            raw_text=raw_token,
            match_type=MatchType.EXACT_ALIAS,
            confidence=1.0,
            ingredient=entry,
        )

    # Priority 5: Check parenthesized sub-content e.g. 'Acidity Regulator (Citric Acid)'
    inner_paren_match = re.search(r"\(([^)]+)\)", raw_token)
    if inner_paren_match:
        inner_content = inner_paren_match.group(1).strip()
        norm_inner = normalize_lookup_token(inner_content)

        if norm_inner in kb.canonical_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.EXACT_CANONICAL,
                confidence=1.0,
                ingredient=kb.canonical_index[norm_inner],
            )
        if norm_inner in kb.indian_alias_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.INDIAN_LANGUAGE_ALIAS,
                confidence=1.0,
                ingredient=kb.indian_alias_index[norm_inner],
            )
        if norm_inner in kb.alias_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.EXACT_ALIAS,
                confidence=1.0,
                ingredient=kb.alias_index[norm_inner],
            )

        norm_inner_ins = normalize_ins_code(inner_content)
        if norm_inner_ins in kb.ins_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.INS_NUMBER,
                confidence=1.0,
                ingredient=kb.ins_index[norm_inner_ins],
            )

    return None


def parse_compound_token(
    raw_token: str,
    kb: IngredientKnowledgeBase,
) -> tuple[MatchedIngredient | None, list[MatchedIngredient], list[str]]:
    """
    Parses a token that may represent a compound ingredient with nested sub-ingredients.
    Returns:
    (parent_match, matched_sub_ingredients, unmatched_sub_ingredients)
    """
    paren_idx = raw_token.find("(")
    if paren_idx <= 0 or not raw_token.endswith(")"):
        return None, [], []

    outer_name = raw_token[:paren_idx].strip()
    inner_clause = raw_token[paren_idx + 1 : -1].strip()

    parent_match = match_single_token(outer_name, kb)
    sub_tokens = split_ingredients_list(inner_clause)

    matched_subs: list[MatchedIngredient] = []
    unmatched_subs: list[str] = []

    for sub in sub_tokens:
        cleaned_sub = clean_raw_token(sub)
        if not cleaned_sub:
            continue
        sub_m = match_single_token(cleaned_sub, kb)
        if sub_m:
            matched_subs.append(sub_m)
        else:
            unmatched_subs.append(cleaned_sub)

    return parent_match, matched_subs, unmatched_subs


def analyze_ingredients(ingredients_text: str) -> IngredientAnalysisResult:
    """
    Parses an ingredients declaration string deterministically against the
    extensible ingredient knowledge base.
    """
    kb = load_knowledge_base()

    raw_tokens = split_ingredients_list(ingredients_text)
    matched_by_id: dict[str, MatchedIngredient] = {}
    unmatched_items: list[str] = []
    ambiguous_items: list[str] = []

    for token in raw_tokens:
        cleaned = clean_raw_token(token)
        if not cleaned:
            continue

        norm_cleaned = normalize_lookup_token(cleaned)
        if norm_cleaned in GENERIC_FUNCTIONAL_CLASSES:
            ambiguous_items.append(cleaned)
            unmatched_items.append(cleaned)
            continue

        # Check if token is a compound ingredient with parentheses
        if "(" in cleaned and cleaned.endswith(")"):
            parent_m, sub_matches, unmatched_subs = parse_compound_token(cleaned, kb)
            if parent_m:
                # Top-level is a recognized compound ingredient
                cid = parent_m.ingredient.id
                if cid in matched_by_id:
                    existing = matched_by_id[cid]
                    object.__setattr__(existing, "occurrences", existing.occurrences + 1)
                    existing.raw_mentions.append(cleaned)
                else:
                    compound_record = MatchedIngredient(
                        raw_text=cleaned,
                        match_type=parent_m.match_type,
                        confidence=parent_m.confidence,
                        ingredient=parent_m.ingredient,
                        occurrences=1,
                        raw_mentions=[cleaned],
                        sub_matches=sub_matches,
                        is_compound=True,
                    )
                    matched_by_id[cid] = compound_record

                # Also add recognized sub-matches
                for sm in sub_matches:
                    sid = sm.ingredient.id
                    if sid in matched_by_id:
                        ex = matched_by_id[sid]
                        object.__setattr__(ex, "occurrences", ex.occurrences + 1)
                        ex.raw_mentions.append(sm.raw_text)
                    else:
                        matched_by_id[sid] = sm

                for us in unmatched_subs:
                    if us not in unmatched_items:
                        unmatched_items.append(us)
                continue
            elif sub_matches:
                # Outer name was not a recognized compound, but sub-ingredients matched!
                for sm in sub_matches:
                    sid = sm.ingredient.id
                    if sid in matched_by_id:
                        ex = matched_by_id[sid]
                        object.__setattr__(ex, "occurrences", ex.occurrences + 1)
                        ex.raw_mentions.append(sm.raw_text)
                    else:
                        matched_by_id[sid] = sm
                for us in unmatched_subs:
                    if us not in unmatched_items:
                        unmatched_items.append(us)
                continue

        # Standard single token match
        match = match_single_token(cleaned, kb)
        if match:
            mid = match.ingredient.id
            if mid in matched_by_id:
                existing = matched_by_id[mid]
                object.__setattr__(existing, "occurrences", existing.occurrences + 1)
                existing.raw_mentions.append(cleaned)
            else:
                matched_by_id[mid] = match
        else:
            unmatched_items.append(cleaned)

    matched_items = list(matched_by_id.values())
    total_tokens = len(matched_items) + len(unmatched_items)

    # Category summary
    cat_summary: dict[str, int] = {}
    for m in matched_items:
        primary_cat = m.ingredient.entity_type.value
        cat_summary[primary_cat] = cat_summary.get(primary_cat, 0) + 1
        for c in m.ingredient.categories:
            c_val = c.value if isinstance(c, IngredientCategory) else str(c)
            if c_val != primary_cat:
                cat_summary[c_val] = cat_summary.get(c_val, 0) + 1

    return IngredientAnalysisResult(
        matched_items=matched_items,
        unmatched_items=unmatched_items,
        total_tokens_detected=total_tokens,
        total_matched=len(matched_items),
        total_unmatched=len(unmatched_items),
        disclaimer=DISCLAIMER,
        ambiguous_items=ambiguous_items,
        category_summary=cat_summary,
    )
