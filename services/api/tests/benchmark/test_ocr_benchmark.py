"""
High-Reliability Food-Label OCR and Deterministic Parsing Benchmark Suite.

Categorizes tests across:
1. Synthetic parser tests.
2. OCR engine adapter tests.
3. Nutrient-to-value association tests.
4. Serving-size and column interpretation tests.
5. End-to-end calculation and plausibility tests.
6. Rejection of unreadable, blurry, or corrupted inputs.
"""

import io

import pytest
from PIL import Image

from app.extraction.adapter import MockOcrAdapter, OcrEngineOutput
from app.extraction.parser import parse_ocr_text
from app.extraction.quality import assess_image_quality
from app.extraction.validator import ImageValidationError, validate_image_payload
from app.nutrition.calculator import analyze_nutrition
from app.nutrition.models import RawNutrientInput, ServingBasis, ServingUnit
from app.nutrition.standards import FoodForm
from tests.fixtures.realistic_fixtures import load_realistic_fixtures


# =========================================================================
# 1. SYNTHETIC PARSER TESTS
# =========================================================================
class TestSyntheticParser:
    """Validates parser performance across synthetic label variations."""

    def test_all_realistic_fixtures_syntax(self) -> None:
        fixtures = load_realistic_fixtures()
        assert len(fixtures) >= 8

        for f in fixtures:
            res = parse_ocr_text(f["raw_text"])
            assert res.verification_required is True
            assert isinstance(res.nutrient_candidates, dict)
            assert res.raw_text == f["raw_text"]

    def test_decimal_comma_normalization(self) -> None:
        raw = "Energy: 120 kcal\nProtein: 3,5 g\nTotal Fat: 4,2 g\nTotal Sugars: 12,8 g"
        res = parse_ocr_text(raw)
        assert res.nutrient_candidates["protein_g"].value == 3.5
        assert res.nutrient_candidates["total_fat_g"].value == 4.2
        assert res.nutrient_candidates["total_sugar_g"].value == 12.8

    def test_ocr_letter_o_substitution_in_numbers(self) -> None:
        raw = "Energy: 1O5 kcal\nProtein: 2.O g\nTotal Fat: 1O.5 g\nSodium: 2O0 mg"
        res = parse_ocr_text(raw)
        assert res.nutrient_candidates["energy_kcal"].value == 105.0
        assert res.nutrient_candidates["protein_g"].value == 2.0
        assert res.nutrient_candidates["total_fat_g"].value == 10.5
        assert res.nutrient_candidates["sodium_mg"].value == 200.0


# =========================================================================
# 2. OCR ENGINE TESTS
# =========================================================================
class TestOcrEngine:
    """Validates OCR engine adapter abstraction, outputs, and discrepancy handling."""

    def test_adapter_output_unpacking(self) -> None:
        adapter = MockOcrAdapter(
            mock_text="Serving Size: 30g\nEnergy: 150 kcal",
            mock_confidence=88.0,
            pass_a_text="Serving Size: 30g\nEnergy: 150 kcal",
            pass_b_text="Serving Size: 30g\nEnergy: 150 kcal",
            pass_discrepancy=False,
        )
        out = adapter.extract_text(b"fake_image_bytes")
        assert isinstance(out, OcrEngineOutput)

        # Backward compatibility 2-tuple unpacking
        text, conf = out
        assert text == "Serving Size: 30g\nEnergy: 150 kcal"
        assert conf == 88.0

    def test_dual_pass_discrepancy_flag(self) -> None:
        adapter = MockOcrAdapter(
            mock_text="Pass A text",
            mock_confidence=75.0,
            pass_a_text="Pass A text with 10g protein",
            pass_b_text="Completely different words in pass B with 20g fat",
            pass_discrepancy=True,
        )
        out = adapter.extract_text(b"fake")
        assert out.pass_discrepancy is True
        assert len(out.discrepancy_details) > 0


# =========================================================================
# 3. NUTRIENT-TO-VALUE ASSOCIATION TESTS
# =========================================================================
class TestNutrientValueAssociation:
    """Verifies column association, sub-nutrient hierarchy, and salt conversion."""

    def test_dual_column_table_association(self) -> None:
        raw = (
            "NUTRITIONAL INFORMATION\n"
            "Per 100g | Per Serve (30g)\n"
            "Energy (kcal) 480 144\n"
            "Protein (g) 7.0 2.1\n"
            "Total Carbohydrates (g) 70.0 21.0\n"
            "Total Sugars (g) 25.0 7.5\n"
            "Added Sugars (g) 20.0 6.0\n"
            "Total Fat (g) 18.0 5.4\n"
            "Sodium (mg) 360 108"
        )
        res = parse_ocr_text(raw)
        assert res.column_basis_detected == "dual_column"
        assert len(res.per_100_candidates) >= 5
        assert len(res.per_serving_candidates) >= 5

        # Check per-100 column
        assert res.per_100_candidates["energy_kcal"].value == 480.0
        assert res.per_100_candidates["protein_g"].value == 7.0
        assert res.per_100_candidates["total_sugar_g"].value == 25.0
        assert res.per_100_candidates["total_fat_g"].value == 18.0

        # Check per-serving column
        assert res.per_serving_candidates["energy_kcal"].value == 144.0
        assert res.per_serving_candidates["protein_g"].value == 2.1
        assert res.per_serving_candidates["total_sugar_g"].value == 7.5
        assert res.per_serving_candidates["total_fat_g"].value == 5.4

    def test_salt_to_sodium_deterministic_conversion(self) -> None:
        raw = "NUTRITION FACTS\nEnergy: 200 kcal\nProtein: 4g\nSalt: 1.0 g\nIngredients: Flour"
        res = parse_ocr_text(raw)
        assert "sodium_mg" in res.nutrient_candidates
        sodium_cand = res.nutrient_candidates["sodium_mg"]
        assert sodium_cand.source == "converted"
        # 1.0g salt = 393.4 mg sodium
        assert sodium_cand.value == pytest.approx(393.4, abs=0.2)
        assert any(w.code == "SALT_CONVERTED_TO_SODIUM" for w in res.warnings)


