"""
Category A: Comprehensive OCR Text Parsing and Heuristic Extraction Suite.

Validates parsing behavior across realistic Indian food label patterns, unit variations,
sub-nutrient collision prevention, and uncertainty warnings.
"""

import pytest

from app.extraction.parser import parse_ocr_text
from tests.fixtures.realistic_fixtures import load_realistic_fixtures


def test_realistic_fixtures_parsing() -> None:
    """
    Validates parsing across all canonical test fixtures.
    """
    fixtures = load_realistic_fixtures()
    assert len(fixtures) >= 8

    for fixture in fixtures:
        raw_text = fixture["raw_text"]
        result = parse_ocr_text(raw_text=raw_text, confidence=85.0)

        assert result.verification_required is True

        expected_parser = fixture.get("expected_parser", {})

        # Serving size check
        if expected_parser.get("serving_size") is not None:
            assert result.serving_size_candidate == pytest.approx(
                expected_parser["serving_size"], abs=0.1
            ), f"Failed serving size in {fixture['id']}"

        # Nutrient candidate checks
        for field_name, expected_val in expected_parser.items():
            if field_name in ("serving_size", "serving_unit", "energy_kj"):
                continue

            candidate = result.nutrient_candidates.get(field_name)
            if expected_val is None:
                assert candidate is None, (
                    f"Expected {field_name} to be None in {fixture['id']}, got {candidate}"
                )
            else:
                assert candidate is not None, (
                    f"Expected {field_name}={expected_val} in {fixture['id']}, "
                    "but candidate missing"
                )
                assert candidate.value == pytest.approx(expected_val, abs=0.1), (
                    f"Mismatch in {fixture['id']} for {field_name}: "
                    f"expected {expected_val}, got {candidate.value}"
                )


def test_energy_unit_handling_kcal_vs_kj() -> None:
    """
    Ensures strict separation of kcal and kJ units:
    - Never treat kJ as kcal
    - Dual units prefer explicit kcal
    - kJ-only converts to kcal via 4.184 and emits ENERGY_KJ_CONVERTED warning
    - Unlabeled energy emits ENERGY_UNIT_UNCERTAIN warning
    """
    # 1. Standard kcal
    res_kcal = parse_ocr_text("Energy: 420 kcal\nProtein: 5g")
    assert res_kcal.nutrient_candidates["energy_kcal"].value == 420.0
    assert res_kcal.nutrient_candidates["energy_kcal"].unit == "kcal"
    assert not any(w.code == "ENERGY_KJ_CONVERTED" for w in res_kcal.warnings)

    # 2. Dual units with kcal first
    res_dual_1 = parse_ocr_text("Energy: 420 kcal / 1757 kJ\nProtein: 5g")
    assert res_dual_1.nutrient_candidates["energy_kcal"].value == 420.0
    assert res_dual_1.nutrient_candidates["energy_kcal"].unit == "kcal"

    # 3. Dual units with kJ first
    res_dual_2 = parse_ocr_text("Energy: 1757 kJ / 420 kcal\nProtein: 5g")
    assert res_dual_2.nutrient_candidates["energy_kcal"].value == 420.0
    assert res_dual_2.nutrient_candidates["energy_kcal"].unit == "kcal"

    # 4. Dual units parenthesized: 420 kcal (1757 kJ)
    res_dual_3 = parse_ocr_text("Energy: 420 kcal (1757 kJ)\nProtein: 5g")
    assert res_dual_3.nutrient_candidates["energy_kcal"].value == 420.0
    assert res_dual_3.nutrient_candidates["energy_kcal"].unit == "kcal"

    # 5. kJ only - strictly convert via 4.184 and emit conversion warning
    res_kj_only = parse_ocr_text("Energy: 1883 kJ\nProtein: 7g")
    cand_kj = res_kj_only.nutrient_candidates["energy_kcal"]
    assert cand_kj.value == pytest.approx(450.0, abs=0.2)
    assert cand_kj.unit == "kcal"
    assert any(w.code == "ENERGY_KJ_CONVERTED" for w in res_kj_only.warnings)

    # 6. Energy without unit: emits uncertainty warning
    res_no_unit = parse_ocr_text("Energy: 450\nProtein: 8g")
    assert res_no_unit.nutrient_candidates["energy_kcal"].value == 450.0
    assert any(w.code == "ENERGY_UNIT_UNCERTAIN" for w in res_no_unit.warnings)


