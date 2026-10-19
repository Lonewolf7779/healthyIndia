"""
Unit and regression tests for Phase 4D expanded ingredients catalogue.

Validates positive and negative deterministic matching for:
- Palm Oil (ing-palm-oil)
- Whole Wheat Flour / Atta (ing-whole-wheat-flour)
- Refined Wheat Flour / Maida (ing-refined-wheat-flour)
- Sugar / Sucrose (ing-sugar)
- Iodized Salt (ing-iodized-salt)
"""

from app.schemas.ingredients import IngredientAnalysisRequest
from app.services.ingredient_service import IngredientService


def test_positive_match_palm_oil_and_aliases() -> None:
    for phrase in [
        "palm oil",
        "refined palm oil",
        "edible palm oil",
        "palmolein",
        "refined palmolein",
        "fractionated palm oil",
        "palm olein",
        "पाम तेल",
        "पामोलीन",
    ]:
        req = IngredientAnalysisRequest(ingredients_text=phrase)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) >= 1, f"Expected match for '{phrase}'"
        match = next(m for m in res.matched_items if m.additive.id == "ing-palm-oil")
        assert match.additive.canonical_name == "Palm Oil"
        assert match.additive.cas_number == "8002-75-3"


def test_positive_match_whole_wheat_flour_atta() -> None:
    for phrase in [
        "atta",
        "whole wheat flour",
        "wheat atta",
        "chakki atta",
        "wholemeal wheat flour",
        "whole grain wheat flour",
        "आटा",
        "गेहूं का आटा",
    ]:
        req = IngredientAnalysisRequest(ingredients_text=phrase)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) >= 1, f"Expected match for '{phrase}'"
        match = next(m for m in res.matched_items if m.additive.id == "ing-whole-wheat-flour")
        assert match.additive.canonical_name == "Whole Wheat Flour (Atta)"
        assert "allergen" in match.additive.categories


def test_positive_match_refined_wheat_flour_maida() -> None:
    for phrase in [
        "maida",
        "refined wheat flour",
        "refined flour",
        "white flour",
        "all-purpose flour",
        "मैदा",
    ]:
        req = IngredientAnalysisRequest(ingredients_text=phrase)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) >= 1, f"Expected match for '{phrase}'"
        match = next(m for m in res.matched_items if m.additive.id == "ing-refined-wheat-flour")
        assert match.additive.canonical_name == "Refined Wheat Flour (Maida)"
        assert match.additive.cas_number == "130498-22-5"
        assert "allergen" in match.additive.categories


def test_positive_match_sugar_sucrose() -> None:
    for phrase in [
        "sugar",
        "white sugar",
        "cane sugar",
        "refined sugar",
        "table sugar",
        "sucrose",
        "crystal sugar",
        "चीनी",
        "शक्कर",
    ]:
        req = IngredientAnalysisRequest(ingredients_text=phrase)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) >= 1, f"Expected match for '{phrase}'"
        match = next(m for m in res.matched_items if m.additive.id == "ing-sugar")
        assert match.additive.canonical_name == "Sugar (Sucrose)"
        assert match.additive.cas_number == "57-50-1"


def test_positive_match_iodized_salt() -> None:
    for phrase in [
        "iodized salt",
        "iodised salt",
        "edible common salt",
        "table salt",
        "namak",
        "common salt",
        "नमक",
        "आयोडीन युक्त नमक",
    ]:
        req = IngredientAnalysisRequest(ingredients_text=phrase)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) >= 1, f"Expected match for '{phrase}'"
        match = next(m for m in res.matched_items if m.additive.id == "ing-iodized-salt")
        assert match.additive.canonical_name == "Iodized Salt"
        assert match.additive.cas_number == "7647-14-5"


def test_negative_matching_broad_unrelated_terms() -> None:
    """Verifies that out-of-context generic terms do not hallucinate matches."""
    unmatched_terms = [
        "oil",  # bare generic oil should not match palm oil
        "fat",  # bare generic fat should not match
        "flour",  # bare generic flour should not match atta or maida
        "grain",
        "sweetener",  # bare generic category
        "refined",  # bare adjective
        "powder",
    ]

    for term in unmatched_terms:
        req = IngredientAnalysisRequest(ingredients_text=term)
        res = IngredientService.analyze(req)
        assert len(res.matched_items) == 0, (
            f"Expected zero matches for generic term '{term}', got {res.matched_items}"
        )


def test_realistic_indian_packaged_food_ingredient_statement() -> None:
    """Tests deterministic parsing of a representative Indian biscuit ingredient list."""
    label_text = (
        "Refined Wheat Flour (Maida) (65%), Palm Oil, Sugar, Inulin, "
        "Iodised Salt, Raising Agent (INS 500(ii)), Emulsifier (INS 322(i))"
    )

    req = IngredientAnalysisRequest(ingredients_text=label_text)
    res = IngredientService.analyze(req)

    matched_ids = {m.additive.id for m in res.matched_items}
    assert "ing-refined-wheat-flour" in matched_ids
    assert "ing-palm-oil" in matched_ids
    assert "ing-sugar" in matched_ids
    assert "nutr-inulin" in matched_ids
    assert "ing-iodized-salt" in matched_ids
    assert "ins-500ii" in matched_ids
    assert "ins-322" in matched_ids

    # Unmatched items should not contain matched staples
    assert not any("sugar" in u.lower() for u in res.unmatched_items)
    assert not any("palm oil" in u.lower() for u in res.unmatched_items)
