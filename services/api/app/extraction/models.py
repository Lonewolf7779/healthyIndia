"""
Domain models for OCR extraction, quality gates, and review workflow.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.extraction.quality import ImageQualityAssessment


@dataclass(frozen=True)
class ExtractionWarning:
    """
    Advisory or uncertainty warning produced during image inspection, OCR, or parsing.
    """

    code: str
    message: str


@dataclass(frozen=True)
class ExtractedNutrientCandidate:
    """
    Candidate nutrient value extracted from food label text.
    Marked as unverified draft suggestion requiring user confirmation.
    """

    field_name: str
    raw_text: str
    value: float | None
    unit: str | None
    confidence: float | None = None
    source: str = "ocr"  # "ocr", "manual", "converted"
    status: str = "unconfirmed"  # "unconfirmed", "confirmed", "edited"
    plausibility: str = "plausible"  # "plausible", "suspicious", "contradictory"
    plausibility_warning: str | None = None
    column: str | None = None  # "per_100g", "per_serving", "single_column", None


@dataclass
class OcrExtractionResult:
    """
    Structured outcome of local image quality gates, OCR processing, and parsing.
    All data is considered unverified draft input until explicitly confirmed by the user.
    """

    raw_text: str
    pass_a_text: str | None = None
    pass_b_text: str | None = None
    pass_discrepancy: bool = False
    image_quality: "ImageQualityAssessment | None" = None
    column_basis_detected: str = "unknown"  # "per_serving", "per_100g", "dual_column", "unknown"
    nutrition_lines: list[str] = field(default_factory=list)
    ingredients_text: str | None = None
    nutrient_candidates: dict[str, ExtractedNutrientCandidate] = field(default_factory=dict)
    per_100_candidates: dict[str, ExtractedNutrientCandidate] = field(default_factory=dict)
    per_serving_candidates: dict[str, ExtractedNutrientCandidate] = field(default_factory=dict)
    serving_size_candidate: float | None = None
    serving_unit_candidate: str | None = None
    overall_confidence: float | None = None
    warnings: list[ExtractionWarning] = field(default_factory=list)
    verification_required: bool = True
    disclaimer: str = (
        "OCR extraction is preliminary and machine-generated. Physical print quality, "
        "lighting, reflections, or packaging folds may cause errors. The user must review, "
        "verify, and confirm all values before calculation."
    )
