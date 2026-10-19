"""
Ingredient analysis orchestration service.
Decouples FastAPI route handlers from the pure ingredient matcher.
Phase 4A: Extensible Ingredient Knowledge Base Foundation.
"""

from app.ingredients.matcher import analyze_ingredients
from app.schemas.ingredients import (
    AdditiveEntrySchema,
    EvidenceProvenanceSchema,
    IngredientAnalysisRequest,
    IngredientAnalysisResponse,
    MatchedIngredientSchema,
    SourceReferenceSchema,
)


class IngredientService:
    @staticmethod
    def analyze(request: IngredientAnalysisRequest) -> IngredientAnalysisResponse:
        result = analyze_ingredients(request.ingredients_text)

        matched_schemas = []
        for item in result.matched_items:
            ing = item.ingredient
            sources_schema = [
                SourceReferenceSchema(
                    title=s.title,
                    url=s.url,
                    source_type=s.source_type,
                    retrieval_date=s.retrieval_date,
                    organization=s.organization,
                    publication_date=s.publication_date,
                    supported_claims=s.supported_claims,
                    section_or_regulation=s.section_or_regulation,
                    license=s.license,
                )
                for s in ing.sources
            ]

            prov_schema = EvidenceProvenanceSchema(
                schema_valid=ing.provenance.schema_valid,
                source_linked=ing.provenance.source_linked,
                source_checked=ing.provenance.source_checked,
                scientifically_reviewed=ing.provenance.scientifically_reviewed,
                regulatory_verified=ing.provenance.regulatory_verified,
                verification_level=ing.provenance.verification_level,
                jurisdiction=ing.provenance.jurisdiction,
                regulatory_act=ing.provenance.regulatory_act,
                notes=ing.provenance.notes,
            )

            additive_schema = AdditiveEntrySchema(
                id=ing.id,
                canonical_name=ing.canonical_name,
                entity_type=ing.entity_type.value,
                categories=[c.value for c in ing.categories],
                ins_number=ing.ins_number,
                e_number=ing.e_number,
                cas_number=ing.cas_number,
                functional_classes=ing.functional_classes,
                jurisdiction=ing.jurisdiction,
                regulatory_status=ing.regulatory_status,
                status_verification=ing.status_verification,
                scope_limitations=ing.scope_limitations,
                chemical_identity=ing.chemical_identity,
                health_effects_evidence=ing.health_effects_evidence,
                acceptable_daily_intake=ing.acceptable_daily_intake,
                population_sensitivities=ing.population_sensitivities,
                everyday_quantity_explanation=ing.everyday_quantity_explanation,
                provenance=prov_schema,
                sources=sources_schema,
            )

            matched_schemas.append(
                MatchedIngredientSchema(
                    raw_text=item.raw_text,
                    match_type=item.match_type,
                    confidence=item.confidence,
                    additive=additive_schema,
                    occurrences=item.occurrences,
                    raw_mentions=item.raw_mentions,
                    is_compound=item.is_compound,
                )
            )

        return IngredientAnalysisResponse(
            matched_items=matched_schemas,
            unmatched_items=result.unmatched_items,
            total_tokens_detected=result.total_tokens_detected,
            total_matched=result.total_matched,
            total_unmatched=result.total_unmatched,
            disclaimer=result.disclaimer,
            ambiguous_items=result.ambiguous_items,
            category_summary=result.category_summary,
        )
