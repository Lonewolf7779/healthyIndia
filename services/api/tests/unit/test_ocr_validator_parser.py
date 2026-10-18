"""
Unit tests for defensive image validation, OCR text parsing, and adapter behavior.
"""

import io

import pytest
from PIL import Image

from app.extraction.adapter import (
    MockOcrAdapter,
    OcrEngineError,
    OcrTimeoutError,
    TesseractOcrAdapter,
)
from app.extraction.parser import parse_ocr_text
from app.extraction.validator import ImageValidationError, validate_image_payload


def _create_test_image_bytes(
    format_name: str = "PNG",
    size: tuple[int, int] = (200, 100),
    color: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    stream = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(stream, format=format_name)
    return stream.getvalue()


def test_validate_valid_image_formats() -> None:
    for fmt in ["PNG", "JPEG", "WEBP"]:
        img_bytes = _create_test_image_bytes(format_name=fmt)
        width, height, detected_fmt = validate_image_payload(img_bytes)
        assert width == 200
        assert height == 100
        assert detected_fmt == fmt


def test_validate_rejects_empty_or_tiny_payload() -> None:
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(b"short")
    assert exc.value.code == "EMPTY_OR_TRUNCATED_IMAGE"


def test_validate_rejects_spoofed_text_extension() -> None:
    fake_png = b"This is a text file claiming to be a PNG image." * 5
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(fake_png)
    assert exc.value.code == "INVALID_IMAGE_FORMAT"


def test_validate_rejects_unsupported_format_gif() -> None:
    gif_bytes = _create_test_image_bytes(format_name="GIF")
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(gif_bytes)
    assert exc.value.code == "UNSUPPORTED_IMAGE_FORMAT"
    assert "GIF" in exc.value.message


def test_validate_rejects_oversized_payload() -> None:
    img_bytes = _create_test_image_bytes(format_name="PNG")
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(img_bytes, max_bytes=50)
    assert exc.value.code == "IMAGE_TOO_LARGE"


def test_validate_rejects_excessive_dimensions() -> None:
    # 5000px exceeds max_dimension 4096
    large_stream = io.BytesIO()
    img = Image.new("RGB", (5000, 10), color=(255, 255, 255))
    img.save(large_stream, format="PNG")
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(large_stream.getvalue(), max_dimension=4096)
    assert exc.value.code == "IMAGE_DIMENSION_EXCEEDED"


def test_validate_rejects_excessive_pixel_count() -> None:
    # 2000x2000 = 4,000,000 pixels exceeds max_pixels 1,000,000
    pixel_stream = io.BytesIO()
    img = Image.new("RGB", (2000, 2000), color=(255, 255, 255))
    img.save(pixel_stream, format="JPEG")
    with pytest.raises(ImageValidationError) as exc:
        validate_image_payload(pixel_stream.getvalue(), max_pixels=1_000_000)
    assert exc.value.code in {"DECOMPRESSION_BOMB_DETECTED", "IMAGE_PIXEL_LIMIT_EXCEEDED"}


def test_parse_ocr_text_extracts_candidates_and_ingredients() -> None:
    raw_ocr = (
        "NUTRITION INFORMATION\n"
        "Serving Size: 30g\n"
        "Energy: 145 kcal\n"
        "Protein: 2.5g\n"
        "Total Carbohydrate: 22g\n"
        "Total Sugars: 9g\n"
        "Added Sugars: 7.5g\n"
        "Total Fat: 6.0g\n"
        "Saturated Fat: 2.8g\n"
        "Trans Fat: 0.0g\n"
        "Sodium: 210mg\n"
        "\n"
        "INGREDIENTS: Refined Wheat Flour, Palm Oil, Sugar, Salt, "
        "Emulsifier (INS 322(i)), Flavour Enhancer (INS 621)\n"
    )

    result = parse_ocr_text(raw_text=raw_ocr, confidence=88.5)

    assert result.serving_size_candidate == 30.0
    assert result.serving_unit_candidate == "g"
    assert result.overall_confidence == 88.5
    assert result.verification_required is True

    candidates = result.nutrient_candidates
    assert candidates["energy_kcal"].value == 145.0
    assert candidates["protein_g"].value == 2.5
    assert candidates["carbohydrates_g"].value == 22.0
    assert candidates["added_sugar_g"].value == 7.5
    assert candidates["total_fat_g"].value == 6.0
    assert candidates["sodium_mg"].value == 210.0

    assert result.ingredients_text is not None
    assert "Refined Wheat Flour" in result.ingredients_text
    assert "Emulsifier (INS 322(i))" in result.ingredients_text


def test_parse_ocr_text_emits_warnings_for_sparse_text() -> None:
    result = parse_ocr_text("Short blurry text", confidence=45.0)
    warning_codes = [w.code for w in result.warnings]

    assert "SPARSE_TEXT" in warning_codes
    assert "LOW_CONFIDENCE" in warning_codes
    assert "MISSING_SERVING_SIZE" in warning_codes
    assert "MISSING_INGREDIENTS" in warning_codes


def test_mock_ocr_adapter_handles_timeouts_and_errors() -> None:
    timeout_adapter = MockOcrAdapter(should_timeout=True)
    with pytest.raises(OcrTimeoutError):
        timeout_adapter.extract_text(b"dummy")

    failing_adapter = MockOcrAdapter(should_fail=True)
    with pytest.raises(OcrEngineError):
        failing_adapter.extract_text(b"dummy")


def test_tesseract_adapter_resolution() -> None:
    adapter = TesseractOcrAdapter()
    # On this Windows machine, Tesseract is installed and should be resolved
    assert adapter.resolved_cmd is not None
    assert adapter.is_available() is True
