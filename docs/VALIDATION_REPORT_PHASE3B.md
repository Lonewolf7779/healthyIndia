# healthyIndia Real-World Food Label Validation Report (Phase 3B.1)

## Executive Summary
- **Canonical Fixtures Evaluated**: 9
- **Parser Candidate Field Accuracy**: 100.0% (84 / 84 ground-truth fields)
- **Food Additive Matching Accuracy**: 100.0% (20 / 20 curated additives)
- **Unmatched Food Staples Preserved**: 50 tokens kept visible without guessing
- **Nutrition Calculation Scenarios Verified**: 100.0% (9 / 9)

## Metric Definitions and Formulas
1. **Parser Candidate Field Accuracy**:
   - **Definition**: The proportion of explicitly expected nutrient candidates and metric serving sizes correctly extracted within ±0.2 units of ground truth.
   - **Formula**: `(correctly_parsed_fields / total_expected_fields) * 100`
   - **Denominator**: Total non-null ground-truth values defined across all synthetic fixtures.

2. **Additive Matching Accuracy**:
   - **Definition**: The proportion of verified additives (INS/E numbers or canonical aliases) correctly matched from ingredient declarations.
   - **Formula**: `(correctly_matched_additives / total_expected_additives) * 100`
   - **Integrity Rule**: Unrecognized staple ingredients (e.g. Flour, Palm Oil, Spices) MUST remain in `unmatched_items` and never falsely matched.

3. **Nutrition Engine Determinism**:
   - **Definition**: The proportion of calculation scenarios where units, serving scaling, missing value preservation, and threshold flags strictly match FSSAI reference criteria.
   - **Formula**: `(passed_scenarios / total_scenarios) * 100`

## Fixture Results Breakdown
| Fixture ID | Product Category / Name | Parser Fields | Additives Matched | Unmatched Staples | Nutrition Status | Flags |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `fixture_01_glucose_biscuits` | SunGold Glucose Biscuits | 10/10 | 2/2 | 6 | `complete` | 2 |
| `fixture_02_bikaneri_bhujia` | Desi Swad Bikaneri Bhujia | 10/10 | 1/1 | 9 | `complete` | 2 |
| `fixture_03_instant_noodles` | QuickTreat Masala Instant Noodles | 11/11 | 3/3 | 6 | `complete` | 2 |
| `fixture_04_mixed_fruit_drink` | Amrit Mixed Fruit Nectar | 9/9 | 2/2 | 4 | `complete` | 1 |
| `fixture_05_multi_additive_extruded_rings` | Crunchy Munch Tomato Rings | 10/10 | 6/6 | 6 | `complete` | 2 |
| `fixture_06_difficult_linebroken_label` | Pahadi Roasted Namkeen | 10/10 | 1/1 | 5 | `complete` | 2 |
| `fixture_07_incomplete_nutrition_label` | Traditional Bakery Rusk | 5/5 | 1/1 | 6 | `incomplete_data` | 1 |
| `fixture_08_energy_in_kj_only` | Export Tea Biscuits | 9/9 | 2/2 | 4 | `complete` | 2 |
| `fixture_09_parenthesized_portion_weight` | Premium Choco Cookies | 10/10 | 2/2 | 4 | `complete` | 2 |

## Uncertainty and Quality Warnings Emitted
| Warning Code | Occurrences | Interpretation |
| :--- | :---: | :--- |
| `ENERGY_KJ_CONVERTED` | 1 | Energy declared solely in kJ was converted to kcal via standard 4.184 factor. |
| `MISSING_SERVING_SIZE` | 4 | No explicit serving size was stated on the packaging panel. |

## Known Limitations and Scientific Boundary Safeguards
1. **OCR Machine Generation Disclaimer**: All extracted OCR values are provisional candidate suggestions and require user verification before being submitted to analysis APIs.
2. **Category-Specific Permission**: Identifying an additive (e.g. INS 211, INS 951) does not imply blanket authorization across all food categories under FSSAI regulations.
3. **Discrete Unit Normalization**: Discrete serving units (e.g., '2 Biscuits') without gram weights cannot be normalized to per-100g without individual piece mass.
4. **No Arbitrary Safety Percentage**: healthyIndia deterministic calculations never compute an overall 'safe percentage' or claim absolute product safety.

## Reproducibility
This report is generated deterministically by `scripts/run_validation_suite.py` and validated by pytest in CI.