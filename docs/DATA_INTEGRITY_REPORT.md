# healthyIndia Evidence-Based Ingredient Data & Provenance Audit Report

## Audit Overview
- **Dataset Version**: 1.1.0
- **Total Additive Records Audited**: 8
- **Verified Records**: 8
- **Partially Verified Records**: 0
- **Unverified Records**: 0
- **Unique Clean Aliases Indexed**: 132
- **Critical Provenance Errors**: 0
- **Audit Warnings**: 0

## Standards & Evidence Classification
Every factual claim is cross-checked against primary authoritative repositories:
- **Indian Statutory Regulations**: FSSAI Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011; FSSAI (Labelling and Display) Regulations, 2020.
- **International Toxicological Evaluations**: Joint FAO/WHO Expert Committee on Food Additives (JECFA) monographs, WHO Technical Report Series, IARC monographs.
- **Food Standards**: Codex General Standard for Food Additives (GSFA, Codex Stan 192-1995).

## Individual Additive Record Verification
| Additive ID | Canonical Name | INS Code | Chemical Identity (CAS) | Status | Citations | FSSAI Cited | JECFA/WHO Cited |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| `ins-621` | Monosodium L-glutamate | INS 621 | `CAS 142-47-2 | Molecular Formu...` | `verified` | 3 | Yes | Yes |
| `ins-951` | Aspartame | INS 951 | `CAS 22839-47-0 | Molecular For...` | `verified` | 3 | Yes | Yes |
| `ins-150d` | Caramel IV - sulphite ammonia caramel | INS 150d | `CAS 8028-89-5 | Complex polyme...` | `verified` | 2 | Yes | Yes |
| `ins-322` | Lecithins | INS 322 | `CAS 8002-43-5 | Complex mixtur...` | `verified` | 3 | Yes | Yes |
| `ins-211` | Sodium benzoate | INS 211 | `CAS 532-32-1 | Molecular Formu...` | `verified` | 2 | Yes | Yes |
| `ins-330` | Citric acid | INS 330 | `CAS 77-92-9 | Molecular Formul...` | `verified` | 2 | Yes | Yes |
| `ins-102` | Tartrazine | INS 102 | `CAS 1934-21-0 | Molecular Form...` | `verified` | 3 | Yes | Yes |
| `ins-500ii` | Sodium hydrogen carbonate | INS 500(ii) | `CAS 144-55-8 | Molecular Formu...` | `verified` | 2 | Yes | Yes |

## Scientific Integrity Principles Applied
1. **Presence != Harm**: The presence of an additive does not by itself prove that a food is dangerous. Effects are evaluated based on dose, exposure, and specific sensitivities.
2. **Category-Specific Legality**: An INS number does not imply universal permission across all foods. Permitted categories and quantitative limits are strictly documented.
3. **Population Sensitivities**: Target advisories (e.g. PKU for Aspartame, infant food prohibition for MSG, soya allergen for soy lecithin, aspirin cross-reactivity for Tartrazine) are explicitly identified.
4. **No Arbitrary Safety Percentage**: healthyIndia never claims a product is universally safe or unsafe based on an invented score.

## Audit Errors and Warnings
- **Zero errors or warnings detected.** All records meet strict provenance criteria.

## Scope and Known Limitations
- The reference dataset currently covers 8 common food additives widely utilized in Indian packaged foods.
- Whole food ingredients (flours, pulses, fats, spices) are deliberately preserved as unmatched tokens and not misclassified as additives.
- Future expansion will continue incrementally based on primary FSSAI Gazette amendments and JECFA monographs.