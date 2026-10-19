# healthyIndia Phase 4A: Ingredient Engine & Knowledge Base Audit Report

## 1. Audit Overview

This audit reviews the architecture, data models, tokenizers, matchers, schemas, and verification pipelines of the existing `healthyIndia` ingredient engine as of commit `54024ebedd931d60b7765be7ba9e3b2eb94d6195`.

---

## 2. Findings on Required Audit Questions

### 1. Which ingredient categories the system can currently recognize
- **Exclusively Food Additives**: The current engine is tightly bound to `AdditiveEntry` and only recognizes 8 audited food additives in `data/ingredient_reference/additives_v1.json`:
  1. `ins-621`: Monosodium L-glutamate (Flavour enhancer)
  2. `ins-951`: Aspartame (Sweetener)
  3. `ins-150d`: Caramel IV - sulphite ammonia caramel (Colour)
  4. `ins-322`: Lecithins (Emulsifier)
  5. `ins-211`: Sodium benzoate (Preservative)
  6. `ins-330`: Citric acid (Acidity regulator)
  7. `ins-102`: Tartrazine (Colour)
  8. `ins-500ii`: Sodium hydrogen carbonate (Raising agent)

### 2. Which categories the system cannot currently recognize
- **Ordinary Food Ingredients**: Whole agricultural staples, flours (e.g. Atta, Maida, Besan), edible oils (e.g. Palmolein, Mustard oil), dairy (e.g. Milk solids), spices, and culinary salt.
- **Compound Ingredients and Sub-Ingredients**: Multi-component preparations (e.g., `Milk Chocolate (Sugar, Cocoa Butter, Milk Solids...)`, `Seasoning Mix (...)`) are kept as monolithic strings; sub-ingredients are not recognized or parsed into parent-child trees.
- **Allergens and Declared Allergen Derivatives**: No formal category or classification for FSSAI-mandated allergen declarations (cereals containing gluten, crustaceans, milk, eggs, fish, peanuts, tree nuts, soybeans, sulphites).
- **Sweeteners**: Nutritive sweeteners (sugar, invert syrup, glucose) and non-nutritive intense sweeteners (sucralose, stevia) are not recognized as a distinct category (only Aspartame as an additive).
- **Vitamins and Minerals (Fortification Compounds)**: Fortification compounds under FSSAI (Fortification of Foods) Regulations 2018 (e.g., Vitamin A, Vitamin D2, Ferric Pyrophosphate, Folic Acid) are not recognized.
- **Flavourings and Botanical Extracts**: Spices, herb extracts, and nature-identical flavourings not carrying an INS code.
- **Processing Aids**: Enzymes (e.g. papain), clarifying agents, and extraction solvents.
- **Nutritional Components**: Isolated dietary fibers, inulin, and protein concentrates.
- **Unknown or Ambiguous Label Terms**: Unresolved terms are dumped into an unclassified list of strings with no diagnostic metadata or ambiguity detection.

### 3. How aliases and INS/E numbers are normalized
- **`normalize_lookup_token(token)`**: Converts to lowercase, collapses consecutive whitespace/underscores to a single space, and strips boundary punctuation (` ,.;:()[]{}'"`).
- **`normalize_ins_code(code)`**: Strips leading `ins` / `e` prefixes (case-insensitive), removes whitespace, and strips all parentheses (`INS 322(i)` -> `322i`, `500(ii)` -> `500ii`).
- **Deficiencies Identified**:
  - No support for Indian language scripts (Devanagari / Hindi) or transliterations.
  - No length or word-boundary guard against short acronym collisions with common English words.
  - Regex in `extract_ins_pattern()` permits bare 3-4 digit numbers to match as INS numbers without requiring `INS` prefix or functional-class context.

### 4. How nested and compound ingredients are parsed
- `split_ingredients_list(text)` maintains a bracket depth counter (`([{\u27e8` vs `)]}\u27e9`) to prevent splitting inside parentheses on commas.
- While this isolates the outer compound token (e.g., `Flour (Wheat Flour [Atta 70%], Refined Flour [Maida 30%])`), the matcher attempts only a single regex search `re.search(r"\(([^)]+)\)")` for inner content. If the inner content contains multiple comma-separated ingredients, the entire sub-clause fails exact alias matching and is left unparsed. Sub-ingredients are completely ignored.

### 5. How duplicate matches are handled
- The matcher uses `matched_ids: set[str] = set()` to ensure each additive ID is appended at most once in `matched_items`.
- **Deficiency**: It silently discards occurrence frequency and contextual packaging locations (e.g. when an ingredient appears in both a "Noodle Cake" and a "Tastemaker" sub-label).

### 6. Whether unknown ingredients remain visible
- Yes: unmatched tokens are preserved in `unmatched_items` and returned to API consumers and frontend UI under "Other Declared Ingredients".
- However, they are flat, unclassified strings without indication of whether they were part of a compound parent, an uncatalogued whole food, or an ambiguous term.

### 7. Whether any match can create a false positive
- **Risk 1 (Bare Numbers)**: The pattern `^([0-9]{3,4}[a-z0-9]*(?:\([a-z0-9]+\))?)$` can match bare numbers (such as "100" in "100g" or "100%") to an INS code if INS 100 is catalogued.
- **Risk 2 (Short Aliases)**: Short aliases (2–3 characters) without word-length or acronym guards risk colliding with everyday packaging terms.
- **Risk 3 (Functional Class Alone)**: A functional keyword alone (e.g., "Emulsifier", "Preservative") must never be assigned to a specific chemical identity without an identifier or specific name.

### 8. Whether evidence status is genuinely independent of schema validation
- In `verify_data_integrity.py`, an audit script evaluates 4 tracks.
- However, at runtime, the domain model `AdditiveEntry` has only a single string `status_verification: str` ("verified" | "unverified").
- The record does not track independent machine-readable flags for:
  - `schema_valid`
  - `source_linked`
  - `source_checked`
  - `scientifically_reviewed`
  - `regulatory_verified`

### 9. Which existing APIs and frontend contracts must remain compatible
- `POST /api/v1/ingredients/analyze`
- Request: `IngredientAnalysisRequest { ingredients_text: str }`
- Response: `IngredientAnalysisResponse`
  - `matched_items`: list of `MatchedIngredientSchema` containing `raw_text`, `match_type`, `confidence`, and `additive: AdditiveEntrySchema`
  - `unmatched_items`: list of `str`
  - `total_tokens_detected: int`
  - `total_matched: int`
  - `total_unmatched: int`
  - `disclaimer: str`
- Frontend `apps/web/src/lib/api/client.ts` and `apps/web/src/components/NutritionDemoForm.tsx` render:
  - `item.additive.canonical_name`
  - `item.additive.ins_number` / `e_number`
  - `item.additive.functional_classes`
  - `item.additive.chemical_identity`
  - `item.additive.regulatory_status`
  - `item.additive.scope_limitations`
  - `item.additive.acceptable_daily_intake`
  - `item.additive.health_effects_evidence`
  - `item.additive.population_sensitivities`
  - `item.additive.everyday_quantity_explanation`
  - `item.additive.sources`
- Backward Compatibility Requirement: Any unified ingredient model must supply all `AdditiveEntry` fields (with sensible defaults for non-additives) so existing frontend components and integration tests continue to function seamlessly.
