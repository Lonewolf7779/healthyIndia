"""
Pydantic schemas for ingredient analysis requests and responses.
Phase 4A: Extensible Ingredient Knowledge Base Foundation.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.ingredients.models import MatchType


class IngredientAnalysisRequest(BaseModel):
    """
    Input schema containing raw ingredient list declaration from food packaging.
    """

    ingredients_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Declared ingredients string from food packaging.",
        examples=[
            "Wheat Flour (65%), Palm Oil, Sugar, Salt, Emulsifier (INS 322(i)), "
            "Raising Agent (INS 500(ii)), Flavour Enhancer (621), Preservative (INS 211)"
        ],
    )


class SourceReferenceSchema(BaseModel):
    title: str
    url: str
    source_type: str
    retrieval_date: str
    organization: str | None = None
    publication_date: str | None = None
    supported_claims: str | None = None
    section_or_regulation: str | None = None
    license: str | None = None


class EvidenceProvenanceSchema(BaseModel):
    schema_valid: bool = True
    source_linked: bool = False
    source_checked: bool = False
    scientifically_reviewed: bool = False
    regulatory_verified: bool = False
    verification_level: str = "unverified"
    jurisdiction: str = "India (FSSAI) & Codex Alimentarius"
    regulatory_act: str | None = None
    notes: str | None = None


class AdditiveEntrySchema(BaseModel):
    id: str
    canonical_name: str
    entity_type: str = "food_additive"
    categories: list[str] = Field(default_factory=list)
    ins_number: str | None = None
    e_number: str | None = None
    cas_number: str | None = None
    functional_classes: list[str] = Field(default_factory=list)
    jurisdiction: str
    regulatory_status: str
    status_verification: str
    scope_limitations: str
    chemical_identity: str | None = None
    health_effects_evidence: str | None = None
    acceptable_daily_intake: str | None = None
    population_sensitivities: str | None = None
    everyday_quantity_explanation: dict[str, Any] | None = None
    provenance: EvidenceProvenanceSchema | None = None
    sources: list[SourceReferenceSchema] = Field(default_factory=list)


class MatchedIngredientSchema(BaseModel):
    raw_text: str
    match_type: MatchType
    confidence: float
    additive: AdditiveEntrySchema
    occurrences: int = 1
    raw_mentions: list[str] = Field(default_factory=list)
    is_compound: bool = False


class IngredientAnalysisResponse(BaseModel):
    matched_items: list[MatchedIngredientSchema] = Field(
        ..., description="List of recognized ingredients and additives with regulatory provenance."
    )
    unmatched_items: list[str] = Field(
        ..., description="List of declared ingredients not matching reference entries."
    )
    total_tokens_detected: int
    total_matched: int
    total_unmatched: int
    disclaimer: str
    ambiguous_items: list[str] = Field(default_factory=list)
    category_summary: dict[str, int] = Field(default_factory=dict)
