# Food Label OCR & Deterministic Parsing Benchmark Report

Generated: 2026-10-19 05:49:53Z
Environment: Local deterministic test framework with OpenCV & Tesseract (Tesseract runtime present: True)
Overall Suite Status: **PASS**

---

## 1. Executive Summary

This benchmark rigorously evaluates the deterministic parsing heuristics, computer vision quality gates,
nutrient-to-value association, and independent mathematical calculation pipelines of the healthyIndia food-label scanner.

> [!IMPORTANT]
> **Real-World Physical Camera Accuracy Remains Unmeasured.**
> These benchmarks measure algorithmic adherence, parser syntax, and computer vision
> boundaries on synthetic test fixtures, controlled rendered images, and mathematical boundary cases.
> Real-world accuracy on varied packaging reflections, warped foil pouches, curved cylindrical cans, and
> low-end mobile cameras remains unmeasured until comprehensive physical field testing with a verified ground-truth dataset.


---

## 2. Benchmark Metrics & Evaluated Denominators

| Category | Evaluated Cases (Denominator) | Correct | Errors | Success Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Synthetic Text Parser Correctness** | 9 realistic text fixtures | 9 | 0 | **100.0%** | PASS |
| **OCR Adapter Plumbing (Mock Integration)** | 4 mock adapter assertions | 4 | 0 | **100.0%** | PASS |
| **Rendered-Image OCR Recognition (Tesseract)** | 5 rendered test lines | 5 | 0 | **100.0%** | PASS |
| **Nutrient-to-Value Association** | 83 nutrient fields | 83 | 0 | **100.0%** | PASS |
| **Serving-Size & Unit Interpretation** | 6 unit/serving formats | 6 | 0 | **100.0%** | PASS |
| **Independent Numerical Calculation Correctness** | 32 mathematical checks | 32 | 0 | **100.0%** | PASS |
| **Computer Vision Quality-Gate Decisions** | 7 edge-case inputs | 7 | 0 | **100.0%** | PASS |
| **Real-World Packaging Photographs** | 0 physical camera photographs (UNMEASURED) | 0 | 0 | **N/A (Unmeasured)** | UNMEASURED |

**Overall Benchmark Outcome**: **PASS** (All required criteria met)
Quality-Gate Specifics: False Acceptances: 0, False Rejections: 0.

---

## 3. Discrepancy & Plausibility Protection

The scanner implements defense-in-depth against silent misinterpretations:
1. **Multi-Pass OCR Discrepancy Detection**: Dual preprocessing passes (CLAHE normalized vs deskewed binarization) audit character-level consistency. Note: agreement between passes does not guarantee accuracy when both passes encounter identical character degradation.
2. **Physical Plausibility Constraints**:
   - Added Sugars cannot exceed Total Sugars (with documented 0.2g regulatory rounding tolerance).
   - Saturated Fat + Trans Fat cannot exceed Total Fat (with documented 0.5g rounding allowance).
   - Solid food macronutrient sum cannot exceed 105g per 100g (5g analytical tolerance).
   - Liquid food macronutrient sum per 100ml accounts for liquid densities up to 1.45 g/ml (syrups/honey).
   - Atwater calorie discrepancy flags discordance between declared energy and macronutrients, with documented exceptions for dietary fiber, polyols, and organic acids.
3. **Strict Confirmation Workflow**:
   - Extracted values are tagged as unverified draft candidates (`status: "unconfirmed"`).
   - Final nutrition calculations require explicit confirmation of all inputs with cryptographic SHA-256 digest validation (`confirmed_values_hash`).

---

## 4. Public Release Acceptance Criteria

Before declaring the food label scanner ready for unassisted public deployment, the following physical criteria must be satisfied:
1. **Physical Dataset**: Minimum 500 verified camera photographs across 10 distinct Indian packaged food categories (biscuits, namkeen, dairy, beverages, instant noodles, edible oils, spices, breakfast cereals, confectionery, ready meals). Current status: Specification and 10 transcribed reference baselines established (status: SCHEMA_VERIFIED_EVIDENCE_PENDING); physical image files are not bundled in repository (0 physical camera photos evaluated).
2. **Real-World Character Recognition**: Character accuracy >= 98.5% on clear packaging; >= 92% on curved or glossy packages. Current status: UNMEASURED.
3. **Nutrient Association Accuracy**: >= 95% correct association of numbers to parent nutrients on physical camera images. Current status: UNMEASURED.
4. **Zero Silent Conversions**: 100% adherence to the zero-conversion rule (missing values remain `None`, never converted to `0.0`). Current status: PASSED in algorithmic and mathematical suites.
5. **Zero Unconfirmed Calculations**: 100% mandatory user verification before final nutrition calculations. Current status: PASSED with cryptographic SHA-256 value-tied confirmation hash.

**Public Release Readiness Gate Status**: **NOT READY** (Physical camera photograph dataset not bundled; character and nutrient recognition on physical camera photos remains unmeasured).
