"""
Deterministic ingredient parser and additive matcher.

Guiding Principles:
1. Pure deterministic exact and regex matching.
2. No generative-AI, heuristic fuzzy guessing, or unverified probabilistic assignment.
3. Unmatched ingredients are preserved as unknown.
4. Identification does not imply blanket category permission.
"""

import re

from app.ingredients.loader import (
    load_ingredient_reference,
    normalize_ins_code,
    normalize_lookup_token,
)
from app.ingredients.models import (
    AdditiveEntry,
    IngredientAnalysisResult,
    MatchedIngredient,
    MatchType,
)

DISCLAIMER: str = (
    "healthyIndia additive matching is deterministic and based on exact verified aliases "
    "and INS numbers. Identification of an additive does not constitute an evaluation of "
    "product safety, nor does the presence of an INS code imply authorization in all "
    "food categories under FSSAI regulations."
)

# Common functional class prefix keywords used in Indian packaging
FUNCTIONAL_PREFIXES_REGEX = (
    r"(?:flavour enhancer|flavor enhancer|emulsifier|sweetener|preservative|colour|color|"
    r"raising agent|acidity regulator|stabilizer|antioxidant|thickener|glazing agent|"
    r"anticaking agent)"
)


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
    1. Explicit prefix: 'INS 322', 'E-621', 'INS. 500(ii)'
    2. Functional wrapper with numeric code: 'Emulsifier (322)', 'Preservative (211)'
    """
    # 1. Explicit INS or E prefix
    explicit_match = re.search(
        r"\b(?:ins|e)\.?[\s\-_]*([0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?)\b",
        token,
        re.IGNORECASE,
    )
    if explicit_match:
        return explicit_match.group(1)

    # 2. Functional prefix with parenthesized code
    pattern = (
        FUNCTIONAL_PREFIXES_REGEX + r"\s*\(\s*(?:ins\s*)?([0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?)\s*\)"
    )
    functional_match = re.search(pattern, token, re.IGNORECASE)
    if functional_match:
        return functional_match.group(1)

    # 3. Trailing parenthesized 3-4 digit code e.g. '(621)'
    paren_code_match = re.search(
        r"\(\s*([0-9]{3,4}[a-z]?(?:\([a-z0-9]+\))?)\s*\)",
        token,
    )
    if paren_code_match:
        return paren_code_match.group(1)

    return None


def match_single_token(
    raw_token: str,
    ins_index: dict[str, AdditiveEntry],
    alias_index: dict[str, AdditiveEntry],
) -> MatchedIngredient | None:
    """
    Attempts deterministic match:
    1. INS/E number extraction
    2. Exact normalized alias matching
    3. Inner parenthetical content matching (e.g. 'Preservative (Sodium Benzoate)')
    """
    # 1. Try INS extraction
    ins_code = extract_ins_pattern(raw_token)
    if ins_code:
        norm_ins = normalize_ins_code(ins_code)
        if norm_ins in ins_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.INS_NUMBER,
                confidence=1.0,
                additive=ins_index[norm_ins],
            )

    # 2. Try whole-token exact alias
    norm_token = normalize_lookup_token(raw_token)
    if norm_token in alias_index:
        return MatchedIngredient(
            raw_text=raw_token,
            match_type=MatchType.EXACT_ALIAS,
            confidence=1.0,
            additive=alias_index[norm_token],
        )

    # 3. Check for parenthesized sub-name e.g. 'Acidity Regulator (Citric Acid)'
    inner_paren_match = re.search(r"\(([^)]+)\)", raw_token)
    if inner_paren_match:
        inner_content = inner_paren_match.group(1).strip()
        norm_inner = normalize_lookup_token(inner_content)
        if norm_inner in alias_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.EXACT_ALIAS,
                confidence=1.0,
                additive=alias_index[norm_inner],
            )
        # Check if inner content is an INS code directly
        norm_inner_ins = normalize_ins_code(inner_content)
        if norm_inner_ins in ins_index:
            return MatchedIngredient(
                raw_text=raw_token,
                match_type=MatchType.INS_NUMBER,
                confidence=1.0,
                additive=ins_index[norm_inner_ins],
            )

    return None


def analyze_ingredients(ingredients_text: str) -> IngredientAnalysisResult:
    """
    Parses an ingredients declaration string deterministically against the
    curated additive dataset.
    """
    ins_index, alias_index = load_ingredient_reference()

    raw_tokens = split_ingredients_list(ingredients_text)
    matched_items: list[MatchedIngredient] = []
    unmatched_items: list[str] = []
    matched_ids: set[str] = set()

    for token in raw_tokens:
        cleaned = clean_raw_token(token)
        if not cleaned:
            continue

        match = match_single_token(cleaned, ins_index, alias_index)
        if match:
            # Prevent duplicate reports of the exact same additive in the same list
            if match.additive.id not in matched_ids:
                matched_items.append(match)
                matched_ids.add(match.additive.id)
        else:
            unmatched_items.append(cleaned)

    total_tokens = len(matched_items) + len(unmatched_items)

    return IngredientAnalysisResult(
        matched_items=matched_items,
        unmatched_items=unmatched_items,
        total_tokens_detected=total_tokens,
        total_matched=len(matched_items),
        total_unmatched=len(unmatched_items),
        disclaimer=DISCLAIMER,
    )
