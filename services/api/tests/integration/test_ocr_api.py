"""
Integration tests for the local OCR extraction API endpoint.
"""

import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.v1.endpoints.extraction import get_extraction_service
from app.core.config import Settings
from app.extraction.adapter import MockOcrAdapter
from app.services.extraction_service import ExtractionService


def _create_image_file(
    format_name: str = "PNG", text: str = "Test Label"
) -> tuple[str, bytes, str]:
    stream = io.BytesIO()
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill=(0, 0, 0))
    img.save(stream, format=format_name)
    content_type = f"image/{format_name.lower()}"
    return f"label.{format_name.lower()}", stream.getvalue(), content_type


def test_extract_ocr_success_with_mock(client: TestClient) -> None:
    mock_text = (
        "NUTRITION FACTS\n"
        "Serving Size: 30g\n"
        "Energy: 140 kcal\n"
        "Protein: 2g\n"
        "Total Carbohydrate: 20g\n"
        "Added Sugars: 6g\n"
        "Total Fat: 5g\n"
        "Sodium: 150mg\n"
        "INGREDIENTS: Wheat Flour, Palm Oil, Sugar, Salt, Emulsifier (INS 322(i))\n"
    )
    mock_service = ExtractionService(
        settings=Settings(),
        ocr_adapter=MockOcrAdapter(mock_text=mock_text, mock_confidence=92.0),
    )

    app = client.app
    app.dependency_overrides[get_extraction_service] = lambda: mock_service

    try:
        filename, payload, mime = _create_image_file()
        response = client.post(
            "/api/v1/extraction/ocr",
            files={"file": (filename, payload, mime)},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["verification_required"] is True
        assert data["overall_confidence"] == 92.0
        assert data["serving_size_candidate"] == 30.0
        assert data["serving_unit_candidate"] == "g"

        candidates = data["nutrient_candidates"]
        assert candidates["energy_kcal"]["value"] == 140.0
        assert candidates["protein_g"]["value"] == 2.0
        assert candidates["added_sugar_g"]["value"] == 6.0
        assert candidates["sodium_mg"]["value"] == 150.0

        assert "Wheat Flour" in data["ingredients_text"]
        assert "Emulsifier (INS 322(i))" in data["ingredients_text"]

    finally:
        app.dependency_overrides.clear()


def test_extract_ocr_rejects_corrupted_image(client: TestClient) -> None:
    fake_payload = b"NOT_A_REAL_IMAGE_DATA_1234567890" * 10
    response = client.post(
        "/api/v1/extraction/ocr",
        files={"file": ("fake.png", fake_payload, "image/png")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "INVALID_IMAGE_FORMAT"


def test_extract_ocr_rejects_unsupported_gif_format(client: TestClient) -> None:
    filename, payload, mime = _create_image_file(format_name="GIF")
    response = client.post(
        "/api/v1/extraction/ocr",
        files={"file": (filename, payload, mime)},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_IMAGE_FORMAT"


def test_extract_ocr_handles_timeout(client: TestClient) -> None:
    timeout_service = ExtractionService(
        settings=Settings(),
        ocr_adapter=MockOcrAdapter(should_timeout=True),
    )

    app = client.app
    app.dependency_overrides[get_extraction_service] = lambda: timeout_service

    try:
        filename, payload, mime = _create_image_file()
        response = client.post(
            "/api/v1/extraction/ocr",
            files={"file": (filename, payload, mime)},
        )
        assert response.status_code == 504
        data = response.json()
        assert data["error"]["code"] == "OCR_TIMEOUT_ERROR"
    finally:
        app.dependency_overrides.clear()


def test_extract_ocr_live_tesseract_end_to_end(client: TestClient) -> None:
    """
    Tests live Tesseract execution on synthesized label image.
    """
    label_text = "Serving Size: 25g\nEnergy: 120 kcal\nIngredients: Wheat, Salt"
    filename, payload, mime = _create_image_file(format_name="PNG", text=label_text)

    # Use default real ExtractionService (Tesseract)
    response = client.post(
        "/api/v1/extraction/ocr",
        files={"file": (filename, payload, mime)},
    )

    # If Tesseract is installed, expect 200 OK; if not installed on an arbitrary runner, 503
    if response.status_code == 503:
        assert response.json()["error"]["code"] == "OCR_ENGINE_UNAVAILABLE"
    else:
        assert response.status_code == 200
        data = response.json()
        assert data["verification_required"] is True
        assert len(data["raw_text"]) > 0