def test_sub_nutrient_collision_prevention() -> None:
    """
    Guarantees that sub-nutrients (added sugars, saturated fat, trans fat)
    do not hijack or corrupt parent nutrient extraction (total sugars, total fat).
    """
    # Case A: Added sugars declared before total sugars
    text_sugars = (
        "NUTRITION FACTS\nAdded Sugars: 6.0 g\nTotal Sugars: 18.0 g\nTotal Carbohydrate: 55.0 g"
    )
    res_sugars = parse_ocr_text(text_sugars)
    assert res_sugars.nutrient_candidates["added_sugar_g"].value == 6.0
    assert res_sugars.nutrient_candidates["total_sugar_g"].value == 18.0

    # Case B: Only added sugars declared, NO total sugars on label
    text_added_only = "NUTRITION INFORMATION\nAdded Sugars: 8.5 g\nTotal Carbohydrates: 40.0 g"
    res_added_only = parse_ocr_text(text_added_only)
    assert res_added_only.nutrient_candidates["added_sugar_g"].value == 8.5
    assert "total_sugar_g" not in res_added_only.nutrient_candidates

    # Case C: Saturated and trans fat declared before total fat
    text_fats = "NUTRITIONAL VALUES\nSaturated Fat: 4.5 g\nTrans Fat: 0.1 g\nTotal Fat: 14.0 g"
    res_fats = parse_ocr_text(text_fats)
    assert res_fats.nutrient_candidates["saturated_fat_g"].value == 4.5
    assert res_fats.nutrient_candidates["trans_fat_g"].value == 0.1
    assert res_fats.nutrient_candidates["total_fat_g"].value == 14.0

    # Case D: Only saturated fat declared, NO total fat on label
    text_sat_only = "NUTRITIONAL VALUES\nSaturated Fat: 3.2 g\nProtein: 5.0 g"
    res_sat_only = parse_ocr_text(text_sat_only)
    assert res_sat_only.nutrient_candidates["saturated_fat_g"].value == 3.2
    assert "total_fat_g" not in res_sat_only.nutrient_candidates


def test_serving_size_patterns() -> None:
    """
    Validates extraction of metric serving sizes from various Indian packaging formats:
    - Standard gram: 'Serving Size: 30g'
    - Parenthesized gram weight: 'Serving Size: 2 Cookies (24g)'
    - Parenthesized gram weight: 'Serving Size: 1 Pack (70g)'
    - Leading weight with description: 'Serving size: 30g (approx 2 tbsp)'
    - Discrete piece unit: 'Serving Size: 2 Biscuits'
    - Liquid volume: 'Serving Size: 200 ml'
    - Missing serving size with Per 100g table
    """
    # Standard 30g
    res1 = parse_ocr_text("Serving Size: 30g\nEnergy: 120 kcal")
    assert res1.serving_size_candidate == 30.0
    assert res1.serving_unit_candidate == "g"

    # Parenthesized weight in biscuits
    res2 = parse_ocr_text("Serving Size: 2 Cookies (24g)\nEnergy: 110 kcal")
    assert res2.serving_size_candidate == 24.0
    assert res2.serving_unit_candidate == "g"

    # Parenthesized weight in noodles pack
    res3 = parse_ocr_text("Serving Size: 1 Pack (70g)\nEnergy: 310 kcal")
    assert res3.serving_size_candidate == 70.0
    assert res3.serving_unit_candidate == "g"

    # Weight first, then description
    res4 = parse_ocr_text("Serving Size: 30g (Approx. 2 tbsp)\nEnergy: 160 kcal")
    assert res4.serving_size_candidate == 30.0
    assert res4.serving_unit_candidate == "g"

    # Discrete pieces without net weight
    res5 = parse_ocr_text("Serving Size: 2 Biscuits\nEnergy: 90 kcal")
    assert res5.serving_size_candidate == 2.0
    assert res5.serving_unit_candidate == "piece"

    # Liquid 200 ml
    res6 = parse_ocr_text("Serving Size: 200 ml\nEnergy: 95 kcal")
    assert res6.serving_size_candidate == 200.0
    assert res6.serving_unit_candidate == "ml"

    # Missing serving size with per 100g header
    res7 = parse_ocr_text("NUTRITIONAL INFORMATION\nPer 100g\nEnergy: 450 kcal")
    assert res7.serving_size_candidate is None
    assert any(w.code == "MISSING_SERVING_SIZE" for w in res7.warnings)


