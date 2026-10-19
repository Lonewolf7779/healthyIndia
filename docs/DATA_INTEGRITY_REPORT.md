# healthyIndia Evidence-Based Ingredient Data & Provenance Audit Report

## Audit Overview & Four-Phase Verification Architecture
healthyIndia strictly distinguishes between automated syntactic validation and independent scientific consensus verification. A record is only marked verified if it passes all four independent verification tracks:
- **Dataset Version**: 1.3.0
- **Total Additive Records Audited**: 8
- **Fully Verified Records**: 8 of 8
- **1. Data Completeness Errors**: 0
- **2. Citation & Link Errors**: 0
- **3. Scientific Claim Errors**: 0
- **4. Indian Regulatory Errors**: 0
- **Audit Warnings**: 0

## Four-Phase Verification Matrix
| Additive ID | Canonical Name | Completeness | Citation Links | Scientific Evidence | Indian Regulations | Overall Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `ins-621` | Monosodium L-glutamate | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-951` | Aspartame | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-150d` | Caramel IV - sulphite ammonia caramel | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-322` | Lecithins | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-211` | Sodium benzoate | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-330` | Citric acid | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-102` | Tartrazine | PASS | PASS | PASS | PASS | **`VERIFIED`** |
| `ins-500ii` | Sodium hydrogen carbonate | PASS | PASS | PASS | PASS | **`VERIFIED`** |

## Specific Audited Scientific Claims & Corrections
1. **Aspartame (INS 951) Consumption Arithmetic**: Corrected previous mathematical error ('12–36 cans'). Reaching an ADI is explicitly distinguished from exceeding it. For a standard 60 kg reference adult (ICMR-NIN 2020), the calculated ADI is 2,400 mg. At 200 mg/can, 12 cans reaches the calculated ADI; at 300 mg/can, 8 cans reaches the calculated ADI. Exceeding the ADI requires more than 8 to 12 cans daily.
2. **Removal of Unsupported Absolutes**: Stripped unsupported assertions such as 'non-toxic at all dietary exposure levels' across records (e.g. Lecithins, Citric Acid, Sodium Benzoate). Replaced with evidence-qualified JECFA and FSSAI statements.
3. **Distinction of Guidance Types**: Clearly separates Acceptable Daily Intake (ADI, toxicological safety ceiling over a lifetime) from Recommended Daily Allowances (RDA, nutritional intake goals) and maximum permitted food concentrations (ppm limits).
4. **Everyday Quantity Explanations**: Integrated plain-language household comparisons using verified substance bulk densities and standardized 5 ml metric measuring spoons, with explicit caveats that Indian household spoons (chamach) vary (3–8 ml).

## Audit Findings Detail
- **Zero errors or warnings detected.** All 8 records satisfy data completeness, citation linkage, scientific claim accuracy, and Indian statutory regulations.

## Scope, Limitations, and Unverified Claims
- Only the 8 audited food additives are registered as verified in the reference dataset.
- Whole food ingredients (flours, pulses, oils, spices) remain deliberately classified as unmatched whole ingredients, not as additives.
- Automated checks confirm field presence and syntactic validity; scientific verification requires human expert cross-examination against Gazette notifications and toxicological monographs. No claim is marked verified merely because an automated test passed.