"""
Category D: Comprehensive Ingredient Matching and Regulatory Verification Suite.

Validates deterministic additive identification, alias normalization, boundary isolation,
similar-number discrimination, unknown ingredient visibility, and regulatory provenance.
"""

from app.extraction.parser import parse_ocr_text
from app.ingredients.matcher import analyze_ingredients, split_ingredients_list
from app.ingredients.models import MatchType
from tests.fixtures.realistic_fixtures import load_realistic_fixtures


def test_realistic_fixtures_ingredient_matching() -> None:
    """
    Tests ingredient parsing and additive matching across all canonical fixtures.
    Ensures expected additives are matched and whole foods remain visible as unmatched tokens.
    """
    fixtures = load_realistic_fixtures()

    for fixture in fixtures:
        # First extract ingredients section using parser
        parse_res = parse_ocr_text(fixture["raw_text"])
        ing_text = parse_res.ingredients_text or fixture["raw_text"]

        result = analyze_ingredients(ing_text)

        expected_additives = fixture.get("expected_matched_additives", [])
        matched_ids = [m.additive.id for m in result.matched_items]

        for expected_id in expected_additives:
            assert expected_id in matched_ids, (
                f"Fixture {fixture['id']}: expected additive {expected_id} "
                f"not found in {matched_ids}"
            )

        # Unmatched ingredients must remain present and visible to user
        assert result.total_tokens_detected >= len(matched_ids)
        assert len(result.disclaimer) > 0


def test_exact_aliases_all_curated_additives() -> None:
    """
    Verifies that canonical names and common commercial aliases match their respective entries.
    """
    alias_cases = [
        ("Monosodium glutamate", "ins-621"),
        ("MSG", "ins-621"),
        ("Flavour Enhancer 621", "ins-621"),
        ("Aspartame", "ins-951"),
        ("Sweetener (951)", "ins-951"),
        ("Caramel IV", "ins-150d"),
        ("Sulphite ammonia caramel", "ins-150d"),
        ("Colour (150d)", "ins-150d"),
        ("Soya lecithin", "ins-322"),
        ("Soy lecithin", "ins-322"),
        ("Sunflower lecithin", "ins-322"),
        ("Sodium benzoate", "ins-211"),
        ("Benzoate of soda", "ins-211"),
        ("Citric acid", "ins-330"),
        ("Acid (330)", "ins-330"),
        ("Tartrazine", "ins-102"),
        ("FD&C Yellow 5", "ins-102"),
        ("Sodium bicarbonate", "ins-500ii"),
        ("Baking soda", "ins-500ii"),
        ("Sodium hydrogen carbonate", "ins-500ii"),
    ]

    for alias, expected_id in alias_cases:
        res = analyze_ingredients(alias)
        assert len(res.matched_items) == 1, f"Failed matching alias: '{alias}'"
        assert res.matched_items[0].additive.id == expected_id
        assert res.matched_items[0].confidence == 1.0


def test_ins_code_formatting_variations() -> None:
    """
    Tests various syntactic representations of INS and E numbers seen on Indian packaging.
    """
    variations = [
        ("INS 322(i)", "ins-322"),
        ("INS 322i", "ins-322"),
        ("ins. 322(i)", "ins-322"),
        ("E-322", "ins-322"),
        ("E322", "ins-322"),
        ("INS 500(ii)", "ins-500ii"),
        ("INS-500ii", "ins-500ii"),
        ("500(ii)", "ins-500ii"),
        ("E 500(ii)", "ins-500ii"),
        ("INS 621", "ins-621"),
        ("E-621", "ins-621"),
        ("INS 150d", "ins-150d"),
        ("INS-150d", "ins-150d"),
        ("E 150d", "ins-150d"),
    ]

    for raw_token, expected_id in variations:
        res = analyze_ingredients(raw_token)
        assert len(res.matched_items) == 1, f"Failed matching variation: '{raw_token}'"
        assert res.matched_items[0].additive.id == expected_id
        assert res.matched_items[0].match_type == MatchType.INS_NUMBER


