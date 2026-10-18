"""
Category B: Image/OCR Integration Tests.

Validates end-to-end image processing, OCR extraction, and API endpoints
using dynamically synthesized label images (no copyrighted or personal photos).
"""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.v1.endpoints.extraction import get_extraction_service
from app.core.config import Settings
from app.extraction.adapter import MockOcrAdapter, TesseractOcrAdapter
from app.services.extraction_service import ExtractionService


def _synthesize_food_label_image(text_lines: list[str], scale: int = 2) -> bytes:
    """
    Renders synthetic label text onto a white image buffer and returns PNG bytes.
    Uses Pillow exclusively; no external network or file dependencies.
    """
    max_len = max(len(line) for line in text_lines) if text_lines else 20
    base_width = max(300, max_len * 10 + 40)
    base_height = max(200, len(text_lines) * 22 + 40)

    img = Image.new("RGB", (base_width, base_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    y = 20
    for line in text_lines:
        draw.text((20, y), line, fill=(0, 0, 0))
        y += 22

    if scale > 1:
        img = img.resize((base_width * scale, base_height * scale), Image.Resampling.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extraction_service_with_synthesized_image() -> None:
    """
    Tests ExtractionService end-to-end with an in-memory rendered PNG image.
    """
    sample_lines = [
        "NUTRITION FACTS",
        "Serving Size: 30g",
        "Energy: 150 kcal",
        "Protein: 3.5 g",
        "Total Fat: 6.0 g",
        "Sodium: 180 mg",
        "",
        "INGREDIENTS: Wheat Flour, Palm Oil, Salt, Emulsifier (INS 322(i)).",
    ]
    img_bytes = _synthesize_food_label_image(sample_lines)

    settings = Settings()
    real_adapter = TesseractOcrAdapter(tesseract_cmd=settings.TESSERACT_CMD)
    if real_adapter.is_available():
        service = ExtractionService(settings=settings, ocr_adapter=real_adapter)
    else:
        mock_raw = "\n".join(sample_lines)
        service = ExtractionService(
            settings=settings,
            ocr_adapter=MockOcrAdapter(mock_text=mock_raw, mock_confidence=90.0),
        )

    response = service.process_image(img_bytes)

    assert response.verification_required is True
    assert response.disclaimer is not None
    assert len(response.raw_text) > 0


def test_ocr_api_endpoint_multipart_upload(client: TestClient) -> None:
    """
    Tests POST /api/v1/extraction/ocr endpoint with a synthetic multipart image upload.
    """
    sample_lines = [
        "NUTRITIONAL INFORMATION",
        "Serving Size: 25g",
        "Energy: 110 kcal",
        "Carbohydrates: 18g",
        "Total Sugars: 6g",
        "Sodium: 95mg",
        "",
        "INGREDIENTS: Whole Wheat, Sugar, Acidity Regulator (INS 330).",
    ]
    img_bytes = _synthesize_food_label_image(sample_lines)

    files = {"file": ("test_label.png", img_bytes, "image/png")}
    response = client.post("/api/v1/extraction/ocr", files=files)

    if response.status_code == 503:
        assert response.json()["error"]["code"] == "OCR_ENGINE_UNAVAILABLE"
    else:
        assert response.status_code == 200
        data = response.json()
        assert data["verification_required"] is True
        assert "raw_text" in data
        assert "nutrient_candidates" in data


def test_ocr_api_endpoint_rejects_non_image_payload(client: TestClient) -> None:
    """
    Verifies that the OCR endpoint defensively rejects text files claiming to be images.
    """
    fake_payload = b"not an image file at all" * 10
    files = {"file": ("malicious.png", fake_payload, "image/png")}
    response = client.post("/api/v1/extraction/ocr", files=files)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE_FORMAT"


def test_mock_adapter_handles_unreadable_or_corrupt_stream(client: TestClient) -> None:
    """
    Verifies that when OCR extraction returns sparse text, uncertainty warnings are generated.
    """
    sparse_adapter = MockOcrAdapter(mock_text="blur", mock_confidence=25.0)
    service = ExtractionService(settings=Settings(), ocr_adapter=sparse_adapter)

    app = client.app
    app.dependency_overrides[get_extraction_service] = lambda: service

    try:
        valid_img = _synthesize_food_label_image(["Dummy Text"])
        response = client.post(
            "/api/v1/extraction/ocr",
            files={"file": ("dummy.png", valid_img, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        warning_codes = [w["code"] for w in data["warnings"]]
        assert "SPARSE_TEXT" in warning_codes
        assert "LOW_CONFIDENCE" in warning_codes
        assert data["verification_required"] is True
    finally:
        app.dependency_overrides.clear()
