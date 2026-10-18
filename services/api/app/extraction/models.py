"""
Domain models for OCR extraction and review workflow.
"""

from dataclasses import dataclass, field


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


@dataclass(frozen=True)
class ExtractionWarning:
    """
    Advisory or uncertainty warning produced during OCR and parsing.
    """

    code: str
    message: str


@dataclass
class OcrExtractionResult:
    """
    Structured outcome of local OCR processing and parsing.
    All data is considered untrusted input until explicitly confirmed by the user.
    """

    raw_text: str
    nutrition_lines: list[str] = field(default_factory=list)
    ingredients_text: str | None = None
    nutrient_candidates: dict[str, ExtractedNutrientCandidate] = field(default_factory=dict)
    serving_size_candidate: float | None = None
    serving_unit_candidate: str | None = None
    overall_confidence: float | None = None
    warnings: list[ExtractionWarning] = field(default_factory=list)
    verification_required: bool = True
    disclaimer: str = (
        "OCR extraction is preliminary and machine-generated. Physical print quality, "
        "lighting, reflections, or packaging folds may cause errors. The user must review, "
        "verify, and correct all values before submission."
    )