def test_similar_number_discrimination() -> None:
    """
    Critical integrity test: Prevents false-positive matching against similar-looking
    but distinct or unverified additive numbers.
    """
    # INS 150a (Plain caramel) vs INS 150d (Caramel IV)
    res_150a = analyze_ingredients("Colour (INS 150a)")
    assert len(res_150a.matched_items) == 0
    assert "Colour (INS 150a)" in res_150a.unmatched_items

    # INS 627 (Disodium guanylate) vs INS 621 (MSG)
    res_627 = analyze_ingredients("Flavour Enhancer (INS 627)")
    assert len(res_627.matched_items) == 0
    assert "Flavour Enhancer (INS 627)" in res_627.unmatched_items

    # INS 210 (Benzoic acid) vs INS 211 (Sodium benzoate)
    res_210 = analyze_ingredients("Preservative (INS 210)")
    assert len(res_210.matched_items) == 0
    assert "Preservative (INS 210)" in res_210.unmatched_items

    # INS 100 (Curcumin) vs INS 102 (Tartrazine)
    res_100 = analyze_ingredients("Natural Colour (INS 100)")
    assert len(res_100.matched_items) == 0
    assert "Natural Colour (INS 100)" in res_100.unmatched_items

    # INS 500(i) (Sodium carbonate) vs INS 500(ii) (Sodium bicarbonate)
    res_500i = analyze_ingredients("Raising Agent (INS 500(i))")
    assert len(res_500i.matched_items) == 0
    assert "Raising Agent (INS 500(i))" in res_500i.unmatched_items


def test_unknown_ingredients_remain_visible() -> None:
    """
    Whole staples and unrecognized ingredients must never be discarded or silently hidden.
    """
    text = (
        "Refined Wheat Flour (Maida), Edible Vegetable Oil (Palmolein), "
        "Sugar, Iodised Salt, Cardamom Powder, Ginger Extract"
    )
    res = analyze_ingredients(text)

    assert len(res.matched_items) == 0
    assert len(res.unmatched_items) == 6
    assert "Refined Wheat Flour (Maida)" in res.unmatched_items
    assert "Sugar" in res.unmatched_items
    assert "Iodised Salt" in res.unmatched_items
    assert res.total_unmatched == 6


def test_parentheses_and_punctuation_tokenization() -> None:
    """
    Splits ingredient lists cleanly while preserving nested parentheses and complex sub-clauses.
    """
    complex_text = (
        "Flour (Wheat Flour [Atta 70%], Refined Flour [Maida 30%]), "
        "Seasoning (Salt, Spices (Chilli, Cumin, Pepper), Sugar), "
        "Emulsifier (INS 322(i)); Acidity Regulator (Citric Acid)"
    )
    tokens = split_ingredients_list(complex_text)
    assert len(tokens) == 4
    assert "Flour (Wheat Flour [Atta 70%], Refined Flour [Maida 30%])" in tokens
    assert "Seasoning (Salt, Spices (Chilli, Cumin, Pepper), Sugar)" in tokens
    assert "Emulsifier (INS 322(i))" in tokens
    assert "Acidity Regulator (Citric Acid)" in tokens

    res = analyze_ingredients(complex_text)
    matched_ids = [m.additive.id for m in res.matched_items]
    assert "ins-322" in matched_ids
    assert "ins-330" in matched_ids


def test_deduplication_of_repeated_additives() -> None:
    """
    If an additive is mentioned twice (e.g. by alias and by INS number in different components),
    it is reported once in matched_items without inflating match counts.
    """
    text = (
        "Noodle Cake: Refined Wheat Flour, Palm Oil, Acidity Regulator (INS 500(ii)). "
        "Tastemaker: Spices, Salt, Raising Agent (Sodium Bicarbonate), Flavour Enhancer (621)."
    )
    res = analyze_ingredients(text)

    # Both INS 500(ii) and Sodium Bicarbonate point to ins-500ii
    ins500_matches = [m for m in res.matched_items if m.additive.id == "ins-500ii"]
    assert len(ins500_matches) == 1
    assert any(m.additive.id == "ins-621" for m in res.matched_items)


def test_regulatory_provenance_and_limitations() -> None:
    """
    Verifies that all matched additives include traceable statutory sources,
    clear category limitations, and do not make absolute safety claims.
    """
    text = "Aspartame (INS 951), Tartrazine (INS 102), Sodium Benzoate (INS 211)"
    res = analyze_ingredients(text)

    assert len(res.matched_items) == 3

    for item in res.matched_items:
        additive = item.additive
        assert additive.status_verification == "verified"
        assert len(additive.sources) > 0

        # Check source traceability
        statutory_source = next((s for s in additive.sources if "FSSAI" in s.title), None)
        assert statutory_source is not None
        assert statutory_source.url.startswith("https://")
        assert statutory_source.source_type == "Statutory Regulation"

        # Check that scope limitations are explicit and never claim blanket permission
        assert len(additive.scope_limitations) > 0
        assert (
            "permission" in additive.regulatory_status.lower()
            or "permitted" in additive.regulatory_status.lower()
        )

    # The result-level disclaimer must explicitly remind user of category-specific rules
    assert "FSSAI" in res.disclaimer
    assert "does not constitute an evaluation of product safety" in res.disclaimer
