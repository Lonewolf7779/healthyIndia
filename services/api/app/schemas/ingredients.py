"""
Pydantic schemas for ingredient analysis requests and responses.
"""

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


class AdditiveEntrySchema(BaseModel):
    id: str
    canonical_name: str
    ins_number: str | None
    e_number: str | None
    functional_classes: list[str]
    jurisdiction: str
    regulatory_status: str
    status_verification: str
    scope_limitations: str
    chemical_identity: str | None = None
    health_effects_evidence: str | None = None
    acceptable_daily_intake: str | None = None
    population_sensitivities: str | None = None
    sources: list[SourceReferenceSchema]


class MatchedIngredientSchema(BaseModel):
    raw_text: str
    match_type: MatchType
    confidence: float
    additive: AdditiveEntrySchema


class IngredientAnalysisResponse(BaseModel):
    matched_items: list[MatchedIngredientSchema] = Field(
        ..., description="List of recognized additives with regulatory provenance."
    )
    unmatched_items: list[str] = Field(
        ..., description="List of declared ingredients not matching reference additives."
    )
    total_tokens_detected: int
    total_matched: int
    total_unmatched: int
    disclaimer: str
