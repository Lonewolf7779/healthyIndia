"""
Orchestration service for food label image extraction and OCR.
"""

from app.core.config import Settings
from app.extraction.adapter import (
    BaseOcrAdapter,
    TesseractOcrAdapter,
)
from app.extraction.parser import parse_ocr_text
from app.extraction.validator import validate_image_payload
from app.schemas.extraction import (
    ExtractedNutrientCandidateSchema,
    ExtractionWarningSchema,
    OcrExtractionResponse,
)


class ExtractionService:
    """
    Coordinates image validation, pluggable OCR extraction, and heuristic parsing.
    """

    def __init__(
        self,
        settings: Settings,
        ocr_adapter: BaseOcrAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.ocr_adapter = ocr_adapter or TesseractOcrAdapter(
            tesseract_cmd=settings.TESSERACT_CMD,
            timeout_seconds=settings.OCR_TIMEOUT_SECONDS,
        )

    def process_image(self, image_bytes: bytes) -> OcrExtractionResponse:
        """
        Validates the image payload, runs local OCR, and returns candidate structured results.
        """
        # 1. Defensive validation (format, dimensions, pixel density)
        validate_image_payload(
            image_bytes=image_bytes,
            max_bytes=self.settings.MAX_IMAGE_UPLOAD_BYTES,
            max_dimension=self.settings.MAX_IMAGE_DIMENSION,
            max_pixels=self.settings.MAX_IMAGE_PIXELS,
        )

        # 2. Local OCR execution via pluggable adapter
        raw_text, confidence = self.ocr_adapter.extract_text(image_bytes)

        # 3. Pure parsing and warning heuristics
        result = parse_ocr_text(raw_text=raw_text, confidence=confidence)

        # 4. Serialize to response schema
        return OcrExtractionResponse(
            raw_text=result.raw_text,
            nutrition_lines=result.nutrition_lines,
            ingredients_text=result.ingredients_text,
            nutrient_candidates={
                k: ExtractedNutrientCandidateSchema(
                    field_name=v.field_name,
                    raw_text=v.raw_text,
                    value=v.value,
                    unit=v.unit,
                    confidence=v.confidence,
                )
                for k, v in result.nutrient_candidates.items()
            },
            serving_size_candidate=result.serving_size_candidate,
            serving_unit_candidate=result.serving_unit_candidate,
            overall_confidence=result.overall_confidence,
            warnings=[
                ExtractionWarningSchema(code=w.code, message=w.message) for w in result.warnings
            ],
            verification_required=result.verification_required,
            disclaimer=result.disclaimer,
        )
