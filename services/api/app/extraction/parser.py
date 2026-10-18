"""
Pure deterministic parsing heuristics for raw OCR text.
Extracts candidate nutrition values, detects ingredient sections,
separates multi-column tables, validates physical plausibility,
and generates uncertainty warnings without making definitive truth claims.
"""

import re
from typing import Final

from app.extraction.models import (
    ExtractedNutrientCandidate,
    ExtractionWarning,
    OcrExtractionResult,
)
from app.extraction.plausibility import audit_table_plausibility

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
SALT_TO_SODIUM_MG_FACTOR: Final[float] = 393.4  # 1g NaCl = 393.4 mg Na (39.34% Na)


def _clean_ocr_text(text: str) -> str:
    """
    Standardizes common OCR artifacts like decimal commas and letter substitutions
    in numeric contexts without corrupting words.
    """
    # Decimal commas: e.g. '12,5 g' -> '12.5 g'
    cleaned = re.sub(r"(?<=\d),(?=\d)", ".", text)
    # Common OCR letter 'O' or 'o' in numeric contexts: e.g. '1O5', '2.O', '1O.5'
    cleaned = re.sub(r"(?<=\d)[Oo](?=\d|\.|\s*g|\s*mg|\s*kcal|\s*%)", "0", cleaned)
    cleaned = re.sub(r"(?<=\.)[Oo](?=\d|\s*g|\s*mg|\s*kcal|\s*%)", "0", cleaned)
    return cleaned


def _detect_table_columns(raw_text: str) -> tuple[str, list[str]]:
    """
    Detects whether nutrition table declares Per 100g/ml, Per Serving, or dual columns.
    """
    has_100 = bool(re.search(r"per\s*100\s*(?:g|ml)\b", raw_text, re.IGNORECASE))
    has_serve = bool(
        re.search(
            r"(?:per\s*(?:serve|serving)|serv(?:ing|e)?\s*size|per\s*\d+\s*(?:g|ml))\b",
            raw_text,
            re.IGNORECASE,
        )
    )

    if has_100 and has_serve:
        return "dual_column", ["per_100", "per_serving"]
    if has_100:
        return "per_100g", ["per_100"]
    if has_serve:
        return "per_serving", ["per_serving"]
    return "single_column", ["default"]


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

    # Clean phrase
    phrase_clean = _clean_ocr_text(phrase)

    # 1. Look for explicit kcal/cal value first
    m_kcal = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:kcal|cal)\b", phrase_clean, re.IGNORECASE)
    if m_kcal:
        val = float(m_kcal.group(1))
        return (
            ExtractedNutrientCandidate(
                field_name="energy_kcal",
                raw_text=line_text,
                value=val,
                unit="kcal",
                source="ocr",
                status="unconfirmed",
            ),
            warnings,
        )

    # 2. Look for kJ without kcal: convert deterministically via 4.184 factor
    m_kj = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:kj)\b", phrase_clean, re.IGNORECASE)
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
                source="converted",
                status="unconfirmed",
            ),
            warnings,
        )

    # 3. Numeric value without unit: flag uncertainty
    m_num = re.search(r"([0-9]+(?:\.[0-9]+)?)\b", phrase_clean)
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
                source="ocr",
                status="unconfirmed",
            ),
            warnings,
        )

    return None, warnings


