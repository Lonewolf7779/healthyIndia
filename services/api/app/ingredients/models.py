"""
Domain data models for ingredient reference and matching.
Independent of web frameworks and database engines.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MatchType(StrEnum):
    INS_NUMBER = "ins_number"
    EXACT_ALIAS = "exact_alias"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceReference:
    title: str
    url: str
    source_type: str
    retrieval_date: str
    organization: str = ""
    publication_date: str = ""
    supported_claims: str = ""
    section_or_regulation: str = ""


@dataclass(frozen=True)
class AdditiveEntry:
    id: str
    canonical_name: str
    ins_number: str | None
    e_number: str | None
    functional_classes: list[str]
    aliases: list[str]
    sources: list[SourceReference]
    jurisdiction: str
    regulatory_status: str
    status_verification: str  # "verified" | "unverified"
    scope_limitations: str
    chemical_identity: str = ""
    health_effects_evidence: str = ""
    acceptable_daily_intake: str = ""
    population_sensitivities: str = ""


@dataclass(frozen=True)
class MatchedIngredient:
    raw_text: str
    match_type: MatchType
    confidence: float
    additive: AdditiveEntry


@dataclass(frozen=True)
class IngredientAnalysisResult:
    matched_items: list[MatchedIngredient]
    unmatched_items: list[str]
    total_tokens_detected: int
    total_matched: int
    total_unmatched: int
    disclaimer: str
    metadata: dict[str, Any] = field(default_factory=dict)
