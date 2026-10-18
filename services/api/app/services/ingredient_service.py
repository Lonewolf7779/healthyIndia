"""
Ingredient analysis orchestration service.
Decouples FastAPI route handlers from the pure ingredient matcher.
"""

from app.ingredients.matcher import analyze_ingredients
from app.schemas.ingredients import (
    AdditiveEntrySchema,
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
            sources_schema = [
                SourceReferenceSchema(
                    title=s.title,
                    url=s.url,
                    source_type=s.source_type,
                    retrieval_date=s.retrieval_date,
                )
                for s in item.additive.sources
            ]

            additive_schema = AdditiveEntrySchema(
                id=item.additive.id,
                canonical_name=item.additive.canonical_name,
                ins_number=item.additive.ins_number,
                e_number=item.additive.e_number,
                functional_classes=item.additive.functional_classes,
                jurisdiction=item.additive.jurisdiction,
                regulatory_status=item.additive.regulatory_status,
                status_verification=item.additive.status_verification,
                scope_limitations=item.additive.scope_limitations,
                sources=sources_schema,
            )

            matched_schemas.append(
                MatchedIngredientSchema(
                    raw_text=item.raw_text,
                    match_type=item.match_type,
                    confidence=item.confidence,
                    additive=additive_schema,
                )
            )

        return IngredientAnalysisResponse(
            matched_items=matched_schemas,
            unmatched_items=result.unmatched_items,
            total_tokens_detected=result.total_tokens_detected,
            total_matched=result.total_matched,
            total_unmatched=result.total_unmatched,
            disclaimer=result.disclaimer,
        )
