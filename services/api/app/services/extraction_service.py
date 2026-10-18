"""
Orchestration service for food label image extraction and OCR.
Integrates image validation, quality gates, dual-pass OCR, and deterministic parsing.
"""

from app.core.config import Settings
from app.extraction.adapter import (
    BaseOcrAdapter,
    OcrEngineOutput,
    TesseractOcrAdapter,
)
from app.extraction.parser import parse_ocr_text
from app.extraction.quality import assess_image_quality
from app.extraction.validator import validate_image_payload
from app.schemas.extraction import (
    ExtractedNutrientCandidateSchema,
    ExtractionWarningSchema,
    ImageQualityAssessmentSchema,
    ImageQualityMetricsSchema,
    OcrExtractionResponse,
)


class ExtractionService:
    """
    Coordinates image validation, computer vision quality gates,
    pluggable multi-pass OCR extraction, and deterministic parsing.
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
        Validates image payload, evaluates image quality gates, runs local OCR,
        and returns unverified draft candidate structured results.
        """
        # 1. Defensive validation (format, dimensions, pixel density, decompression bomb protection)
        validate_image_payload(
            image_bytes=image_bytes,
            max_bytes=self.settings.MAX_IMAGE_UPLOAD_BYTES,
            max_dimension=self.settings.MAX_IMAGE_DIMENSION,
            max_pixels=self.settings.MAX_IMAGE_PIXELS,
        )

        # 2. Computer vision image quality gates
        # (blur, glare, resolution, contrast, skew, table cropping)
        quality_assessment = assess_image_quality(image_bytes)

        # 3. Local OCR execution via pluggable adapter
        ocr_result_raw = self.ocr_adapter.extract_text(image_bytes)
        if isinstance(ocr_result_raw, OcrEngineOutput):
            ocr_output = ocr_result_raw
        else:
            # Fallback if custom adapter returned a 2-tuple
            raw_t, conf_v = ocr_result_raw
            ocr_output = OcrEngineOutput(raw_text=raw_t, confidence=conf_v)

        # 4. Pure deterministic parsing, column separation, and plausibility auditing
        result = parse_ocr_text(raw_text=ocr_output.raw_text, confidence=ocr_output.confidence)

        # Combine warnings from image quality gates, OCR discrepancy, and table parsing
        all_warnings: list[ExtractionWarningSchema] = []

        # Add image quality warnings
        for w in quality_assessment.warnings:
            all_warnings.append(ExtractionWarningSchema(code=w.code, message=w.message))

        # Add dual-pass OCR discrepancy warning if detected
        if ocr_output.pass_discrepancy:
            all_warnings.append(
                ExtractionWarningSchema(
                    code="OCR_PASS_DISCREPANCY",
                    message=(
                        "Multiple OCR preprocessing passes generated conflicting interpretations. "
                        "Please verify all highlighted fields against the packaging photograph."
                    ),
                )
            )

        # Add parser and plausibility warnings
        for w in result.warnings:
            # Prevent duplicate codes
            if not any(existing.code == w.code for existing in all_warnings):
                all_warnings.append(ExtractionWarningSchema(code=w.code, message=w.message))

        # Build quality schema
        quality_schema = ImageQualityAssessmentSchema(
            is_acceptable=quality_assessment.is_acceptable,
            grade=quality_assessment.grade,
            metrics=ImageQualityMetricsSchema(
                width=quality_assessment.metrics.width,
                height=quality_assessment.metrics.height,
                total_pixels=quality_assessment.metrics.total_pixels,
                sharpness_score=round(quality_assessment.metrics.sharpness_score, 1),
                glare_ratio=round(quality_assessment.metrics.glare_ratio, 3),
                mean_luminance=round(quality_assessment.metrics.mean_luminance, 1),
                contrast_std=round(quality_assessment.metrics.contrast_std, 1),
                estimated_skew_degrees=round(quality_assessment.metrics.estimated_skew_degrees, 1),
                min_content_margin_px=quality_assessment.metrics.min_content_margin_px,
            ),
            warnings=[
                ExtractionWarningSchema(code=w.code, message=w.message)
                for w in quality_assessment.warnings
            ],
            disclaimer=quality_assessment.disclaimer,
        )

        def map_candidate(cand) -> ExtractedNutrientCandidateSchema:
            return ExtractedNutrientCandidateSchema(
                field_name=cand.field_name,
                raw_text=cand.raw_text,
                value=cand.value,
                unit=cand.unit,
                confidence=cand.confidence,
                source=cand.source,
                status=cand.status,
                plausibility=cand.plausibility,
                plausibility_warning=cand.plausibility_warning,
                column=cand.column,
            )

        # 5. Serialize to response schema
        return OcrExtractionResponse(
            raw_text=result.raw_text,
            pass_a_text=ocr_output.pass_a_text,
            pass_b_text=ocr_output.pass_b_text,
            pass_discrepancy=ocr_output.pass_discrepancy,
            image_quality=quality_schema,
            column_basis_detected=result.column_basis_detected,
            nutrition_lines=result.nutrition_lines,
            ingredients_text=result.ingredients_text,
            nutrient_candidates={
                k: map_candidate(v) for k, v in result.nutrient_candidates.items()
            },
            per_100_candidates={k: map_candidate(v) for k, v in result.per_100_candidates.items()},
            per_serving_candidates={
                k: map_candidate(v) for k, v in result.per_serving_candidates.items()
            },
            serving_size_candidate=result.serving_size_candidate,
            serving_unit_candidate=result.serving_unit_candidate,
            overall_confidence=result.overall_confidence,
            warnings=all_warnings,
            verification_required=result.verification_required,
            disclaimer=result.disclaimer,
        )
