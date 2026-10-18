from app.ingredients.matcher import analyze_ingredients, split_ingredients_list
from app.ingredients.models import MatchType


def test_split_ingredients_nested_parentheses() -> None:
    text = (
        "Wheat Flour (Atta 60%, Maida 40%), Palm Oil, "
        "Seasoning (Salt, Spices (Chilli, Coriander), Sugar), "
        "Emulsifier (INS 322(i)); Acidity Regulator (INS 330)"
    )
    tokens = split_ingredients_list(text)
    assert len(tokens) == 5
    assert tokens[0] == "Wheat Flour (Atta 60%, Maida 40%)"
    assert tokens[1] == "Palm Oil"
    assert tokens[2] == "Seasoning (Salt, Spices (Chilli, Coriander), Sugar)"
    assert tokens[3] == "Emulsifier (INS 322(i))"
    assert tokens[4] == "Acidity Regulator (INS 330)"


def test_ins_number_extraction_formats() -> None:
    # Test different formatting of INS codes commonly observed on Indian packaging
    test_cases = [
        ("Flavour Enhancer (INS 621)", "ins-621", MatchType.INS_NUMBER),
        ("Emulsifier (INS 322(i))", "ins-322", MatchType.INS_NUMBER),
        ("Colour (150d)", "ins-150d", MatchType.INS_NUMBER),
        ("Preservative: E 211", "ins-211", MatchType.INS_NUMBER),
        ("Raising Agent (500(ii))", "ins-500ii", MatchType.INS_NUMBER),
        ("Acidity Regulator (INS-330)", "ins-330", MatchType.INS_NUMBER),
    ]

    for raw_string, expected_id, expected_match_type in test_cases:
        result = analyze_ingredients(raw_string)
        assert len(result.matched_items) == 1, f"Failed matching: {raw_string}"
        item = result.matched_items[0]
        assert item.additive.id == expected_id
        assert item.match_type == expected_match_type
        assert item.confidence == 1.0


def test_case_insensitivity_and_punctuation() -> None:
    # Unusual casing, trailing dots, extra whitespace
    text = "  •  mSg  . ,  TARTRAZINE  ;  sOyA  LeCiThIn  "
    result = analyze_ingredients(text)

    matched_ids = [m.additive.id for m in result.matched_items]
    assert "ins-621" in matched_ids
    assert "ins-102" in matched_ids
    assert "ins-322" in matched_ids


def test_unknown_ingredients_preserved_without_guessing() -> None:
    text = "Wheat Flour, Iodized Salt, Natural Spices (Cumin, Pepper), Cardamom"
    result = analyze_ingredients(text)

    # None of these whole staple ingredients are in the food additives dataset
    assert len(result.matched_items) == 0
    assert len(result.unmatched_items) == 4
    assert "Wheat Flour" in result.unmatched_items
    assert "Iodized Salt" in result.unmatched_items
    assert "Natural Spices (Cumin, Pepper)" in result.unmatched_items
    assert "Cardamom" in result.unmatched_items


def test_duplicate_additive_mentions_deduplicated() -> None:
    # Product lists MSG by name and by INS number in two places
    text = "Monosodium Glutamate, Salt, Spices, Flavour Enhancer (INS 621)"
    result = analyze_ingredients(text)

    # Both refer to ins-621; result should report ins-621 once in matched_items
    msg_matches = [m for m in result.matched_items if m.additive.id == "ins-621"]
    assert len(msg_matches) == 1
    assert result.total_matched == 1


def test_regulatory_status_and_limitations_present() -> None:
    text = "Aspartame (Sweetener INS 951)"
    result = analyze_ingredients(text)

    assert len(result.matched_items) == 1
    matched = result.matched_items[0]
    additive = matched.additive

    assert additive.canonical_name == "Aspartame"
    assert additive.status_verification == "verified"
    assert "phenylketonurics" in additive.regulatory_status.lower()
    assert "Prohibited in general foods" in additive.scope_limitations
    assert len(additive.sources) > 0
    assert "FSSAI" in additive.sources[0].title
