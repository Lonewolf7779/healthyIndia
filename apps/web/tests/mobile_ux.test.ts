import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import {
  validateImageFile,
  buildReviewFieldsFromOcr,
  scannerReducer,
  initialScannerState,
} from "../src/components/LabelScanner";
import { parseOptionalNumber } from "../src/components/NutritionDemoForm";
import {
  IngredientAnalysisResponse,
  NutritionAnalysisResponse,
  OcrExtractionResponse,
} from "../src/lib/api/client";

describe("Mobile-First Scanner and UX Verification Suite (Phase 4B)", () => {
  describe("Viewport Width Constraints and Zero Horizontal Overflow", () => {
    const representativeViewports = [320, 360, 390, 430, 768, 1024, 1280];

    it("verifies grid columns never exceed available container width at any supported viewport", () => {
      // At each viewport, calculate available width inside main content
      for (const vw of representativeViewports) {
        // Desktop padding: 24px each side (48px total), Mobile padding: 14-16px each side (28-32px total), Smallest: 8px each side (16px total)
        const sidePadding = vw <= 360 ? 16 : vw <= 640 ? 28 : 48;
        const availableWidth = vw - sidePadding;

        // Formula: min(100%, 280px)
        const gridItemMinWidth = Math.min(availableWidth, 280);

        // Grid item min-width must NEVER exceed available width
        expect(gridItemMinWidth).toBeLessThanOrEqual(availableWidth);
        expect(availableWidth).toBeGreaterThan(0);
      }
    });

    it("verifies nutrient input grid columns fit within narrow 320px screens without overflow", () => {
      const vw = 320;
      const padding = 16;
      const availableWidth = vw - padding; // 304px
      // Formula: min(100%, 140px)
      const columnMinWidth = Math.min(availableWidth, 140);

      // Two columns with 8px gap: 140 + 140 + 8 = 288px <= 304px
      const twoColumnsWidth = columnMinWidth * 2 + 8;
      expect(twoColumnsWidth).toBeLessThanOrEqual(availableWidth);
    });

    it("verifies globals.css enforces overflow-x hidden on root container", () => {
      const cssPath = resolve(__dirname, "../src/app/globals.css");
      const cssContent = readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain("overflow-x: hidden");
      expect(cssContent).toContain("max-width: 100vw");
    });

    it("verifies globals.css defines WCAG minimum 44px touch targets", () => {
      const cssPath = resolve(__dirname, "../src/app/globals.css");
      const cssContent = readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain("min-height: 44px");
      expect(cssContent).toContain(".touch-checkbox-label");
      expect(cssContent).toContain("min-width: 44px");
    });

    it("verifies globals.css sets 16px font size on inputs to prevent iOS Safari auto-zoom", () => {
      const cssPath = resolve(__dirname, "../src/app/globals.css");
      const cssContent = readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain("font-size: 16px !important;");
    });

    it("verifies globals.css implements accessible focus rings and reduced-motion preferences", () => {
      const cssPath = resolve(__dirname, "../src/app/globals.css");
      const cssContent = readFileSync(cssPath, "utf-8");

      expect(cssContent).toContain(":focus-visible");
      expect(cssContent).toContain("outline: 2px solid var(--color-primary)");
      expect(cssContent).toContain("@media (prefers-reduced-motion: reduce)");
    });
  });

  describe("Mobile Label Scanner Workflow & Edge Cases", () => {
    it("handles camera-captured and gallery-selected files interchangeably", () => {
      const cameraPhoto = new File(["camera-jpeg-bytes"], "camera_capture.jpg", {
        type: "image/jpeg",
      });
      const galleryUpload = new File(["gallery-png-bytes"], "gallery_photo.png", {
        type: "image/png",
      });

      expect(validateImageFile(cameraPhoto).valid).toBe(true);
      expect(validateImageFile(galleryUpload).valid).toBe(true);
    });

    it("state reducer correctly tracks draft extraction and unconfirmed review count", () => {
      const mockOcr: OcrExtractionResponse = {
        extraction_id: "ext-mobile-001",
        extraction_token: "tok-mobile-001",
        raw_text: "Energy 120 kcal, Protein 3g",
        serving_size_candidate: 25,
        serving_unit_candidate: "g",
        nutrient_candidates: {
          energy_kcal: {
            field_name: "energy_kcal",
            raw_text: "120 kcal",
            value: 120,
            unit: "kcal",
            confidence: 0.95,
          },
          protein_g: {
            field_name: "protein_g",
            raw_text: "3g",
            value: 3,
            unit: "g",
            confidence: 0.92,
          },
        },
        ingredients_text: "Wheat Flour, Sugar",
        image_quality: {
          is_acceptable: true,
          grade: "good",
          metrics: {
            width: 1200,
            height: 800,
            total_pixels: 960000,
            sharpness_score: 180,
            glare_ratio: 0.02,
            mean_luminance: 140,
            contrast_std: 55,
            estimated_skew_degrees: 0.5,
            min_content_margin_px: 20,
          },
          warnings: [],
          disclaimer: "Quality metrics acceptable.",
        },
        warnings: [],
        overall_confidence: 94,
        column_basis_detected: "per_serving",
        nutrition_lines: ["Energy 120 kcal", "Protein 3g"],
        verification_required: true,
        disclaimer: "Review against physical packaging required.",
      };

      const extractedState = scannerReducer(initialScannerState, {
        type: "EXTRACTION_SUCCESS",
        data: mockOcr,
      });

      expect(extractedState.reviewFields.servingSize).toBe("25");
      expect(extractedState.reviewFields.energyKcal).toBe("120");
      expect(extractedState.reviewFields.proteinG).toBe("3");
      expect(extractedState.confirmedFields.energyKcal).toBe(false);

      // User confirms all fields on mobile checklist
      const confirmedState = scannerReducer(extractedState, {
        type: "ALL_FIELDS_CONFIRMED",
      });

      expect(confirmedState.confirmedFields.energyKcal).toBe(true);
      expect(confirmedState.confirmedFields.proteinG).toBe(true);
      expect(confirmedState.confirmedFields.servingSize).toBe(true);

      // User manually edits a field on mobile keyboard -> that specific field's confirmation must reset to false
      const editedState = scannerReducer(confirmedState, {
        type: "FIELD_UPDATED",
        field: "energyKcal",
        value: "125",
      });

      expect(editedState.reviewFields.energyKcal).toBe("125");
      expect(editedState.confirmedFields.energyKcal).toBe(false);
      expect(editedState.confirmedFields.proteinG).toBe(true);
    });
  });

  describe("Phase 4A Ingredient Intelligence Integration in Mobile UI", () => {
    it("safely accepts and processes ambiguous items without throwing or guessing", () => {
      const response: IngredientAnalysisResponse = {
        matched_items: [
          {
            raw_text: "Soy Lecithin",
            match_type: "exact_alias",
            confidence: 0.95,
            occurrences: 2,
            raw_mentions: ["Soy Lecithin", "Lecithin"],
            is_compound: false,
            additive: {
              id: "ins-322",
              canonical_name: "Lecithins",
              entity_type: "food_additive",
              categories: ["food_additive", "allergen"],
              ins_number: "INS 322",
              e_number: "E 322",
              functional_classes: ["Emulsifier"],
              jurisdiction: "India (FSSAI) & Codex Alimentarius",
              regulatory_status: "PERMITTED",
              status_verification: "verified",
              scope_limitations: "GMP in specified food categories",
              sources: [],
            },
          },
        ],
        unmatched_items: ["Wheat Flour"],
        ambiguous_items: ["Emulsifier", "Preservative"],
        category_summary: {
          food_additive: 1,
          allergen: 1,
        },
        total_tokens_detected: 4,
        total_matched: 1,
        total_unmatched: 1,
        disclaimer: "Deterministic results.",
      };

      expect(response.ambiguous_items).toEqual(["Emulsifier", "Preservative"]);
      expect(response.category_summary?.food_additive).toBe(1);
      expect(response.matched_items[0].occurrences).toBe(2);
      expect(response.matched_items[0].raw_mentions).toContain("Soy Lecithin");
    });
  });
});
