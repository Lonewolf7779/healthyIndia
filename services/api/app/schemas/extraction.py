"""
Pydantic schemas for OCR extraction requests and responses.
Includes quality gates, confirmation metadata, dual-column separation, and plausibility.
"""

from pydantic import BaseModel, Field


class ImageQualityMetricsSchema(BaseModel):
    width: int
    height: int
    total_pixels: int
    sharpness_score: float
    glare_ratio: float
    mean_luminance: float
    contrast_std: float
    estimated_skew_degrees: float
    min_content_margin_px: int


class ExtractionWarningSchema(BaseModel):
    code: str
    message: str


class ImageQualityAssessmentSchema(BaseModel):
    is_acceptable: bool
    grade: str = Field(..., description="Overall image quality grade: 'good', 'fair', or 'poor'")
    metrics: ImageQualityMetricsSchema
    warnings: list[ExtractionWarningSchema] = Field(default_factory=list)
    disclaimer: str


class ExtractedNutrientCandidateSchema(BaseModel):
    field_name: str
    raw_text: str
    value: float | None = None
    unit: str | None = None
    confidence: float | None = None
    source: str = "ocr"  # "ocr", "manual", "converted"
    status: str = "unconfirmed"  # "unconfirmed", "confirmed", "edited"
    plausibility: str = "plausible"  # "plausible", "suspicious", "contradictory"
    plausibility_warning: str | None = None
    column: str | None = None  # "per_100g", "per_serving", "single_column", None


class OcrExtractionResponse(BaseModel):
    raw_text: str = Field(..., description="Complete raw text extracted by the local OCR engine.")
    pass_a_text: str | None = Field(
        None, description="Raw text from Pass A (normalized grayscale + CLAHE)."
    )
    pass_b_text: str | None = Field(
        None, description="Raw text from Pass B (deskewed adaptive binary)."
    )
    pass_discrepancy: bool = Field(
        False, description="True if independent OCR passes produced conflicting extractions."
    )
    image_quality: ImageQualityAssessmentSchema | None = Field(
        None,
        description="Pre-OCR computer vision quality assessment (blur, glare, resolution, skew).",
    )
    column_basis_detected: str = Field(
        "unknown",
        description=(
            "Detected table layout: 'dual_column', 'per_100g', 'per_serving', or 'unknown'."
        ),
    )
    nutrition_lines: list[str] = Field(
        default_factory=list,
        description="Identified candidate text lines relating to nutritional panel facts.",
    )
    ingredients_text: str | None = Field(
        None, description="Identified candidate ingredients statement text."
    )
    nutrient_candidates: dict[str, ExtractedNutrientCandidateSchema] = Field(
        default_factory=dict,
        description="Unverified draft nutrient values extracted from label text.",
    )
    per_100_candidates: dict[str, ExtractedNutrientCandidateSchema] = Field(
        default_factory=dict,
        description="Candidate values associated specifically with the Per 100g/ml column.",
    )
    per_serving_candidates: dict[str, ExtractedNutrientCandidateSchema] = Field(
        default_factory=dict,
        description="Candidate values associated specifically with the Per Serving column.",
    )
    serving_size_candidate: float | None = Field(
        None, description="Candidate serving size number, if identified."
    )
    serving_unit_candidate: str | None = Field(
        None, description="Candidate serving unit (g, ml, piece), if identified."
    )
    overall_confidence: float | None = Field(
        None, description="Average OCR engine word confidence score (0 to 100), if available."
    )
    warnings: list[ExtractionWarningSchema] = Field(
        default_factory=list,
        description="Quality, clarity, physical plausibility, or missing section warnings.",
    )
    verification_required: bool = Field(
        True, description="Always true. All OCR extraction requires manual user review."
    )
    disclaimer: str = Field(
        ...,
        description=(
            "Notice that extracted data is machine-generated and must be verified by the user."
        ),
    )
