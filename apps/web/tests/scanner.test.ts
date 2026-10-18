import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  validateImageFile,
  safeRevokeObjectURL,
  buildReviewFieldsFromOcr,
  scannerReducer,
  initialScannerState,
  initialReviewFields,
  MAX_UPLOAD_SIZE_BYTES,
  ScannerState,
} from "../src/components/LabelScanner";
import { OcrExtractionResponse } from "../src/lib/api/client";

describe("LabelScanner Image Selection & Lifecycle", () => {
  const originalRevokeObjectURL = URL.revokeObjectURL;
  const originalCreateObjectURL = URL.createObjectURL;

  beforeEach(() => {
    URL.revokeObjectURL = vi.fn();
    URL.createObjectURL = vi.fn((file: Blob) => `blob:http://localhost/${(file as File).name}`);
  });

  afterEach(() => {
    URL.revokeObjectURL = originalRevokeObjectURL;
    URL.createObjectURL = originalCreateObjectURL;
    vi.restoreAllMocks();
  });

  describe("validateImageFile", () => {
    it("accepts valid JPEG, PNG, and WEBP files within 10 MB", () => {
      const validPng = new File(["dummy content"], "label.png", { type: "image/png" });
      const validJpg = new File(["dummy content"], "label.jpg", { type: "image/jpeg" });
      const validWebp = new File(["dummy content"], "label.webp", { type: "image/webp" });

      expect(validateImageFile(validPng)).toEqual({ valid: true });
      expect(validateImageFile(validJpg)).toEqual({ valid: true });
      expect(validateImageFile(validWebp)).toEqual({ valid: true });
    });

    it("rejects unsupported file formats like GIF, SVG, or plain text", () => {
      const gif = new File(["dummy"], "label.gif", { type: "image/gif" });
      const txt = new File(["dummy"], "label.txt", { type: "text/plain" });

      const gifResult = validateImageFile(gif);
      expect(gifResult.valid).toBe(false);
      expect(gifResult.error).toContain("supported image file (JPEG, PNG, or WEBP)");

      const txtResult = validateImageFile(txt);
      expect(txtResult.valid).toBe(false);
      expect(txtResult.error).toContain("supported image file");
    });

    it("rejects oversized images exceeding 10 MB", () => {
      const oversized = new File(["dummy"], "big.png", { type: "image/png" });
      Object.defineProperty(oversized, "size", { value: MAX_UPLOAD_SIZE_BYTES + 1 });

      const result = validateImageFile(oversized);
      expect(result.valid).toBe(false);
      expect(result.error).toContain("exceeds the maximum limit of 10 MB");
    });

    it("handles null or undefined file selection (file picker cancellation)", () => {
      expect(validateImageFile(null)).toEqual({ valid: false, error: "No file selected." });
      expect(validateImageFile(undefined)).toEqual({ valid: false, error: "No file selected." });
    });
  });

  describe("safeRevokeObjectURL lifecycle", () => {
    it("revokes object URL when a valid string is passed", () => {
      safeRevokeObjectURL("blob:http://localhost/test-uuid");
      expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:http://localhost/test-uuid");
    });

    it("safely ignores null or undefined URLs without throwing", () => {
      expect(() => safeRevokeObjectURL(null)).not.toThrow();
      expect(() => safeRevokeObjectURL(undefined)).not.toThrow();
      expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    });
  });

  describe("scannerReducer state transitions", () => {
    const mockFileA = new File(["image-bytes-a"], "photo_a.jpg", { type: "image/jpeg" });
    const mockFileB = new File(["image-bytes-b"], "photo_b.png", { type: "image/png" });

    it("transitions on valid image selection", () => {
      const nextState = scannerReducer(initialScannerState, {
        type: "FILE_SELECTED",
        file: mockFileA,
        previewUrl: "blob:http://localhost/photo_a.jpg",
      });

      expect(nextState.selectedFile).toBe(mockFileA);
      expect(nextState.previewUrl).toBe("blob:http://localhost/photo_a.jpg");
      expect(nextState.uploading).toBe(false);
      expect(nextState.error).toBeNull();
      expect(nextState.ocrResult).toBeNull();
      expect(nextState.transferred).toBe(false);
    });

    it("clears previously selected file, preview, and results when an unsupported file is selected", () => {
      // 1. Establish state with valid image and existing OCR result
      const stateWithValidFile: ScannerState = {
        ...initialScannerState,
        selectedFile: mockFileA,
        previewUrl: "blob:http://localhost/photo_a.jpg",
        ocrResult: {
          raw_text: "Nutrition facts",
          nutrition_lines: ["Energy 100"],
          ingredients_text: null,
          nutrient_candidates: {},
          serving_size_candidate: 30,
          serving_unit_candidate: "g",
          overall_confidence: 90,
          warnings: [],
          verification_required: true,
          disclaimer: "test",
        },
        transferred: true,
      };

      // 2. User selects an unsupported GIF file
      const nextState = scannerReducer(stateWithValidFile, {
        type: "FILE_REJECTED",
        error: "Please select a supported image file (JPEG, PNG, or WEBP).",
      });

      expect(nextState.selectedFile).toBeNull();
      expect(nextState.previewUrl).toBeNull();
      expect(nextState.ocrResult).toBeNull();
      expect(nextState.transferred).toBe(false);
      expect(nextState.error).toBe("Please select a supported image file (JPEG, PNG, or WEBP).");
    });

    it("clears previous state when user selects an oversized file", () => {
      const stateWithValidFile: ScannerState = {
        ...initialScannerState,
        selectedFile: mockFileA,
        previewUrl: "blob:http://localhost/photo_a.jpg",
      };

      const nextState = scannerReducer(stateWithValidFile, {
        type: "FILE_REJECTED",
        error: "Image file size exceeds the maximum limit of 10 MB.",
      });

      expect(nextState.selectedFile).toBeNull();
      expect(nextState.previewUrl).toBeNull();
      expect(nextState.error).toContain("10 MB");
    });

    it("clears selection when file picker is cancelled", () => {
      const stateWithValidFile: ScannerState = {
        ...initialScannerState,
        selectedFile: mockFileA,
        previewUrl: "blob:http://localhost/photo_a.jpg",
      };

      const nextState = scannerReducer(stateWithValidFile, {
        type: "FILE_CLEARED",
      });

      expect(nextState.selectedFile).toBeNull();
      expect(nextState.previewUrl).toBeNull();
      expect(nextState.error).toBeNull();
    });

    it("manages extraction failure and recovers loading state", () => {
      const runningState = scannerReducer(initialScannerState, {
        type: "EXTRACTION_STARTED",
      });
      expect(runningState.uploading).toBe(true);
      expect(runningState.error).toBeNull();

      const failedState = scannerReducer(runningState, {
        type: "EXTRACTION_FAILURE",
        error: "OCR extraction timed out after 15 seconds.",
      });
      expect(failedState.uploading).toBe(false);
      expect(failedState.error).toBe("OCR extraction timed out after 15 seconds.");
      expect(failedState.ocrResult).toBeNull();
    });

    it("handles extraction success and populates editable review fields", () => {
      const mockOcrData: OcrExtractionResponse = {
        raw_text: "Serving Size: 30g\nEnergy: 140 kcal\nIngredients: Wheat Flour",
        nutrition_lines: ["Serving Size: 30g", "Energy: 140 kcal"],
        ingredients_text: "Wheat Flour",
        nutrient_candidates: {
          energy_kcal: {
            field_name: "energy_kcal",
            raw_text: "Energy: 140 kcal",
            value: 140.0,
            unit: "kcal",
            confidence: 95.0,
          },
        },
        serving_size_candidate: 30.0,
        serving_unit_candidate: "g",
        overall_confidence: 95.0,
        warnings: [],
        verification_required: true,
        disclaimer: "User review required.",
      };

      const runningState = scannerReducer(initialScannerState, {
        type: "EXTRACTION_STARTED",
      });

      const successState = scannerReducer(runningState, {
        type: "EXTRACTION_SUCCESS",
        data: mockOcrData,
      });

      expect(successState.uploading).toBe(false);
      expect(successState.ocrResult).toEqual(mockOcrData);
      expect(successState.reviewFields.servingSize).toBe("30");
      expect(successState.reviewFields.energyKcal).toBe("140");
      expect(successState.reviewFields.ingredientsText).toBe("Wheat Flour");
    });

    it("allows manual editing of candidate fields before transfer", () => {
      const stateWithOcr = scannerReducer(initialScannerState, {
        type: "EXTRACTION_SUCCESS",
        data: {
          raw_text: "Serving Size: 30g",
          nutrition_lines: [],
          ingredients_text: null,
          nutrient_candidates: {},
          serving_size_candidate: 30,
          serving_unit_candidate: "g",
          overall_confidence: 90,
          warnings: [],
          verification_required: true,
          disclaimer: "test",
        },
      });

      const editedState = scannerReducer(stateWithOcr, {
        type: "FIELD_UPDATED",
        field: "servingSize",
        value: "35",
      });

      expect(editedState.reviewFields.servingSize).toBe("35");
    });

    it("records verified transfer state", () => {
      const state = scannerReducer(initialScannerState, {
        type: "VALUES_TRANSFERRED",
      });
      expect(state.transferred).toBe(true);
    });

    it("resets scanner to initial clean state", () => {
      const dirtyState: ScannerState = {
        ...initialScannerState,
        selectedFile: mockFileA,
        previewUrl: "blob:http://localhost/test",
        uploading: false,
        error: "Previous error",
        ocrResult: null,
        transferred: true,
        reviewFields: { ...initialReviewFields, servingSize: "50" },
      };

      const resetState = scannerReducer(dirtyState, { type: "RESET" });
      expect(resetState).toEqual(initialScannerState);
    });
  });

  describe("buildReviewFieldsFromOcr", () => {
    it("safely handles null candidates without converting missing to zero", () => {
      const emptyOcrData: OcrExtractionResponse = {
        raw_text: "",
        nutrition_lines: [],
        ingredients_text: null,
        nutrient_candidates: {},
        serving_size_candidate: null,
        serving_unit_candidate: null,
        overall_confidence: null,
        warnings: [],
        verification_required: true,
        disclaimer: "test",
      };

      const fields = buildReviewFieldsFromOcr(emptyOcrData);
      expect(fields.servingSize).toBe("");
      expect(fields.energyKcal).toBe("");
      expect(fields.addedSugarG).toBe("");
      expect(fields.sodiumMg).toBe("");
      expect(fields.ingredientsText).toBe("");
    });
  });
});