# =========================================================================
# 4. SERVING-SIZE INTERPRETATION TESTS
# =========================================================================
class TestServingSizeInterpretation:
    """Verifies parsing of various serving size formats."""

    def test_parenthesized_serving_weights(self) -> None:
        res = parse_ocr_text("Serving Size: 2 Biscuits (25g)\nEnergy: 120 kcal")
        assert res.serving_size_candidate == 25.0
        assert res.serving_unit_candidate == "g"

    def test_discrete_portion_serving(self) -> None:
        res = parse_ocr_text("Serving Size: 3 Pieces\nEnergy: 150 kcal")
        assert res.serving_size_candidate == 3.0
        assert res.serving_unit_candidate == "piece"

    def test_missing_serving_size_warning(self) -> None:
        res = parse_ocr_text("NUTRITION FACTS Per 100g\nEnergy: 400 kcal")
        assert res.serving_size_candidate is None
        assert any(w.code == "MISSING_SERVING_SIZE" for w in res.warnings)


# =========================================================================
# 5. END-TO-END CALCULATION & PLAUSIBILITY TESTS
# =========================================================================
class TestEndToEndCalculation:
    """Verifies that parsed candidate values flow into deterministic calculation."""

    def test_confirmed_values_generate_audit_assumptions(self) -> None:
        input_data = RawNutrientInput(
            serving_size=30.0,
            serving_unit=ServingUnit.G,
            basis=ServingBasis.PER_SERVING,
            food_form=FoodForm.SOLID,
            energy_kcal=140.0,
            protein_g=2.5,
            carbohydrates_g=22.0,
            total_sugar_g=8.0,
            added_sugar_g=6.0,
            total_fat_g=5.0,
            saturated_fat_g=2.0,
            trans_fat_g=0.0,
            sodium_mg=150.0,
        )
        result = analyze_nutrition(input_data)
        assert result.status == "complete"
        assert result.is_complete is True
        assert len(result.calculation_assumptions) >= 4
        assert "serving_scaling_formula" in result.calculation_assumptions
        assert "rounding_precision" in result.calculation_assumptions

    def test_contradictory_plausibility_flagging(self) -> None:
        # Added sugar (15g) exceeds total sugar (10g)
        raw = "NUTRITION FACTS\nEnergy: 150 kcal\nTotal Sugars: 10.0g\nAdded Sugars: 15.0g"
        res = parse_ocr_text(raw)
        assert any(w.code == "PLAUSIBILITY_ADDED_SUGAR_EXCEEDS_TOTAL" for w in res.warnings)
        assert res.nutrient_candidates["added_sugar_g"].plausibility == "contradictory"
        assert res.nutrient_candidates["total_sugar_g"].plausibility == "contradictory"


# =========================================================================
# 6. REJECTION OF UNREADABLE OR AMBIGUOUS INPUTS
# =========================================================================
class TestInputRejection:
    """Verifies computer vision quality gates and defensive image validation."""

    def test_rejects_corrupted_payload(self) -> None:
        with pytest.raises(ImageValidationError):
            validate_image_payload(b"corrupted bytes that are not an image" * 4)

    def test_cv_quality_detects_severe_blur(self) -> None:
        # Create an artificial flat uniform image with 0 Laplacian variance
        stream = io.BytesIO()
        img = Image.new("RGB", (700, 500), color=(128, 128, 128))
        img.save(stream, format="PNG")
        assessment = assess_image_quality(stream.getvalue())

        assert assessment.metrics.sharpness_score < 10.0
        assert any("BLUR" in w.code for w in assessment.warnings)

    def test_cv_quality_detects_glare(self) -> None:
        # Create image that is 40% saturated pure white (255, 255, 255)
        stream = io.BytesIO()
        img = Image.new("RGB", (800, 600), color=(50, 50, 50))
        # Draw large white rectangle
        for x in range(200, 600):
            for y in range(150, 450):
                img.putpixel((x, y), (255, 255, 255))
        img.save(stream, format="PNG")
        assessment = assess_image_quality(stream.getvalue())

        assert assessment.metrics.glare_ratio > 0.15
        assert any(w.code == "IMAGE_GLARE_SEVERE" for w in assessment.warnings)
