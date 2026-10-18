"""
Mathematical Integrity and Plausibility Verification Suite.

Validates explicit formulas, dimensional analysis, justified physical constraints,
independent expected results, rounding rules, and adversarial edge cases.
"""

import pytest

from app.extraction.adapter import MockOcrAdapter
from app.extraction.parser import SALT_TO_SODIUM_MG_FACTOR, parse_ocr_text
from app.extraction.plausibility import audit_table_plausibility
from app.nutrition.calculator import analyze_nutrition, normalize_nutrients
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FoodForm


class TestMathematicalIntegrity:
    """Rigorous verification of calculations, dimensional analysis, and constraints."""

    # -------------------------------------------------------------------------
    # 1. Negative Values and Boundary Conditions
    # -------------------------------------------------------------------------
    def test_negative_nutrient_rejection(self) -> None:
        """Domain calculator MUST reject negative nutrient amounts."""
        with pytest.raises(ValueError, match="physically impossible"):
            RawNutrientInput(
                serving_size=30.0,
                serving_unit=ServingUnit.G,
                basis=ServingBasis.PER_SERVING,
                protein_g=-2.5,
            )
            # normalize_nutrients is called internally by analyze_nutrition
            normalize_nutrients(
                RawNutrientInput(
                    serving_size=30.0,
                    serving_unit=ServingUnit.G,
                    basis=ServingBasis.PER_SERVING,
                    protein_g=-2.5,
                )
            )

    def test_zero_vs_missing_strict_distinction(self) -> None:
        """
        0.0 is a declared quantity; None is an unlisted/unverified nutrient.
        Missing values must NEVER silently become 0.0.
        """
        inp = RawNutrientInput(
            serving_size=50.0,
            serving_unit=ServingUnit.G,
            basis=ServingBasis.PER_SERVING,
            food_form=FoodForm.SOLID,
            protein_g=0.0,  # Declared zero
            total_fat_g=None,  # Missing / unlisted
            added_sugar_g=0.0,  # Declared zero
            sodium_mg=None,  # Missing
        )
        res = analyze_nutrition(inp)

        # Protein (declared zero)
        assert res.per_serving["protein_g"] == 0.0
        assert res.per_100["protein_g"] == 0.0
        p_comp = next(c for c in res.daily_value_comparisons if c.nutrient_key == "protein_g")
        assert p_comp.amount == 0.0
        assert p_comp.percentage_of_daily_value == 0.0
        assert p_comp.status == "calculated"

        # Fat (missing)
        assert res.per_serving["total_fat_g"] is None
        assert res.per_100["total_fat_g"] is None
        f_comp = next(c for c in res.daily_value_comparisons if c.nutrient_key == "total_fat_g")
        assert f_comp.amount is None
        assert f_comp.percentage_of_daily_value is None
        assert f_comp.status == "not_provided"

        # Data completeness tracking
        assert res.is_complete is False
        assert "total_fat_g" in res.missing_nutrients
        assert "sodium_mg" in res.missing_nutrients
        assert "protein_g" not in res.missing_nutrients

    # -------------------------------------------------------------------------
    # 2. Dimensional Analysis and Scaling Boundaries
    # -------------------------------------------------------------------------
    def test_serving_size_scaling_arithmetic(self) -> None:
        """
        Asserts exact scaling formulas:
        per_100 = round(val * (100.0 / serving_size), 2)
        per_serving = round(val * (serving_size / 100.0), 2)
        """
        # Serving size 33.33g (scale factor = 3.00030003...)
        inp = RawNutrientInput(
            serving_size=33.33,
            serving_unit=ServingUnit.G,
            basis=ServingBasis.PER_SERVING,
            food_form=FoodForm.SOLID,
            protein_g=3.33,
            total_fat_g=6.66,
        )
        res = analyze_nutrition(inp)
        # 3.33 * (100 / 33.33) = 9.991 -> 9.99
        assert res.per_100["protein_g"] == round(3.33 * (100.0 / 33.33), 2)
        # 6.66 * (100 / 33.33) = 19.98199 -> 19.98
        assert res.per_100["total_fat_g"] == round(6.66 * (100.0 / 33.33), 2)

    def test_discrete_units_prevent_per_100g_extrapolation(self) -> None:
        """Pieces or portions without gram weights must not be scaled to 100g."""
        inp = RawNutrientInput(
            serving_size=1.0,
            serving_unit=ServingUnit.PIECE,
            basis=ServingBasis.PER_SERVING,
            food_form=FoodForm.SOLID,
            protein_g=5.0,
            energy_kcal=120.0,
        )
        res = analyze_nutrition(inp)
        assert res.per_100["protein_g"] is None
        assert res.per_100["energy_kcal"] is None
        assert any(f.id == "discrete_serving_unit" for f in res.flags)

    # -------------------------------------------------------------------------
    # 3. Stoichiometry: Salt to Sodium Conversion
    # -------------------------------------------------------------------------
    def test_salt_to_sodium_stoichiometry(self) -> None:
        """
        Molar mass NaCl = 58.4428 g/mol; Na = 22.9898 g/mol.
        Fraction Na in NaCl = 22.9898 / 58.4428 = 0.393372 (39.34%).
        1.0g Salt = 393.4 mg Sodium.
        """
        assert pytest.approx(SALT_TO_SODIUM_MG_FACTOR, abs=0.1) == (22.98977 / 58.44277) * 1000.0

        # Test single-column salt in grams
        res_g = parse_ocr_text("Energy: 200 kcal\nSalt: 2.5 g")
        assert res_g.nutrient_candidates["sodium_mg"].value == round(2.5 * 393.4, 1)

        # Test single-column salt in milligrams
        res_mg = parse_ocr_text("Energy: 200 kcal\nSalt: 500 mg")
        assert res_mg.nutrient_candidates["sodium_mg"].value == round(0.5 * 393.4, 1)

        # Test dual-column salt
        dual_text = (
            "NUTRITIONAL FACTS\n"
            "Per 100g | Per Serving (25g)\n"
            "Energy (kcal) 400 100\n"
            "Salt (g) 1.2 0.3"
        )
        res_dual = parse_ocr_text(dual_text)
        assert res_dual.per_100_candidates["sodium_mg"].value == round(1.2 * 393.4, 1)
        assert res_dual.per_serving_candidates["sodium_mg"].value == round(0.3 * 393.4, 1)

    # -------------------------------------------------------------------------
    # 4. Added Sugar vs Total Sugar with Rounding Tolerances
    # -------------------------------------------------------------------------
    def test_added_sugar_vs_total_sugar_bounds(self) -> None:
        """
        Added sugars cannot chemically exceed total mono- and disaccharides.
        A 0.2g tolerance accommodates independent regulatory rounding.
        """
        # Case A: Clear contradiction (> 0.2g excess)
        res_contra = audit_table_plausibility({"total_sugar_g": 5.0, "added_sugar_g": 8.0})
        assert res_contra.field_plausibility["added_sugar_g"] == "contradictory"
        assert any(w.code == "PLAUSIBILITY_ADDED_SUGAR_EXCEEDS_TOTAL" for w in res_contra.warnings)

        # Case B: Slight rounding discrepancy (<= 0.2g excess)
        res_round = audit_table_plausibility({"total_sugar_g": 1.0, "added_sugar_g": 1.1})
        assert res_round.field_plausibility["added_sugar_g"] == "suspicious"
        assert any(
            w.code == "PLAUSIBILITY_ADDED_SUGAR_ROUNDING_DISCREPANCY" for w in res_round.warnings
        )

        # Case C: Fully valid (added <= total)
        res_valid = audit_table_plausibility({"total_sugar_g": 10.0, "added_sugar_g": 6.0})
        assert res_valid.field_plausibility["added_sugar_g"] == "plausible"
        assert not any("SUGAR" in w.code for w in res_valid.warnings)

    # -------------------------------------------------------------------------
    # 5. Saturated and Trans Fat vs Total Fat
    # -------------------------------------------------------------------------
    def test_fat_components_bounds(self) -> None:
        """Saturated and trans fatty acids are chemical subclasses of total lipids."""
        # Saturated fat exceeds total fat
        res_sat = audit_table_plausibility({"total_fat_g": 4.0, "saturated_fat_g": 6.0})
        assert res_sat.field_plausibility["saturated_fat_g"] == "contradictory"

        # Trans fat exceeds total fat
        res_trans = audit_table_plausibility({"total_fat_g": 2.0, "trans_fat_g": 3.0})
        assert res_trans.field_plausibility["trans_fat_g"] == "contradictory"

        # Combined sub-fats exceed total fat
        res_comb = audit_table_plausibility(
            {"total_fat_g": 5.0, "saturated_fat_g": 3.0, "trans_fat_g": 3.0}
        )
        assert any(w.code == "PLAUSIBILITY_FAT_COMPONENTS_EXCEED_TOTAL" for w in res_comb.warnings)

    # -------------------------------------------------------------------------
    # 6. Macronutrient Mass Bound (Solid 100g vs Liquid 100ml Density)
    # -------------------------------------------------------------------------
    def test_macronutrient_mass_bound_consistency(self) -> None:
        """
        In 100g of solid food: sum of macros <= 105g (5g analytical tolerance).
        In 100ml of liquid: density can reach 1.45 g/ml (syrups/honey), mass <= 150g.
        """
        # Solid food exceeding 105g
        res_solid_excess = audit_table_plausibility(
            {"protein_g": 20.0, "carbohydrates_g": 60.0, "total_fat_g": 35.0},  # Sum = 115g
            basis="per_100g",
        )
        assert any(
            w.code == "PLAUSIBILITY_MACRO_SUM_EXCEEDS_100G" for w in res_solid_excess.warnings
        )

        # High-density liquid syrup (120g carbs in 100ml, density ~1.35) -> PLAUSIBLE
        res_liquid_syrup = audit_table_plausibility(
            {"protein_g": 0.5, "carbohydrates_g": 115.0, "total_fat_g": 0.0},  # Sum = 115.5g
            basis="per_100ml",
        )
        assert not any(
            w.code == "PLAUSIBILITY_MACRO_SUM_EXCEEDS_100G" for w in res_liquid_syrup.warnings
        )

        # Liquid exceeding 150g limit -> flags
        res_liquid_excess = audit_table_plausibility(
            {"protein_g": 20.0, "carbohydrates_g": 135.0, "total_fat_g": 20.0},  # Sum = 175g
            basis="per_100ml",
        )
        assert any(
            w.code == "PLAUSIBILITY_MACRO_SUM_EXCEEDS_100G" for w in res_liquid_excess.warnings
        )

    # -------------------------------------------------------------------------
    # 7. Atwater Calorie Consistency and Exceptions
    # -------------------------------------------------------------------------
    def test_atwater_calorie_consistency_and_exceptions(self) -> None:
        """
        Standard Atwater: 4 kcal/g protein, 4 kcal/g carbs, 9 kcal/g fat.
        Tolerance: Max(35 kcal, 35% diff) to accommodate fiber (2 kcal/g), polyols, and acids.
        """
        # Consistent energy
        res_ok = audit_table_plausibility(
            {
                "energy_kcal": 330.0,
                "protein_g": 10.0,  # 40 kcal
                "carbohydrates_g": 50.0,  # 200 kcal
                "total_fat_g": 10.0,  # 90 kcal -> Total 330
            }
        )
        assert not any(
            w.code == "PLAUSIBILITY_ATWATER_CALORIE_DISCREPANCY" for w in res_ok.warnings
        )

        # Extreme divergence: declared 650 kcal vs expected 330 kcal
        res_divergent = audit_table_plausibility(
            {
                "energy_kcal": 650.0,
                "protein_g": 10.0,
                "carbohydrates_g": 50.0,
                "total_fat_g": 10.0,
            }
        )
        assert any(
            w.code == "PLAUSIBILITY_ATWATER_CALORIE_DISCREPANCY" for w in res_divergent.warnings
        )

    # -------------------------------------------------------------------------
    # 8. Dual-Pass Failure Mode: Agreement When Both Passes Are Wrong
    # -------------------------------------------------------------------------
    def test_dual_pass_agreement_when_both_passes_wrong(self) -> None:
        """
        If an ink smudge causes both CLAHE and Otsu to extract 'Protein: 0g'
        instead of 'Protein: 8g', pass_discrepancy will be False.
        The system must still require explicit manual user verification.
        """
        adapter = MockOcrAdapter(
            mock_text="Protein: 0g\nFat: 5g",
            mock_confidence=92.0,
            pass_a_text="Protein: 0g\nFat: 5g",
            pass_b_text="Protein: 0g\nFat: 5g",
            pass_discrepancy=False,
        )
        out = adapter.extract_text(b"corrupted_char_image")
        assert out.pass_discrepancy is False

        res = parse_ocr_text(out.raw_text, confidence=out.confidence)
        # Even though passes agreed, verification is ALWAYS required
        assert res.verification_required is True
        assert res.nutrient_candidates["protein_g"].status == "unconfirmed"

    # -------------------------------------------------------------------------
    # 9. OCR Decimal and Digit Confusions
    # -------------------------------------------------------------------------
    def test_ocr_decimal_comma_and_letter_o(self) -> None:
        """Handles comma decimals (1,5g) and letter 'O' in numeric positions."""
        raw = "Energy: 1O5 kcal\nProtein: 1,5 g\nTotal Fat: 2.O g\nSodium: 1O.5 mg"
        res = parse_ocr_text(raw)
        assert res.nutrient_candidates["energy_kcal"].value == 105.0
        assert res.nutrient_candidates["protein_g"].value == 1.5
        assert res.nutrient_candidates["total_fat_g"].value == 2.0
        assert res.nutrient_candidates["sodium_mg"].value == 10.5
