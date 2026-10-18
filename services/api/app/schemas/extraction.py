"""
Pydantic schemas for OCR extraction requests and responses.
"""

from pydantic import BaseModel, Field


class ExtractedNutrientCandidateSchema(BaseModel):
    field_name: str
    raw_text: str
    value: float | None = None
    unit: str | None = None
    confidence: float | None = None


class ExtractionWarningSchema(BaseModel):
    code: str
    message: str


class OcrExtractionResponse(BaseModel):
    raw_text: str = Field(..., description="Complete raw text extracted by the local OCR engine.")
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
        description="Quality, clarity, or missing section warnings.",
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
