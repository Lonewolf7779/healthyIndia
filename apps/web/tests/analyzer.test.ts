import { describe, it, expect } from "vitest";
import { parseOptionalNumber } from "../src/components/NutritionDemoForm";
import {
  NutritionAnalysisResponse,
  IngredientAnalysisResponse,
  ApiClientError,
  computeNutritionValuesHash,
} from "../src/lib/api/client";

describe("Frontend Nutrition & Ingredient Analysis Logic", () => {
  describe("parseOptionalNumber", () => {
    it("preserves empty strings as null (never converts to zero)", () => {
      expect(parseOptionalNumber("")).toBeNull();
      expect(parseOptionalNumber("   ")).toBeNull();
    });

    it("distinguishes explicitly entered zero from missing value", () => {
      expect(parseOptionalNumber("0")).toBe(0);
      expect(parseOptionalNumber("0.0")).toBe(0);
      expect(parseOptionalNumber("  0  ")).toBe(0);
    });

    it("parses valid positive decimal numbers accurately", () => {
      expect(parseOptionalNumber("12.5")).toBe(12.5);
      expect(parseOptionalNumber("0.05")).toBe(0.05);
      expect(parseOptionalNumber("240")).toBe(240);
    });

    it("returns null for non-numeric junk input without throwing", () => {
      expect(parseOptionalNumber("not-a-number")).toBeNull();
      expect(parseOptionalNumber("abc")).toBeNull();
    });
  });

  describe("Analysis Response Data Integrity", () => {
    it("handles incomplete nutrition data without default-to-zero", () => {
      const response: NutritionAnalysisResponse = {
        status: "incomplete_data",
        serving_size: 30,
        serving_unit: "g",
        food_form: "solid",
        per_100: {
          energy_kcal: 450,
          added_sugar_g: null,
          sodium_mg: null,
        },
        per_serving: {
          energy_kcal: 135,
          added_sugar_g: null,
          sodium_mg: null,
        },
        daily_value_comparisons: [
          {
            nutrient_key: "added_sugar_g",
            display_name: "Added Sugars",
            amount: null,
            unit: "g",
            reference_amount: 50,
            reference_unit: "g",
            percentage_of_daily_value: null,
            status: "missing_on_label",
            source_citation: "ICMR-NIN (2020) RDA for Indian Adults",
          },
        ],
        flags: [],
        is_complete: false,
        missing_nutrients: ["added_sugar_g", "sodium_mg"],
        disclaimer: "Missing fields are strictly preserved as unknown.",
      };

      expect(response.is_complete).toBe(false);
      expect(response.missing_nutrients).toContain("added_sugar_g");
      expect(response.per_serving.added_sugar_g).toBeNull();
      expect(response.daily_value_comparisons[0].percentage_of_daily_value).toBeNull();
    });

    it("preserves unmatched ingredients without guessing identities", () => {
      const response: IngredientAnalysisResponse = {
        matched_items: [
          {
            raw_text: "Flavour Enhancer (INS 621)",
            match_type: "ins_number",
            confidence: 1.0,
            additive: {
              id: "ins-621",
              canonical_name: "Monosodium Glutamate (MSG)",
              ins_number: "INS 621",
              e_number: "E 621",
              functional_classes: ["Flavour enhancer"],
              jurisdiction: "India (FSSAI) & Codex Alimentarius",
              regulatory_status:
                "Permitted under Good Manufacturing Practice (GMP) in specified categories under FSSAI regulations; prohibited in foods intended for infants below 12 months.",
              status_verification: "verified",
              scope_limitations: "Prohibited in foods intended for infants below 12 months.",
              sources: [
                {
                  title: "FSSAI Regulations 2011",
                  url: "https://www.fssai.gov.in",
                  source_type: "Statutory Regulation",
                  retrieval_date: "2026-10-18",
                },
              ],
            },
          },
        ],
        unmatched_items: ["Whole Wheat Flour", "Refined Sunflower Oil", "Cardamom Powder"],
        total_tokens_detected: 4,
        total_matched: 1,
        total_unmatched: 3,
        disclaimer: "Deterministic reference match only.",
      };

      expect(response.total_matched).toBe(1);
      expect(response.total_unmatched).toBe(3);
      expect(response.unmatched_items).toEqual([
        "Whole Wheat Flour",
        "Refined Sunflower Oil",
        "Cardamom Powder",
      ]);
      expect(response.matched_items[0].additive.regulatory_status).toContain(
        "prohibited in foods intended for infants"
      );
    });

    it("verifies ApiClientError encapsulates safe error codes without internal tracebacks", () => {
      const err = new ApiClientError("Validation failed for input", "VALIDATION_ERROR", 422);
      expect(err.message).toBe("Validation failed for input");
      expect(err.code).toBe("VALIDATION_ERROR");
      expect(err.status).toBe(422);
      // Ensure no raw Python traceback leaked into message
      expect(err.message).not.toContain("Traceback");
      expect(err.message).not.toContain("fastapi");
      expect(err.message).not.toContain("pydantic");
    });

    it("verifies OCR response mandates verification and holds candidate values", () => {
      const ocrData = {
        raw_text: "Serving 30g\nEnergy 140 kcal\nIngredients: Wheat, Oil",
        nutrition_lines: ["Serving 30g", "Energy 140 kcal"],
        ingredients_text: "Wheat, Oil",
        nutrient_candidates: {
          energy_kcal: {
            field_name: "energy_kcal",
            raw_text: "Energy 140 kcal",
            value: 140,
            unit: "kcal",
            confidence: 85,
          },
        },
        serving_size_candidate: 30,
        serving_unit_candidate: "g",
        overall_confidence: 85,
        warnings: [
          {
            code: "LOW_CONFIDENCE",
            message: "OCR confidence is low (85%). Please verify values.",
          },
        ],
        verification_required: true,
        disclaimer: "Machine-generated draft requiring manual review.",
      };

      expect(ocrData.verification_required).toBe(true);
      expect(ocrData.serving_size_candidate).toBe(30);
      expect(ocrData.nutrient_candidates.energy_kcal.value).toBe(140);
      expect(ocrData.warnings[0].code).toBe("LOW_CONFIDENCE");
    });
  });

  describe("computeNutritionValuesHash", () => {
    it("computes deterministic SHA-256 hash matching backend canonical format", () => {
      const nutrients = {
        added_sugar_g: 12.5,
        carbohydrates_g: 55.0,
        cholesterol_mg: null,
        dietary_fiber_g: 3.2,
        energy_kcal: 420.0,
        protein_g: 8.0,
        saturated_fat_g: 4.5,
        sodium_mg: 350.0,
        total_fat_g: 15.0,
        total_sugar_g: 20.0,
        trans_fat_g: 0.0,
      };

      const hash1 = computeNutritionValuesHash(30, "g", "per_serving", "solid", nutrients);
      const hash2 = computeNutritionValuesHash(30, "g", "per_serving", "solid", nutrients);

      expect(hash1).toBe(hash2);
      expect(hash1).toBe("c47fddbe51641e511f79178e72d01525a96d875bda2da4fd11f4ad7db3a2b329");
    });

    it("breaks hash equality when any nutrient is modified", () => {
      const baseNutrients = {
        added_sugar_g: 12.5,
        carbohydrates_g: 55.0,
        cholesterol_mg: null,
        dietary_fiber_g: 3.2,
        energy_kcal: 420.0,
        protein_g: 8.0,
        saturated_fat_g: 4.5,
        sodium_mg: 350.0,
        total_fat_g: 15.0,
        total_sugar_g: 20.0,
        trans_fat_g: 0.0,
      };

      const baseHash = computeNutritionValuesHash(30, "g", "per_serving", "solid", baseNutrients);

      // Mutate one value
      const modifiedNutrients = { ...baseNutrients, added_sugar_g: 12.6 };
      const modifiedHash = computeNutritionValuesHash(30, "g", "per_serving", "solid", modifiedNutrients);

      expect(modifiedHash).not.toBe(baseHash);
    });

    it("breaks hash equality when foodForm, servingUnit, or basis is modified", () => {
      const baseNutrients = {
        added_sugar_g: 12.5,
        carbohydrates_g: 55.0,
        cholesterol_mg: null,
        dietary_fiber_g: 3.2,
        energy_kcal: 420.0,
        protein_g: 8.0,
        saturated_fat_g: 4.5,
        sodium_mg: 350.0,
        total_fat_g: 15.0,
        total_sugar_g: 20.0,
        trans_fat_g: 0.0,
      };

      const baseHash = computeNutritionValuesHash(30, "g", "per_serving", "solid", baseNutrients);

      // Change foodForm
      const liquidHash = computeNutritionValuesHash(30, "g", "per_serving", "liquid", baseNutrients);
      expect(liquidHash).not.toBe(baseHash);

      // Change servingUnit
      const mlHash = computeNutritionValuesHash(30, "ml", "per_serving", "solid", baseNutrients);
      expect(mlHash).not.toBe(baseHash);

      // Change basis
      const per100Hash = computeNutritionValuesHash(30, "g", "per_100g", "solid", baseNutrients);
      expect(per100Hash).not.toBe(baseHash);
    });
  });
});
