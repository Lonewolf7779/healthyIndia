"""
Pure parsing heuristics for raw OCR text.
Extracts candidate nutrition values, detects ingredient sections,
and generates uncertainty warnings without making definitive truth claims.
"""

import re
from typing import Final

from app.extraction.models import (
    ExtractedNutrientCandidate,
    ExtractionWarning,
    OcrExtractionResult,
)

NUTRITION_LINE_KEYWORDS: Final[set[str]] = {
    "nutrition",
    "nutritional",
    "energy",
    "calories",
    "protein",
    "carbohydrate",
    "carbohydrates",
    "carbs",
    "sugar",
    "sugars",
    "fat",
    "fats",
    "saturated",
    "trans",
    "sodium",
    "salt",
    "cholesterol",
    "fiber",
    "fibre",
    "serving",
    "serve",
    "per 100g",
    "per 100ml",
    "approximate",
}


KJ_TO_KCAL_FACTOR: Final[float] = 4.184


def _extract_number_from_text(pattern: str, text: str) -> tuple[float | None, str | None, str]:
    """
    Finds first regex match for nutrient pattern and returns (value, unit, matched_line).
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None, None, ""

    matched_text = match.group(0).strip()
    try:
        val = float(match.group(1))
    except (ValueError, IndexError):
        val = None

    unit = None
    if len(match.groups()) >= 2 and match.group(2):
        unit = match.group(2).strip()

    return val, unit, matched_text


def _extract_energy_candidate(
    raw_text: str,
) -> tuple[ExtractedNutrientCandidate | None, list[ExtractionWarning]]:
    """
    Carefully parses energy declarations, distinguishing kcal and kJ.
    Never treats kJ as kcal. Converts kJ to kcal if only kJ is reported,
    with an explicit warning.
    """
    warnings: list[ExtractionWarning] = []
    energy_match = re.search(
        r"(?:energy|calories|caloric\s+value)\s*[:\.\-_=]*\s*([^\n\r;]+)",
        raw_text,
        re.IGNORECASE,
    )
    if not energy_match:
        return None, warnings

    line_text = energy_match.group(0).strip()
    phrase = energy_match.group(1).strip()

    # 1. Look for explicit kcal/cal value first
    m_kcal = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:kcal|cal)\b", phrase, re.IGNORECASE)
    if m_kcal:
        val = float(m_kcal.group(1))
        return (
            ExtractedNutrientCandidate(
                field_name="energy_kcal",
                raw_text=line_text,
                value=val,
                unit="kcal",
            ),
            warnings,
        )

    # 2. Look for kJ without kcal: convert deterministically via 4.184 factor
    m_kj = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:kj)\b", phrase, re.IGNORECASE)
    if m_kj:
        kj_val = float(m_kj.group(1))
        kcal_val = round(kj_val / KJ_TO_KCAL_FACTOR, 1)
        warnings.append(
            ExtractionWarning(
                code="ENERGY_KJ_CONVERTED",
                message=(
                    f"Energy was declared in kJ ({kj_val} kJ) and converted to kcal "
                    f"({kcal_val} kcal) using standard factor {KJ_TO_KCAL_FACTOR} kJ/kcal. "
                    "Please verify against physical label."
                ),
            )
        )
        return (
            ExtractedNutrientCandidate(
                field_name="energy_kcal",
                raw_text=line_text,
                value=kcal_val,
                unit="kcal",
            ),
            warnings,
        )

    # 3. Numeric value without unit: flag uncertainty
    m_num = re.search(r"([0-9]+(?:\.[0-9]+)?)\b", phrase)
    if m_num:
        val = float(m_num.group(1))
        warnings.append(
            ExtractionWarning(
                code="ENERGY_UNIT_UNCERTAIN",
                message=(
                    f"Energy value ({val}) was detected without an explicit unit (kcal or kJ). "
                    "Please verify unit against physical label."
                ),
            )
        )
        return (
            ExtractedNutrientCandidate(
                field_name="energy_kcal",
                raw_text=line_text,
                value=val,
                unit="kcal",
            ),
            warnings,
        )

    return None, warnings


def _extract_serving_candidate(raw_text: str) -> tuple[float | None, str, str]:
    """
    Extracts serving size candidate, giving precedence to parenthesized metric weights
    (e.g. '2 Cookies (24g)' -> (24.0, 'g')).
    """
    m = re.search(
        r"(?:serv(?:ing|e)?\.?\s+size|per\s+serve(?:ing)?)\s*[:\.\-_=]*\s*([^\n\r;]+)",
        raw_text,
        re.IGNORECASE,
    )
    if not m:
        m_standalone = re.search(
            r"(?:serv(?:ing|e)?\.?)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g|ml|piece|portion)?",
            raw_text,
            re.IGNORECASE,
        )
        if not m_standalone:
            return None, "g", ""
        val = float(m_standalone.group(1))
        unit = m_standalone.group(2) or "g"
        return val, unit, m_standalone.group(0).strip()

    phrase = m.group(1).strip()
    full_match = m.group(0).strip()

    # Priority 1: Parenthesized weight e.g. '(24g)' or '(approx. 24g)'
    m_paren = re.search(
        r"\(\s*(?:approx\.?\s*)?([0-9]+(?:\.[0-9]+)?)\s*(g|ml)\s*\)",
        phrase,
        re.IGNORECASE,
    )
    if m_paren:
        return float(m_paren.group(1)), m_paren.group(2).lower(), full_match

    # Priority 2: Leading weight e.g. '30g (Approx. 2 tbsp)' or '30g'
    m_weight = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(g|ml)\b", phrase, re.IGNORECASE)
    if m_weight:
        return float(m_weight.group(1)), m_weight.group(2).lower(), full_match

    # Priority 3: Discrete piece/portion unit
    m_discrete = re.search(
        r"([0-9]+(?:\.[0-9]+)?)\s*(piece|portion|biscuit|cookie|bar|pack)?",
        phrase,
        re.IGNORECASE,
    )
    if m_discrete:
        unit = m_discrete.group(2)
        discrete_unit = "portion" if unit == "portion" else ("piece" if unit else "piece")
        return float(m_discrete.group(1)), discrete_unit, full_match

    return None, "g", full_match


def parse_ocr_text(raw_text: str, confidence: float | None = None) -> OcrExtractionResult:
    """
    Heuristically partitions raw OCR text into candidate sections and values.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    warnings: list[ExtractionWarning] = []

    # 1. Uncertainty warnings on quality
    if len(raw_text.strip()) < 20:
        warnings.append(
            ExtractionWarning(
                code="SPARSE_TEXT",
                message=(
                    "Extracted text is very short or unclear. "
                    "Ensure the packaging label is well-lit, in focus, and flat."
                ),
            )
        )

    if confidence is not None and confidence < 60.0:
        warnings.append(
            ExtractionWarning(
                code="LOW_CONFIDENCE",
                message=(
                    f"OCR confidence is low ({confidence}%). "
                    "Please carefully verify all extracted fields against the physical label."
                ),
            )
        )

    # 2. Extract Ingredients Section
    ingredients_text: str | None = None
    ing_match = re.search(
        r"(?:ingredients|ingredient\s+list|ingredients\s*[:\-]?)\s*[:\-]?\s*([^\n\r]+(?:\n[^\n\r]+)*)",
        raw_text,
        re.IGNORECASE,
    )
    if ing_match:
        candidate_ing = ing_match.group(1).strip()
        stop_match = re.search(
            r"(?:nutrition\s+facts|nutritional\s+information|nutritional\s+panel|"
            r"approximate\s+values|mfg|mrp|best\s+before|batch\s+no|"
            r"allergen\s+advice|allergen\s+information|contains\s+wheat|"
            r"contains\s+milk|contains\s+soy|contains\s+added|"
            r"fssai\s+lic|lic\s+no|net\s+weight|net\s+qty|net\s+content)",
            candidate_ing,
            re.IGNORECASE,
        )
        if stop_match:
            candidate_ing = candidate_ing[: stop_match.start()].strip()
        ingredients_text = candidate_ing
    else:
        warnings.append(
            ExtractionWarning(
                code="MISSING_INGREDIENTS",
                message="No clear ingredients declaration statement was identified.",
            )
        )

    # 3. Identify nutrition lines
    nutrition_lines: list[str] = []
    for line in lines:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in NUTRITION_LINE_KEYWORDS):
            nutrition_lines.append(line)

    if not nutrition_lines:
        warnings.append(
            ExtractionWarning(
                code="NO_NUTRITION_PANEL",
                message="No clear nutritional information panel lines were identified.",
            )
        )

    # 4. Extract Nutrient Candidates
    candidates: dict[str, ExtractedNutrientCandidate] = {}

    # Serving size candidate
    serving_val, serving_unit, _ = _extract_serving_candidate(raw_text)
    if serving_val is None:
        warnings.append(
            ExtractionWarning(
                code="MISSING_SERVING_SIZE",
                message=(
                    "No explicit serving size was detected; please enter serving size manually."
                ),
            )
        )

    # Energy candidate (kJ vs kcal aware)
    energy_candidate, energy_warnings = _extract_energy_candidate(raw_text)
    warnings.extend(energy_warnings)
    if energy_candidate:
        candidates["energy_kcal"] = ExtractedNutrientCandidate(
            field_name="energy_kcal",
            raw_text=energy_candidate.raw_text,
            value=energy_candidate.value,
            unit=energy_candidate.unit,
            confidence=confidence,
        )

    # Other nutrient patterns (resilient to leader dots/dashes and sub-nutrient collisions)
    nutrient_patterns = [
        (
            "protein_g",
            r"(?:protein)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "carbohydrates_g",
            r"(?:total\s+carbohydrate|total\s+carbohydrates|total\s+carbs|carbohydrate|carbohydrates|carbs)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "added_sugar_g",
            r"(?:added\s+sugars?)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "total_sugar_g",
            r"(?:total\s+sugars?|of\s+which\s+(?:total\s+)?sugars?|(?<!added\s)(?<!added\s{2})(?<!added\s{3})sugars?)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "dietary_fiber_g",
            r"(?:dietary\s+fib(?:er|re)|fib(?:er|re))\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "saturated_fat_g",
            r"(?:saturated\s+fat|saturates|saturated\s+fatty\s+acids)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "trans_fat_g",
            r"(?:trans\s+fat|trans\s+fatty\s+acids)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "total_fat_g",
            r"(?:total\s+fat|(?<!saturated\s)(?<!trans\s)(?<!monounsaturated\s)(?<!polyunsaturated\s)\bfat)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "cholesterol_mg",
            r"(?:cholesterol)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(mg)?",
            "mg",
        ),
        (
            "sodium_mg",
            r"(?:sodium)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(mg)?",
            "mg",
        ),
    ]

    for field_name, regex, default_unit in nutrient_patterns:
        val, parsed_unit, raw_m = _extract_number_from_text(regex, raw_text)
        if val is not None:
            candidates[field_name] = ExtractedNutrientCandidate(
                field_name=field_name,
                raw_text=raw_m,
                value=val,
                unit=parsed_unit or default_unit,
                confidence=confidence,
            )

    return OcrExtractionResult(
        raw_text=raw_text,
        nutrition_lines=nutrition_lines,
        ingredients_text=ingredients_text,
        nutrient_candidates=candidates,
        serving_size_candidate=serving_val,
        serving_unit_candidate=serving_unit or "g",
        overall_confidence=confidence,
        warnings=warnings,
        verification_required=True,
    )
