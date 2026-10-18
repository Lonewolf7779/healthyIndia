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
        # Take text after keyword and stop if a distinct section header occurs
        candidate_ing = ing_match.group(1).strip()
        stop_match = re.search(
            r"(?:nutrition\s+facts|nutritional\s+information|mfg|mrp|best\s+before|batch\s+no)",
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

    # Serving size
    serving_val, serving_unit, s_raw = _extract_number_from_text(
        r"(?:serving\s+size|serve\s+size|per\s+serve(?:ing)?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g|ml|piece|portion)?",
        raw_text,
    )
    if serving_val is None:
        # Try finding standalone e.g. "30g" near "serve"
        serving_val, serving_unit, s_raw = _extract_number_from_text(
            r"(?:serving|serve)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g|ml)?",
            raw_text,
        )

    if serving_val is None:
        warnings.append(
            ExtractionWarning(
                code="MISSING_SERVING_SIZE",
                message=(
                    "No explicit serving size was detected; please enter serving size manually."
                ),
            )
        )

    nutrient_patterns = [
        (
            "energy_kcal",
            r"(?:energy|calories|caloric\s+value)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(kcal|cal)?",
            "kcal",
        ),
        (
            "protein_g",
            r"(?:protein)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "carbohydrates_g",
            r"(?:carbohydrate|carbohydrates|total\s+carbohydrate|carbs)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "added_sugar_g",
            r"(?:added\s+sugars?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "total_sugar_g",
            r"(?:total\s+sugars?|sugars?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "dietary_fiber_g",
            r"(?:dietary\s+fib(?:er|re)|fib(?:er|re))\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "total_fat_g",
            r"(?:total\s+fat|fat)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "saturated_fat_g",
            r"(?:saturated\s+fat|saturates|saturated\s+fatty\s+acids)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "trans_fat_g",
            r"(?:trans\s+fat|trans\s+fatty\s+acids)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g)?",
            "g",
        ),
        (
            "cholesterol_mg",
            r"(?:cholesterol)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg)?",
            "mg",
        ),
        (
            "sodium_mg",
            r"(?:sodium)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg)?",
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
