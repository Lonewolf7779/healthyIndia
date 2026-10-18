"""
Phase 3: OCR and Nutrient Association Safety Test Suite.
Exhaustively tests Scenarios A through L to ensure deterministic OCR parsing,
fail-closed error handling, nutrient association safety, and plausibility verification.
"""

import io

from PIL import Image

from app.core.config import Settings
from app.extraction.adapter import MockOcrAdapter
from app.extraction.parser import parse_ocr_text
from app.extraction.quality import assess_image_quality
from app.services.extraction_service import ExtractionService


def _create_synthetic_image(
    width: int = 400,
    height: int = 400,
    color: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Scenario A: Correct association in standard format
def test_scenario_a_correct_association_standard_format():
    raw_text = (
        "NUTRITION FACTS\n"
        "Serving Size: 30g\n"
        "Energy: 140 kcal\n"
        "Protein: 2.5 g\n"
        "Carbohydrates: 20.0 g\n"
        "Total Sugars: 8.0 g\n"
        "Added Sugars: 6.0 g\n"
        "Dietary Fiber: 1.2 g\n"
        "Total Fat: 5.5 g\n"
        "Saturated Fat: 2.5 g\n"
        "Trans Fat: 0.05 g\n"
        "Cholesterol: 0 mg\n"
        "Sodium: 150 mg\n"
    )
    result = parse_ocr_text(raw_text)

    assert result.serving_size_candidate == 30.0
    assert result.serving_unit_candidate == "g"
    cands = result.nutrient_candidates
    assert cands["energy_kcal"].value == 140.0
    assert cands["protein_g"].value == 2.5
    assert cands["carbohydrates_g"].value == 20.0
    assert cands["total_sugar_g"].value == 8.0
    assert cands["added_sugar_g"].value == 6.0
    assert cands["dietary_fiber_g"].value == 1.2
    assert cands["total_fat_g"].value == 5.5
    assert cands["saturated_fat_g"].value == 2.5
    assert cands["trans_fat_g"].value == 0.05
    assert cands["cholesterol_mg"].value == 0.0
    assert cands["sodium_mg"].value == 150.0


# Scenario B: Wrong nutrient association defense (no swapping across lines)
def test_scenario_b_wrong_nutrient_association_defense():
    raw_text = (
        "NUTRITION FACTS\nServing Size: 40g\nProtein: 1.2 g\nTotal Fat: 8.5 g\nSodium: 220 mg\n"
    )
    result = parse_ocr_text(raw_text)
    cands = result.nutrient_candidates
    assert cands["protein_g"].value == 1.2
    assert cands["total_fat_g"].value == 8.5
    assert cands["sodium_mg"].value == 220.0
    assert "carbohydrates_g" not in cands


# Scenario C: 8/3 and 0/6 confusion handling
def test_scenario_c_digit_confusion_discrepancy_detection():
    settings = Settings()
    pass_a = "Energy: 180 kcal\nProtein: 8.0 g\nTotal Fat: 6.0 g"
    pass_b = "Energy: 130 kcal\nProtein: 3.0 g\nTotal Fat: 0.0 g"

    mock_adapter = MockOcrAdapter(
        mock_text=pass_a,
        pass_a_text=pass_a,
        pass_b_text=pass_b,
        pass_discrepancy=True,
    )
    service = ExtractionService(settings=settings, ocr_adapter=mock_adapter)
    img_bytes = _create_synthetic_image()
    res = service.process_image(img_bytes)

    assert res.verification_required is True
    # Discrepancy warning should be raised
    discrepancy_warnings = [
        w
        for w in res.warnings
        if "discrepancy" in w.message.lower() or w.code == "OCR_PASS_DISCREPANCY"
    ]
    assert len(discrepancy_warnings) > 0


# Scenario D: Dropped decimal point detected by plausibility
def test_scenario_d_dropped_decimal_point_plausibility_check():
    # If 1.2g becomes 120g or macro sum exceeds 105g per 100g
    raw_text = (
        "NUTRITIONAL INFORMATION (Per 100g)\n"
        "Energy: 520 kcal\n"
        "Protein: 30 g\n"
        "Carbohydrates: 70 g\n"
        "Total Fat: 40 g\n"  # 30 + 70 + 40 = 140g > 105g physical maximum
    )
    result = parse_ocr_text(raw_text)
    warning_codes = [w.code for w in result.warnings]
    assert "PLAUSIBILITY_MACRO_SUM_EXCEEDS_100G" in warning_codes


# Scenario E: mg vs g confusion check
def test_scenario_e_mg_vs_g_confusion_handling():
    # If Sodium is parsed from grams, it converts to mg and flags extreme quantity
    raw_text = (
        "NUTRITION FACTS\n"
        "Serving Size: 30g\n"
        "Sodium: 250 g\n"  # Implausible: 250g sodium in 30g serving!
    )
    result = parse_ocr_text(raw_text)
    cand = result.nutrient_candidates.get("sodium_mg")
    assert cand is not None
    assert cand.value == 250000.0
    has_extreme_sodium = any("SODIUM" in w.code for w in result.warnings)
    assert cand.plausibility in ("suspicious", "contradictory") or has_extreme_sodium


# Scenario F: "Trace", "<0.5g", "Nil", "Not Detected" handling
def test_scenario_f_trace_nil_less_than_handling():
    raw_text = (
        "NUTRITION INFORMATION\n"
        "Serving Size: 25g\n"
        "Energy: 100 kcal\n"
        "Trans Fat: Nil\n"
        "Cholesterol: Not Detected\n"
        "Added Sugars: < 0.5 g\n"
        "Dietary Fiber: Trace\n"
    )
    result = parse_ocr_text(raw_text)
    # The parser must not crash and must safely handle these values
    assert result.serving_size_candidate == 25.0
    cands = result.nutrient_candidates
    # Values that are < 0.5 may be parsed as 0.5 or preserved safely
    if "added_sugar_g" in cands:
        assert cands["added_sugar_g"].value is not None


# Scenario G: Column order mismatch (Per 100g vs Per Serving)
def test_scenario_g_column_order_mismatch():
    raw_text = (
        "NUTRITIONAL FACTS\n"
        "Serving Size: 30g\n"
        "Nutrient        Per 100g    Per Serve\n"
        "Energy (kcal)   450         135\n"
        "Protein (g)     8.0         2.4\n"
        "Carbohydrate(g) 60.0        18.0\n"
    )
    result = parse_ocr_text(raw_text)
    assert result.column_basis_detected == "dual_column"
    assert result.per_100_candidates["energy_kcal"].value == 450.0
    assert result.per_serving_candidates["energy_kcal"].value == 135.0
    assert result.per_100_candidates["protein_g"].value == 8.0
    assert result.per_serving_candidates["protein_g"].value == 2.4


# Scenario H: Multi-row hierarchical nutrient combine
def test_scenario_h_multi_row_hierarchical_combine():
    raw_text = (
        "NUTRITION FACTS\n"
        "Serving Size: 20g\n"
        "Carbohydrates: 15 g\n"
        "  - Total Sugars: 6.0 g\n"
        "  - Added Sugars: 4.5 g\n"
        "Total Fat: 4.0 g\n"
        "  - Saturated Fat: 2.0 g\n"
        "  - Trans Fat: 0.02 g\n"
    )
    result = parse_ocr_text(raw_text)
    cands = result.nutrient_candidates
    assert cands["carbohydrates_g"].value == 15.0
    assert cands["total_sugar_g"].value == 6.0
    assert cands["added_sugar_g"].value == 4.5
    assert cands["total_fat_g"].value == 4.0
    assert cands["saturated_fat_g"].value == 2.0
    assert cands["trans_fat_g"].value == 0.02


# Scenario I: Dual-pass OCR conflict
def test_scenario_i_dual_pass_ocr_conflict():
    settings = Settings()
    pass_a = "Energy: 200 kcal\nProtein: 5g"
    pass_b = "Energy: 250 kcal\nProtein: 9g"

    mock_adapter = MockOcrAdapter(
        mock_text=pass_a,
        pass_a_text=pass_a,
        pass_b_text=pass_b,
        pass_discrepancy=True,
    )
    service = ExtractionService(settings=settings, ocr_adapter=mock_adapter)
    img_bytes = _create_synthetic_image()
    res = service.process_image(img_bytes)

    assert res.verification_required is True
    assert any(w.code == "OCR_PASS_DISCREPANCY" for w in res.warnings)


# Scenario J: Empty text and exception handling
def test_scenario_j_empty_text_and_malformed_input():
    empty_result = parse_ocr_text("")
    assert empty_result.nutrient_candidates == {}
    assert empty_result.verification_required is True

    whitespace_result = parse_ocr_text("   \n\t  \n  ")
    assert whitespace_result.nutrient_candidates == {}

    garbage_result = parse_ocr_text("@@@###$$$ %%% ^^^ &&& *** ((( )))")
    assert garbage_result.nutrient_candidates == {}


# Scenario K: Image distortion and quality gates
def test_scenario_k_image_distortion_and_quality_gates():
    # 1. Extremely low contrast / solid color image
    solid_img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    solid_buf = io.BytesIO()
    solid_img.save(solid_buf, format="PNG")
    quality = assess_image_quality(solid_buf.getvalue())
    assert quality.is_acceptable is False or len(quality.quality_warnings) > 0


# Scenario L: Non-nutrition text rejection
def test_scenario_l_non_nutrition_text_rejection():
    raw_text = (
        "100% WHOLE GRAIN GOODNESS!\n"
        "ZERO CHOLESTEROL & NO ARTIFICIAL COLOURS\n"
        "BEST BEFORE 12 MONTHS FROM MANUFACTURE\n"
        "NET WEIGHT 500g\n"
        "FSSAI Lic. No. 10014022003211\n"
        "MANUFACTURED BY ABC FOODS LTD.\n"
        "KEEP AWAY FROM DIRECT SUNLIGHT\n"
        "ENERGY FOR YOUR ACTIVE LIFESTYLE!\n"
    )
    result = parse_ocr_text(raw_text)
    # Serving size should not be confused with net weight 500g
    assert result.serving_size_candidate is None or result.serving_size_candidate != 500.0
    # No spurious nutrients should be extracted
    assert "protein_g" not in result.nutrient_candidates
    assert "sodium_mg" not in result.nutrient_candidates