def test_split_lines_and_leader_dots() -> None:
    """
    Ensures parser handles leader dots, hyphens, and newline-separated fields.
    """
    # Leader dots
    text_dots = (
        "NUTRITION INFORMATION\n"
        "Energy ................... 450 kcal\n"
        "Protein .................. 6.5 g\n"
        "Total Carbohydrate ....... 78.0 g\n"
        "Total Fat ................ 12.5 g\n"
        "Sodium ................... 280 mg"
    )
    res_dots = parse_ocr_text(text_dots)
    assert res_dots.nutrient_candidates["energy_kcal"].value == 450.0
    assert res_dots.nutrient_candidates["protein_g"].value == 6.5
    assert res_dots.nutrient_candidates["carbohydrates_g"].value == 78.0
    assert res_dots.nutrient_candidates["total_fat_g"].value == 12.5
    assert res_dots.nutrient_candidates["sodium_mg"].value == 280.0

    # Newline separated nutrient name and value
    text_split = "NUTRITION FACTS\nEnergy:\n150 kcal\nProtein:\n4.0 g\nTotal Fat:\n6.0 g"
    res_split = parse_ocr_text(text_split)
    assert res_split.nutrient_candidates["energy_kcal"].value == 150.0
    assert res_split.nutrient_candidates["protein_g"].value == 4.0
    assert res_split.nutrient_candidates["total_fat_g"].value == 6.0


def test_ingredients_boundary_cleaning() -> None:
    """
    Verifies that packaging metadata after ingredients statements is excluded.
    """
    text = (
        "NUTRITION FACTS\nEnergy: 200 kcal\n\n"
        "INGREDIENTS: Refined Wheat Flour, Sugar, Palm Oil, Salt, Emulsifier (INS 322(i)).\n"
        "ALLERGEN ADVICE: Contains Wheat and Soy.\n"
        "Net Weight: 100g.\n"
        "Mfg Date: 10/26. Batch No: B-402.\n"
        "FSSAI Lic No: 10014011000123."
    )
    res = parse_ocr_text(text)
    assert res.ingredients_text is not None
    assert "Refined Wheat Flour" in res.ingredients_text
    assert "Emulsifier (INS 322(i))" in res.ingredients_text
    # Metadata sections must be truncated from ingredients_text
    assert "ALLERGEN ADVICE" not in res.ingredients_text
    assert "Net Weight" not in res.ingredients_text
    assert "Batch No" not in res.ingredients_text


def test_sparse_and_low_confidence_warnings() -> None:
    """
    Tests warning emission for sparse text, low confidence, and missing sections.
    """
    res_sparse = parse_ocr_text("Hi", confidence=30.0)
    warning_codes = [w.code for w in res_sparse.warnings]
    assert "SPARSE_TEXT" in warning_codes
    assert "LOW_CONFIDENCE" in warning_codes
    assert "MISSING_SERVING_SIZE" in warning_codes
    assert "MISSING_INGREDIENTS" in warning_codes
    assert "NO_NUTRITION_PANEL" in warning_codes
