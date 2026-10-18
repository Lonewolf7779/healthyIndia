# Food Label OCR & Deterministic Parsing Benchmark Report

Generated: 2026-10-18 08:27:51Z
Environment: Local deterministic test framework with OpenCV & Tesseract

---

## 1. Executive Summary

This benchmark validates the deterministic parsing heuristics, computer vision quality gates,
multi-column association, and calculation pipelines of the healthyIndia food-label scanner.

> [!IMPORTANT]
> **Real-World Camera Accuracy Remains Unmeasured.**
> These benchmarks measure algorithmic adherence, parser syntax, and computer vision
> boundaries on synthetic test fixtures and controlled edge cases. Real-world accuracy
> on varied packaging reflections, warped foil pouches, curved cylindrical cans, and
> low-end mobile cameras remains unmeasured until comprehensive physical field testing.

---

## 2. Benchmark Metrics

| Category | Evaluated Cases | Success Rate | Status |
| :--- | :--- | :--- | :--- |
| **Synthetic Text Recognition & Parsing** | 9 realistic fixtures | **100.0%** | PASS |
| **Nutrient-to-Value Association** | 83 nutrient fields | **100.0%** | PASS |
| **Serving-Size & Unit Interpretation** | 5 unit/serving formats | **100.0%** | PASS |
| **Final Calculation Correctness** | 2 confirmed inputs | **100.0%** | PASS |
| **Input Rejection & Quality Gates** | 3 corrupted/blurry inputs | **100.0%** | PASS |

---

## 3. Discrepancy & Plausibility Protection

The scanner implements defense-in-depth against silent misinterpretations:
1. **Multi-Pass OCR Discrepancy Detection**: Dual preprocessing passes (CLAHE normalized vs deskewed binarization) audit character-level consistency. Any substantial divergence flags `OCR_PASS_DISCREPANCY`.
2. **Physical Plausibility Constraints**:
   - Added Sugars cannot exceed Total Sugars.
   - Saturated Fat + Trans Fat cannot exceed Total Fat.
   - Macronutrient sum cannot exceed 100g per 100g (or serving weight).
   - Atwater calorie discrepancy flags discordance between declared energy and macronutrients.
3. **Strict Confirmation Workflow**:
   - Extracted values are tagged as unverified draft candidates (`status: "unconfirmed"`).
   - Final nutrition calculations require explicit confirmation of all inputs.

---

## 4. Public Release Acceptance Criteria

Before declaring the food label scanner ready for unassisted public deployment, the following physical criteria must be satisfied:
1. **Physical Dataset**: Minimum 500 verified camera photographs across 10 distinct Indian packaged food categories (biscuits, namkeen, dairy, beverages, instant noodles, edible oils, spices, breakfast cereals, confectionery, ready meals).
2. **Real-World Character Recognition**: Character accuracy >= 98.5% on clear packaging; >= 92% on curved or glossy packages.
3. **Nutrient Association Accuracy**: >= 95% correct association of numbers to parent nutrients on physical camera images.
4. **Zero Silent Conversions**: 100% adherence to the zero-conversion rule (missing values remain `None`, never converted to `0.0`).
5. **Zero Unconfirmed Calculations**: 100% mandatory user verification before final nutrition calculations.