def _extract_serving_candidate(raw_text: str) -> tuple[float | None, str, str]:
    """
    Extracts serving size candidate, giving precedence to parenthesized metric weights
    (e.g. '2 Cookies (24g)' -> (24.0, 'g')).
    """
    cleaned_text = _clean_ocr_text(raw_text)

    m = re.search(
        r"(?:serv(?:ing|e)?\.?\s+size|per\s+serve(?:ing)?)\s*[:\.\-_=]*\s*([^\n\r;]+)",
        cleaned_text,
        re.IGNORECASE,
    )
    if not m:
        m_standalone = re.search(
            r"(?:serv(?:ing|e)?\.?)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g|ml|piece|portion)?",
            cleaned_text,
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


def _extract_all_numbers_from_line(line: str) -> list[tuple[float, str | None]]:
    """
    Extracts all distinct numbers with their units from a line.
    E.g. 'Total Sugars (g) 25.0 7.5 15%' -> [(25.0, 'g'), (7.5, 'g'), (15.0, '%')]
    """
    matches = re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*(g|mg|kcal|kj|%|ml)?\b", line, re.IGNORECASE)
    results: list[tuple[float, str | None]] = []
    for m in matches:
        try:
            val = float(m.group(1))
            unit = m.group(2).lower() if m.group(2) else None
            results.append((val, unit))
        except ValueError:
            continue
    return results


def parse_ocr_text(raw_text: str, confidence: float | None = None) -> OcrExtractionResult:
    """
    Heuristically partitions raw OCR text into candidate sections and values,
    detects multi-column tables, checks physical plausibility, and emits uncertainty warnings.
    """
    cleaned_text = _clean_ocr_text(raw_text)
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
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
        cleaned_text,
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

    # 3. Identify nutrition lines & table columns
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

    column_basis_detected, _ = _detect_table_columns(cleaned_text)

    # 4. Serving size candidate
    serving_val, serving_unit, _ = _extract_serving_candidate(cleaned_text)
    if serving_val is None:
        warnings.append(
            ExtractionWarning(
                code="MISSING_SERVING_SIZE",
                message=(
                    "No explicit serving size was detected; please enter serving size manually."
                ),
            )
        )

    # 5. Extract Candidates
    candidates: dict[str, ExtractedNutrientCandidate] = {}
    per_100_candidates: dict[str, ExtractedNutrientCandidate] = {}
    per_serving_candidates: dict[str, ExtractedNutrientCandidate] = {}

    # Energy candidate
    energy_candidate, energy_warnings = _extract_energy_candidate(cleaned_text)
    warnings.extend(energy_warnings)
    if energy_candidate:
        candidates["energy_kcal"] = energy_candidate

    # Optional parenthesized unit spec on nutrient label: e.g. 'Protein (g)' or 'Energy (kcal)'
    u_spec = r"(?:\s*\((?:g|mg|kcal|kj)\))?"

    # Nutrient patterns requiring numeric values following optional delimiter/leader dots
    nutrient_patterns = [
        (
            "protein_g",
            r"(?:\bprotein)" + u_spec + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "carbohydrates_g",
            r"(?:total\s+carbohydrate|total\s+carbohydrates|total\s+carbs|carbohydrate|carbohydrates|\bcarbs)"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "added_sugar_g",
            r"(?:added\s+sugars?)" + u_spec + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "total_sugar_g",
            r"(?:total\s+sugars?|of\s+which\s+(?:total\s+)?sugars?|(?<!added\s)(?<!added\s{2})(?<!added\s{3})\bsugars?)"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "dietary_fiber_g",
            r"(?:dietary\s+fib(?:er|re)|\bfib(?:er|re))"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "saturated_fat_g",
            r"(?:saturated\s+fat|\bsaturates|saturated\s+fatty\s+acids)"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "trans_fat_g",
            r"(?:trans\s+fat|trans\s+fatty\s+acids)"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "total_fat_g",
            r"(?:total\s+fat|(?<!saturated\s)(?<!trans\s)(?<!monounsaturated\s)(?<!polyunsaturated\s)\bfat)"
            + u_spec
            + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "g",
        ),
        (
            "cholesterol_mg",
            r"(?:\bcholesterol)" + u_spec + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "mg",
        ),
        (
            "sodium_mg",
            r"(?:\bsodium)" + u_spec + r"\s*[:\.\-_=]*\s*((?:[\.\-_\s]*[0-9]+[^\n\r;]*))",
            "mg",
        ),
    ]

    for field_name, regex, default_unit in nutrient_patterns:
        m = re.search(regex, cleaned_text, re.IGNORECASE)
        if not m:
            continue

        raw_match_line = m.group(0).strip()
        phrase = m.group(1).strip()
        numbers = _extract_all_numbers_from_line(phrase)

        if not numbers:
            continue

        # Filter out percentage numbers (e.g. '15%') unless no other numbers exist
        gram_numbers = [n for n in numbers if n[1] != "%"]
        if not gram_numbers:
            gram_numbers = numbers

        # Dual column handling
        if len(gram_numbers) >= 2 and column_basis_detected == "dual_column":
            val_100, unit_100 = gram_numbers[0]
            val_serv, unit_serv = gram_numbers[1]

            cand_100 = ExtractedNutrientCandidate(
                field_name=field_name,
                raw_text=raw_match_line,
                value=val_100,
                unit=unit_100 or default_unit,
                confidence=confidence,
                column="per_100g",
                source="ocr",
                status="unconfirmed",
            )
            cand_serv = ExtractedNutrientCandidate(
                field_name=field_name,
                raw_text=raw_match_line,
                value=val_serv,
                unit=unit_serv or default_unit,
                confidence=confidence,
                column="per_serving",
                source="ocr",
                status="unconfirmed",
            )
            per_100_candidates[field_name] = cand_100
            per_serving_candidates[field_name] = cand_serv
            # Default candidates dict to per-100g or per-serving
            candidates[field_name] = cand_serv if serving_val is not None else cand_100
        else:
            val, parsed_unit = gram_numbers[0]
            cand = ExtractedNutrientCandidate(
                field_name=field_name,
                raw_text=raw_match_line,
                value=val,
                unit=parsed_unit or default_unit,
                confidence=confidence,
                column=column_basis_detected,
                source="ocr",
                status="unconfirmed",
            )
            candidates[field_name] = cand
            if column_basis_detected == "per_100g":
                per_100_candidates[field_name] = cand
            elif column_basis_detected == "per_serving":
                per_serving_candidates[field_name] = cand

    # 6. Salt Detection & Conversion to Sodium
    if "sodium_mg" not in candidates:
        salt_m = re.search(
            r"(?:salt|iodized\s+salt|table\s+salt)\s*[:\.\-_=]*\s*([0-9]+(?:\.[0-9]+)?)\s*(g|mg)?\b",
            cleaned_text,
            re.IGNORECASE,
        )
        if salt_m:
            salt_val = float(salt_m.group(1))
            salt_unit = (salt_m.group(2) or "g").lower()
            if salt_unit == "mg":
                salt_g = salt_val / 1000.0
            else:
                salt_g = salt_val

            sodium_mg_val = round(salt_g * SALT_TO_SODIUM_MG_FACTOR, 1)
            warnings.append(
                ExtractionWarning(
                    code="SALT_CONVERTED_TO_SODIUM",
                    message=(
                        f"Label declared Salt ({salt_val}{salt_unit}). Converted to equivalent "
                        f"Sodium ({sodium_mg_val}mg Na) using FSSAI 393.4 mg/g factor. "
                        "Please verify against physical label."
                    ),
                )
            )
            candidates["sodium_mg"] = ExtractedNutrientCandidate(
                field_name="sodium_mg",
                raw_text=salt_m.group(0).strip(),
                value=sodium_mg_val,
                unit="mg",
                confidence=confidence,
                source="converted",
                status="unconfirmed",
            )

    # 7. Audit Physical Plausibility
    cand_values = {k: v.value for k, v in candidates.items()}
    audit_res = audit_table_plausibility(
        cand_values,
        serving_size=serving_val,
        basis="per_serving" if column_basis_detected == "per_serving" else "per_100g",
    )
    warnings.extend(audit_res.warnings)

    # Annotate candidates with plausibility outcome
    annotated_candidates: dict[str, ExtractedNutrientCandidate] = {}
    for k, v in candidates.items():
        plaus = audit_res.field_plausibility.get(k, "plausible")
        warn_msg = audit_res.field_warnings.get(k)
        annotated_candidates[k] = ExtractedNutrientCandidate(
            field_name=v.field_name,
            raw_text=v.raw_text,
            value=v.value,
            unit=v.unit,
            confidence=v.confidence,
            source=v.source,
            status=v.status,
            plausibility=plaus,
            plausibility_warning=warn_msg,
            column=v.column,
        )

    return OcrExtractionResult(
        raw_text=raw_text,
        column_basis_detected=column_basis_detected,
        nutrition_lines=nutrition_lines,
        ingredients_text=ingredients_text,
        nutrient_candidates=annotated_candidates,
        per_100_candidates=per_100_candidates,
        per_serving_candidates=per_serving_candidates,
        serving_size_candidate=serving_val,
        serving_unit_candidate=serving_unit or "g",
        overall_confidence=confidence,
        warnings=warnings,
        verification_required=True,
    )
