"""
API endpoints for local food label OCR and text extraction.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings
from app.extraction.adapter import (
    OcrEngineError,
    OcrEngineUnavailableError,
    OcrTimeoutError,
)
from app.extraction.validator import ImageValidationError
from app.schemas.extraction import OcrExtractionResponse
from app.services.extraction_service import ExtractionService

router = APIRouter()


def get_extraction_service(
    settings: Settings = Depends(lambda: Settings()),  # noqa: B008
) -> ExtractionService:
    return ExtractionService(settings=settings)


@router.post(
    "/ocr",
    response_model=OcrExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text and candidate nutrition/ingredients from a food label image",
    description=(
        "Processes an uploaded food label image locally using Tesseract OCR. "
        "Extracts raw text, identifies candidate nutrient lines, and extracts candidate "
        "ingredient text. Returns candidate values requiring explicit user confirmation."
    ),
)
async def extract_label_ocr(
    file: UploadFile = File(..., description="Food label image (JPEG, PNG, or WEBP)"),
    service: ExtractionService = Depends(get_extraction_service),
) -> OcrExtractionResponse:
    """
    Accepts an uploaded image, runs offline OCR, and returns reviewable candidate extraction.
    """
    try:
        image_bytes = await file.read()
        return service.process_image(image_bytes)
    except ImageValidationError as err:
        status_code = 413 if err.code == "IMAGE_TOO_LARGE" else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": err.code, "message": err.message},
        ) from None
    except OcrTimeoutError as err:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": err.code, "message": err.message},
        ) from None
    except OcrEngineUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": err.code, "message": err.message},
        ) from None
    except OcrEngineError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": err.code, "message": err.message},
        ) from None
    finally:
        await file.close()
