"""
API endpoints for local food label OCR and text extraction.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings
from app.core.security import generate_confirmation_token, verify_extraction_token
from app.extraction.adapter import (
    OcrEngineError,
    OcrEngineUnavailableError,
    OcrTimeoutError,
)
from app.extraction.validator import ImageValidationError
from app.schemas.extraction import (
    OcrConfirmationRequest,
    OcrConfirmationResponse,
    OcrExtractionResponse,
)
from app.schemas.nutrition import compute_nutrition_values_hash
from app.services.extraction_service import ExtractionService
from app.services.session_store import session_store

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


@router.post(
    "/confirm",
    response_model=OcrConfirmationResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm and authenticate reviewed OCR nutrient values",
    description=(
        "Authenticates the extraction session token, records user review and corrections "
        "in the server extraction state, and issues a cryptographically signed server-keyed "
        "confirmation token binding the reviewed values to the extraction session."
    ),
)
async def confirm_ocr_values(
    request: OcrConfirmationRequest,
    settings: Settings = Depends(lambda: Settings()),  # noqa: B008
) -> OcrConfirmationResponse:
    """
    Validates the session token, binds reviewed values, and issues a server confirmation token.
    """
    # 1. Verify extraction session token
    is_valid, err_msg = verify_extraction_token(
        token=request.extraction_token,
        extraction_id=request.extraction_id,
        secret_key=settings.SECRET_KEY,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extraction session authentication failed: {err_msg}",
        )

    # 2. Build canonical nutrients map and calculate canonical SHA-256 digest
    nutrients_map: dict[str, float | None] = {
        "added_sugar_g": request.added_sugar_g,
        "carbohydrates_g": request.carbohydrates_g,
        "cholesterol_mg": request.cholesterol_mg,
        "dietary_fiber_g": request.dietary_fiber_g,
        "energy_kcal": request.energy_kcal,
        "protein_g": request.protein_g,
        "saturated_fat_g": request.saturated_fat_g,
        "sodium_mg": request.sodium_mg,
        "total_fat_g": request.total_fat_g,
        "total_sugar_g": request.total_sugar_g,
        "trans_fat_g": request.trans_fat_g,
    }

    canonical_digest = compute_nutrition_values_hash(
        serving_size=request.serving_size,
        serving_unit=request.serving_unit.value,
        basis=request.basis.value,
        food_form=request.food_form.value,
        nutrients=nutrients_map,
    )

    # 3. Check and update server-side session state (if session exists)
    _, _, session = session_store.confirm_session(
        extraction_id=request.extraction_id,
        confirmed_digest=canonical_digest,
        confirmed_values=nutrients_map,
    )

    user_modified = session.user_modified if session else False
    modified_fields = session.modified_fields if session else []

    # 4. Generate server-keyed confirmation token
    confirmation_token = generate_confirmation_token(
        extraction_id=request.extraction_id,
        values_digest=canonical_digest,
        secret_key=settings.SECRET_KEY,
    )

    return OcrConfirmationResponse(
        status="confirmed",
        extraction_id=request.extraction_id,
        confirmed_values_hash=confirmation_token,
        canonical_digest=canonical_digest,
        user_modified=user_modified,
        modified_fields=modified_fields,
    )
