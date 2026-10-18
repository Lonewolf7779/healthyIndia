"""
Pydantic schemas for OCR extraction requests and responses.
Includes quality gates, confirmation metadata, dual-column separation, and plausibility.
"""

from pydantic import BaseModel, Field

from app.nutrition.models import ServingBasis, ServingUnit
from app.nutrition.standards import FoodForm


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
    gate_outcome: str = Field(
        "ACCEPT",
        description="Quality gate disposition: 'ACCEPT', 'WARN', or 'REJECT'",
    )
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
    extraction_id: str = Field(
        default="",
        description="Unique identifier for this OCR extraction session.",
    )
    extraction_token: str = Field(
        default="",
        description="Cryptographic token certifying provenance of this OCR extraction.",
    )
    disclaimer: str = Field(
        ...,
        description=(
            "Notice that extracted data is machine-generated and must be verified by the user."
        ),
    )


class OcrConfirmationRequest(BaseModel):
    """
    Schema for confirming and optionally correcting reviewed OCR nutrient values.
    """

    extraction_id: str = Field(
        ...,
        description="Mandatory UUID matching the original OCR extraction session.",
    )
    extraction_token: str = Field(
        ...,
        description="Signed extraction session token certifying session authenticity.",
    )
    serving_size: float = Field(
        ...,
        gt=0.0,
        le=5000.0,
        description="Declared serving size (must be strictly positive).",
    )
    serving_unit: ServingUnit = Field(
        default=ServingUnit.G,
        description="Unit of serving size.",
    )
    basis: ServingBasis = Field(
        default=ServingBasis.PER_SERVING,
        description="Basis on which the package values are reported.",
    )
    food_form: FoodForm = Field(
        default=FoodForm.SOLID,
        description="Physical state of the food (solid food or liquid beverage).",
    )

    energy_kcal: float | None = Field(default=None, ge=0.0, le=5000.0)
    protein_g: float | None = Field(default=None, ge=0.0, le=500.0)
    carbohydrates_g: float | None = Field(default=None, ge=0.0, le=500.0)
    total_sugar_g: float | None = Field(default=None, ge=0.0, le=500.0)
    added_sugar_g: float | None = Field(default=None, ge=0.0, le=500.0)
    dietary_fiber_g: float | None = Field(default=None, ge=0.0, le=500.0)
    total_fat_g: float | None = Field(default=None, ge=0.0, le=500.0)
    saturated_fat_g: float | None = Field(default=None, ge=0.0, le=500.0)
    trans_fat_g: float | None = Field(default=None, ge=0.0, le=500.0)
    cholesterol_mg: float | None = Field(default=None, ge=0.0, le=5000.0)
    sodium_mg: float | None = Field(default=None, ge=0.0, le=50000.0)


class OcrConfirmationResponse(BaseModel):
    """
    Schema returning the server-authenticated confirmation token binding reviewed values.
    """

    status: str = Field("confirmed", description="Confirmation state.")
    extraction_id: str = Field(..., description="Extraction session UUID.")
    confirmed_values_hash: str = Field(
        ...,
        description="Server-keyed HMAC confirmation token 'c1.<id>.<digest>.<timestamp>.<sig>'.",
    )
    canonical_digest: str = Field(
        ...,
        description="Canonical 64-character SHA-256 digest of the submitted parameters.",
    )
    user_modified: bool = Field(
        False,
        description="True if any values were adjusted from raw OCR candidates.",
    )
    modified_fields: list[str] = Field(
        default_factory=list,
        description="List of field names modified from initial OCR candidates.",
    )
    disclaimer: str = Field(
        "Server confirmation validates that reviewed values were verified during an authenticated "
        "session. It does not certify that the physical packaging or label itself is authentic.",
        description="Evidential scope disclaimer.",
    )
