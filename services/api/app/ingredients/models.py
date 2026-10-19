"""
Domain data models for ingredient reference and matching.
Independent of web frameworks and database engines.

Phase 4A: Extensible Ingredient Knowledge Base Foundation.
Supports:
1. Ordinary food ingredients.
2. Food additives.
3. Compound ingredients and nested sub-ingredients.
4. Allergens and declared allergen derivatives.
5. Sweeteners.
6. Vitamins and minerals used for fortification.
7. Flavourings and flavour enhancers.
8. Processing aids.
9. Nutritional components.
10. Unknown or unresolved label terms.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IngredientCategory(StrEnum):
    """Broad, non-mutually-exclusive ingredient categories."""

    ORDINARY_INGREDIENT = "ordinary_ingredient"
    FOOD_ADDITIVE = "food_additive"
    COMPOUND_INGREDIENT = "compound_ingredient"
    ALLERGEN = "allergen"
    SWEETENER = "sweetener"
    FORTIFICATION_COMPOUND = "fortification_compound"
    FLAVOURING = "flavouring"
    PROCESSING_AID = "processing_aid"
    NUTRITIONAL_COMPONENT = "nutritional_component"
    UNKNOWN = "unknown"


class RecordStatus(StrEnum):
    """Lifecycle status of a reference knowledge-base record."""

    ACTIVE = "active"
    PROVISIONAL = "provisional"
    DEPRECATED = "deprecated"


class MatchType(StrEnum):
    """Explicit deterministic match mechanism."""

    EXACT_CANONICAL = "exact_canonical"
    EXACT_ALIAS = "exact_alias"
    INS_NUMBER = "ins_number"
    E_NUMBER = "e_number"
    INDIAN_LANGUAGE_ALIAS = "indian_language_alias"
    CONTEXT_AWARE = "context_aware"
    COMPOUND_SUB_INGREDIENT = "compound_sub_ingredient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceProvenance:
    """
    Multi-track verification provenance.
    Syntactic validity is strictly distinguished from scientific consensus
    and statutory regulatory authorization across 5 independent tracks.
    """

    schema_valid: bool = True
    source_linked: bool = False
    source_checked: bool = False
    scientifically_reviewed: bool = False
    regulatory_verified: bool = False
    # "schema_only" | "source_linked" | "partially_verified" | "fully_verified"
    verification_level: str = "unverified"
    jurisdiction: str = "India (FSSAI) & Codex Alimentarius"
    regulatory_act: str = ""
    notes: str = ""

    # Phase 4C: 5 Independent Verification Tracks & Audit Metadata
    source_url_recorded: bool = False
    source_url_accessible: bool = False
    source_content_checked: bool = False
    scientific_claim_supported: bool = False
    regulatory_claim_verified: bool = False
    audit_date: str = ""
    auditor_role: str = ""
    scientific_review_status: str = "unverified"  # "verified" | "partially_verified"
    regulatory_verification_status: str = "unverified"  # "verified" | "partially_verified"
    claim_verification_notes: str = ""


@dataclass(frozen=True)
class SourceReference:
    """Documented bibliographic or regulatory citation."""

    title: str
    url: str
    source_type: str
    retrieval_date: str
    organization: str = ""
    publication_date: str = ""
    supported_claims: str = ""
    section_or_regulation: str = ""
    license: str = ""
    url_accessible: bool = True
    verification_status: str = "verified"  # "verified" | "partially_verified" | "unverified"
    citation_tier: str = "primary_statutory"  # primary_statutory | primary_scientific_body


@dataclass(frozen=True)
class IngredientRecord:
    """
    Generalized ingredient knowledge base entity.
    Unifies ordinary foods, additives, fortification compounds, sweeteners,
    allergens, and compound foods without forcing all into an additive-only schema.
    """

    id: str
    canonical_name: str
    entity_type: IngredientCategory = IngredientCategory.ORDINARY_INGREDIENT
    categories: list[IngredientCategory] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    indian_language_aliases: dict[str, list[str]] = field(default_factory=dict)
    ins_number: str | None = None
    e_number: str | None = None
    cas_number: str | None = None
    functional_classes: list[str] = field(default_factory=list)
    parent_ingredient_id: str | None = None
    sub_ingredient_ids: list[str] = field(default_factory=list)
    sources: list[SourceReference] = field(default_factory=list)
    jurisdiction: str = "India (FSSAI) & Codex Alimentarius"
    regulatory_status: str = "unverified"
    status_verification: str = "unverified"  # "verified" | "unverified"
    scope_limitations: str = ""
    provenance: EvidenceProvenance = field(default_factory=EvidenceProvenance)
    chemical_identity: str = ""
    health_effects_evidence: str = ""
    acceptable_daily_intake: str = ""
    population_sensitivities: str = ""
    everyday_quantity_explanation: dict[str, Any] | None = None
    known_limitations_and_uncertainty: str = ""
    last_reviewed: str = ""
    dataset_version: str = "1.0.0"
    record_status: RecordStatus = RecordStatus.ACTIVE


# Backward compatibility alias for existing code
AdditiveEntry = IngredientRecord


@dataclass(frozen=True)
class MatchedIngredient:
    """
    Result of a deterministic ingredient match.
    Preserves occurrence frequency and sub-ingredient relationships.
    """

    raw_text: str
    match_type: MatchType
    confidence: float
    ingredient: IngredientRecord
    occurrences: int = 1
    raw_mentions: list[str] = field(default_factory=list)
    sub_matches: list["MatchedIngredient"] = field(default_factory=list)
    is_compound: bool = False

    def __init__(
        self,
        raw_text: str,
        match_type: MatchType,
        confidence: float,
        ingredient: IngredientRecord | None = None,
        additive: IngredientRecord | None = None,
        occurrences: int = 1,
        raw_mentions: list[str] | None = None,
        sub_matches: list["MatchedIngredient"] | None = None,
        is_compound: bool = False,
    ):
        resolved_ingredient = ingredient or additive
        if resolved_ingredient is None:
            raise ValueError("MatchedIngredient requires either 'ingredient' or 'additive'.")
        object.__setattr__(self, "raw_text", raw_text)
        object.__setattr__(self, "match_type", match_type)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "ingredient", resolved_ingredient)
        object.__setattr__(self, "occurrences", occurrences)
        resolved_mentions = raw_mentions if raw_mentions is not None else [raw_text]
        object.__setattr__(self, "raw_mentions", resolved_mentions)
        object.__setattr__(self, "sub_matches", sub_matches or [])
        object.__setattr__(self, "is_compound", is_compound)

    @property
    def additive(self) -> IngredientRecord:
        """Backwards compatibility alias for code expecting .additive"""
        return self.ingredient


@dataclass(frozen=True)
class IngredientAnalysisResult:
    """
    Comprehensive, explainable ingredient parsing result.
    Guarantees unknown terms remain visible and distinct from ambiguous terms.
    """

    matched_items: list[MatchedIngredient]
    unmatched_items: list[str]
    total_tokens_detected: int
    total_matched: int
    total_unmatched: int
    disclaimer: str
    ambiguous_items: list[str] = field(default_factory=list)
    category_summary: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
