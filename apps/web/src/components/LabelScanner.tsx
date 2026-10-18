"use client";

import React, { useState, useRef, useEffect, useReducer } from "react";
import { apiClient, OcrExtractionResponse } from "../lib/api/client";

export const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
export const SUPPORTED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];

export interface TransferredValues {
  servingSize?: string;
  servingUnit?: "g" | "ml" | "piece" | "portion";
  energyKcal?: string;
  proteinG?: string;
  carbohydratesG?: string;
  totalSugarG?: string;
  addedSugarG?: string;
  dietaryFiberG?: string;
  totalFatG?: string;
  saturatedFatG?: string;
  transFatG?: string;
  cholesterolMg?: string;
  sodiumMg?: string;
  ingredientsText?: string;
}

export interface LabelScannerReviewFields {
  servingSize: string;
  servingUnit: "g" | "ml" | "piece" | "portion";
  energyKcal: string;
  proteinG: string;
  carbohydratesG: string;
  totalSugarG: string;
  addedSugarG: string;
  dietaryFiberG: string;
  totalFatG: string;
  saturatedFatG: string;
  transFatG: string;
  cholesterolMg: string;
  sodiumMg: string;
  ingredientsText: string;
}

export interface ScannerState {
  selectedFile: File | null;
  previewUrl: string | null;
  uploading: boolean;
  error: string | null;
  ocrResult: OcrExtractionResponse | null;
  transferred: boolean;
  reviewFields: LabelScannerReviewFields;
}

export type ScannerAction =
  | { type: "FILE_SELECTED"; file: File; previewUrl: string }
  | { type: "FILE_REJECTED"; error: string }
  | { type: "FILE_CLEARED" }
  | { type: "EXTRACTION_STARTED" }
  | { type: "EXTRACTION_SUCCESS"; data: OcrExtractionResponse }
  | { type: "EXTRACTION_FAILURE"; error: string }
  | { type: "VALUES_TRANSFERRED" }
  | { type: "FIELD_UPDATED"; field: keyof LabelScannerReviewFields; value: string }
  | { type: "RESET" };

export const initialReviewFields: LabelScannerReviewFields = {
  servingSize: "",
  servingUnit: "g",
  energyKcal: "",
  proteinG: "",
  carbohydratesG: "",
  totalSugarG: "",
  addedSugarG: "",
  dietaryFiberG: "",
  totalFatG: "",
  saturatedFatG: "",
  transFatG: "",
  cholesterolMg: "",
  sodiumMg: "",
  ingredientsText: "",
};

export const initialScannerState: ScannerState = {
  selectedFile: null,
  previewUrl: null,
  uploading: false,
  error: null,
  ocrResult: null,
  transferred: false,
  reviewFields: initialReviewFields,
};

/**
 * Validates an image file for format and size boundaries.
 */
export function validateImageFile(file: File | null | undefined): {
  valid: boolean;
  error?: string;
} {
  if (!file) {
    return { valid: false, error: "No file selected." };
  }

  if (!SUPPORTED_MIME_TYPES.includes(file.type)) {
    return {
      valid: false,
      error: "Please select a supported image file (JPEG, PNG, or WEBP).",
    };
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      valid: false,
      error: "Image file size exceeds the maximum limit of 10 MB.",
    };
  }

  return { valid: true };
}

/**
 * Safely revokes an object URL if valid.
 */
export function safeRevokeObjectURL(url: string | null | undefined): void {
  if (url && typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function") {
    URL.revokeObjectURL(url);
  }
}

/**
 * Converts OCR extraction response candidates into editable review field values.
 */
export function buildReviewFieldsFromOcr(
  data: OcrExtractionResponse
): LabelScannerReviewFields {
  const c = data.nutrient_candidates || {};

  return {
    servingSize:
      data.serving_size_candidate !== null && data.serving_size_candidate !== undefined
        ? String(data.serving_size_candidate)
        : "",
    servingUnit:
      data.serving_unit_candidate === "ml"
        ? "ml"
        : data.serving_unit_candidate === "piece"
        ? "piece"
        : data.serving_unit_candidate === "portion"
        ? "portion"
        : "g",
    energyKcal:
      c.energy_kcal?.value !== undefined && c.energy_kcal?.value !== null
        ? String(c.energy_kcal.value)
        : "",
    proteinG:
      c.protein_g?.value !== undefined && c.protein_g?.value !== null
        ? String(c.protein_g.value)
        : "",
    carbohydratesG:
      c.carbohydrates_g?.value !== undefined && c.carbohydrates_g?.value !== null
        ? String(c.carbohydrates_g.value)
        : "",
    totalSugarG:
      c.total_sugar_g?.value !== undefined && c.total_sugar_g?.value !== null
        ? String(c.total_sugar_g.value)
        : "",
    addedSugarG:
      c.added_sugar_g?.value !== undefined && c.added_sugar_g?.value !== null
        ? String(c.added_sugar_g.value)
        : "",
    dietaryFiberG:
      c.dietary_fiber_g?.value !== undefined && c.dietary_fiber_g?.value !== null
        ? String(c.dietary_fiber_g.value)
        : "",
    totalFatG:
      c.total_fat_g?.value !== undefined && c.total_fat_g?.value !== null
        ? String(c.total_fat_g.value)
        : "",
    saturatedFatG:
      c.saturated_fat_g?.value !== undefined && c.saturated_fat_g?.value !== null
        ? String(c.saturated_fat_g.value)
        : "",
    transFatG:
      c.trans_fat_g?.value !== undefined && c.trans_fat_g?.value !== null
        ? String(c.trans_fat_g.value)
        : "",
    cholesterolMg:
      c.cholesterol_mg?.value !== undefined && c.cholesterol_mg?.value !== null
        ? String(c.cholesterol_mg.value)
        : "",
    sodiumMg:
      c.sodium_mg?.value !== undefined && c.sodium_mg?.value !== null
        ? String(c.sodium_mg.value)
        : "",
    ingredientsText: data.ingredients_text || "",
  };
}

/**
 * Pure state reducer ensuring deterministic state transitions for scanner lifecycle.
 */
export function scannerReducer(state: ScannerState, action: ScannerAction): ScannerState {
  switch (action.type) {
    case "FILE_SELECTED":
      return {
        ...state,
        selectedFile: action.file,
        previewUrl: action.previewUrl,
        uploading: false,
        error: null,
        ocrResult: null,
        transferred: false,
        reviewFields: initialReviewFields,
      };

    case "FILE_REJECTED":
      return {
        ...state,
        selectedFile: null,
        previewUrl: null,
        uploading: false,
        error: action.error,
        ocrResult: null,
        transferred: false,
        reviewFields: initialReviewFields,
      };

    case "FILE_CLEARED":
      return {
        ...state,
        selectedFile: null,
        previewUrl: null,
        uploading: false,
        error: null,
        ocrResult: null,
        transferred: false,
        reviewFields: initialReviewFields,
      };

    case "EXTRACTION_STARTED":
      return {
        ...state,
        uploading: true,
        error: null,
        transferred: false,
      };

    case "EXTRACTION_SUCCESS":
      return {
        ...state,
        uploading: false,
        error: null,
        ocrResult: action.data,
        transferred: false,
        reviewFields: buildReviewFieldsFromOcr(action.data),
      };

    case "EXTRACTION_FAILURE":
      return {
        ...state,
        uploading: false,
        error: action.error,
        ocrResult: null,
        transferred: false,
      };

    case "VALUES_TRANSFERRED":
      return {
        ...state,
        transferred: true,
      };

    case "FIELD_UPDATED":
      return {
        ...state,
        reviewFields: {
          ...state.reviewFields,
          [action.field]: action.value,
        },
      };

    case "RESET":
      return initialScannerState;

    default:
      return state;
  }
}

interface LabelScannerProps {
  onTransferValues: (values: TransferredValues) => void;
}

export const LabelScanner: React.FC<LabelScannerProps> = ({ onTransferValues }) => {
  const [state, dispatch] = useReducer(scannerReducer, initialScannerState);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const activeRequestIdRef = useRef<number>(0);

  // Revoke preview URL on component unmount
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        safeRevokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
    };
  }, []);

  const cleanupCurrentPreview = () => {
    if (previewUrlRef.current) {
      safeRevokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Invalidate any currently running extraction request
    activeRequestIdRef.current++;

    const file = e.target.files?.[0];

    // Handle cancellation of file picker
    if (!file) {
      cleanupCurrentPreview();
      dispatch({ type: "FILE_CLEARED" });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    const validation = validateImageFile(file);

    // Handle invalid format or oversized file: clear previous selection and preview
    if (!validation.valid) {
      cleanupCurrentPreview();
      dispatch({ type: "FILE_REJECTED", error: validation.error! });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    // Valid image selected: replace preview safely
    cleanupCurrentPreview();
    const newPreviewUrl = URL.createObjectURL(file);
    previewUrlRef.current = newPreviewUrl;

    dispatch({ type: "FILE_SELECTED", file, previewUrl: newPreviewUrl });
  };

  const handleExtract = async () => {
    // Prevent duplicate extraction submissions while request is in-flight
    if (state.uploading) {
      return;
    }

    if (!state.selectedFile) {
      dispatch({
        type: "EXTRACTION_FAILURE",
        error: "Please select or capture a label image first.",
      });
      return;
    }

    const requestId = ++activeRequestIdRef.current;
    dispatch({ type: "EXTRACTION_STARTED" });

    try {
      const data = await apiClient.extractOcr(state.selectedFile);

      // Race condition guard: ignore response if user changed the image while request was in-flight
      if (activeRequestIdRef.current === requestId) {
        dispatch({ type: "EXTRACTION_SUCCESS", data });
      }
    } catch (err: unknown) {
      // Race condition guard: ignore error if user changed the image while request was in-flight
      if (activeRequestIdRef.current === requestId) {
        const message =
          err instanceof Error
            ? err.message
            : "OCR text extraction failed. Please try a clearer photograph or enter values manually.";
        dispatch({ type: "EXTRACTION_FAILURE", error: message });
      }
    }
  };

  const handleTransfer = () => {
    onTransferValues({
      servingSize: state.reviewFields.servingSize,
      servingUnit: state.reviewFields.servingUnit,
      energyKcal: state.reviewFields.energyKcal,
      proteinG: state.reviewFields.proteinG,
      carbohydratesG: state.reviewFields.carbohydratesG,
      totalSugarG: state.reviewFields.totalSugarG,
      addedSugarG: state.reviewFields.addedSugarG,
      dietaryFiberG: state.reviewFields.dietaryFiberG,
      totalFatG: state.reviewFields.totalFatG,
      saturatedFatG: state.reviewFields.saturatedFatG,
      transFatG: state.reviewFields.transFatG,
      cholesterolMg: state.reviewFields.cholesterolMg,
      sodiumMg: state.reviewFields.sodiumMg,
      ingredientsText: state.reviewFields.ingredientsText,
    });
    dispatch({ type: "VALUES_TRANSFERRED" });
  };

  const handleResetScanner = () => {
    activeRequestIdRef.current++;
    cleanupCurrentPreview();
    dispatch({ type: "RESET" });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <section
      className="card"
      aria-labelledby="scanner-heading"
      style={{
        marginBottom: "1.5rem",
        backgroundColor: "#fdfefe",
        border: "1px dashed #94a3b8",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <h3
          id="scanner-heading"
          style={{ fontSize: "1.15rem", margin: 0, color: "var(--color-primary)" }}
        >
          Scan Label Photograph (Local Offline OCR)
        </h3>
        <span
          style={{
            fontSize: "0.75rem",
            backgroundColor: "#e2e8f0",
            padding: "0.2rem 0.5rem",
            borderRadius: "4px",
          }}
        >
          Phase 3A
        </span>
      </div>

      <p
        style={{
          fontSize: "0.85rem",
          color: "var(--color-text-muted)",
          marginTop: "0.25rem",
          marginBottom: "1rem",
        }}
      >
        Upload or capture a clear photo of the food packaging nutrition panel and ingredients list.
        Images are processed locally in memory and never stored permanently.
      </p>

      {/* Upload Controls */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.75rem" }}>
        <label
          htmlFor="labelFileInput"
          className="btn-retry"
          style={{
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            backgroundColor: "#f1f5f9",
          }}
        >
          📷 Select or Capture Image
        </label>
        <input
          id="labelFileInput"
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          onClick={(e) => {
            // Clearing value on click ensures selecting the exact same file fires onChange reliably
            (e.currentTarget as HTMLInputElement).value = "";
          }}
          onChange={handleFileChange}
          style={{ display: "none" }}
        />

        {state.selectedFile && (
          <span style={{ fontSize: "0.85rem", color: "#334155" }}>
            <strong>{state.selectedFile.name}</strong> ({(state.selectedFile.size / 1024).toFixed(0)}{" "}
            KB)
          </span>
        )}

        {state.selectedFile && (
          <button
            type="button"
            onClick={handleExtract}
            disabled={state.uploading}
            className="btn-retry"
            style={{
              backgroundColor: "var(--color-primary)",
              color: "#ffffff",
              fontWeight: 600,
            }}
          >
            {state.uploading ? "Extracting Locally..." : "Extract Text (Offline OCR)"}
          </button>
        )}

        {state.selectedFile && (
          <button
            type="button"
            onClick={handleResetScanner}
            disabled={state.uploading}
            className="btn-retry"
            style={{ fontSize: "0.8rem" }}
          >
            Clear Image
          </button>
        )}
      </div>

      {/* Error Banner */}
      {state.error && (
        <div
          role="alert"
          style={{
            marginTop: "1rem",
            padding: "0.75rem",
            backgroundColor: "var(--color-offline-bg)",
            color: "var(--color-offline-text)",
            borderRadius: "6px",
            fontSize: "0.875rem",
          }}
        >
          <strong>Extraction Error:</strong> {state.error}
        </div>
      )}

      {/* Image Preview */}
      {state.previewUrl && (
        <div style={{ marginTop: "1rem", maxWidth: "320px" }}>
          <span
            style={{
              fontSize: "0.75rem",
              color: "var(--color-text-muted)",
              display: "block",
              marginBottom: "0.25rem",
            }}
          >
            Image Preview:
          </span>
          <img
            src={state.previewUrl}
            alt="Preview of uploaded food package label"
            style={{
              width: "100%",
              maxHeight: "220px",
              objectFit: "contain",
              border: "1px solid var(--color-border)",
              borderRadius: "6px",
              backgroundColor: "#ffffff",
            }}
          />
        </div>
      )}

      {/* Interactive Review & Verification Section */}
      {state.ocrResult && (
        <div
          style={{
            marginTop: "1.25rem",
            padding: "1rem",
            backgroundColor: "#f8fafc",
            border: "1px solid #cbd5e1",
            borderRadius: "8px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              flexWrap: "wrap",
              gap: "0.5rem",
            }}
          >
            <h4 style={{ margin: 0, fontSize: "1rem" }}>Review &amp; Verify Extracted Values</h4>
            {state.ocrResult.overall_confidence !== null && (
              <span className="status-pill status-loading" style={{ fontSize: "0.75rem" }}>
                OCR Confidence: {state.ocrResult.overall_confidence}%
              </span>
            )}
          </div>

          <div
            style={{
              marginTop: "0.5rem",
              marginBottom: "1rem",
              padding: "0.5rem 0.75rem",
              backgroundColor: "var(--color-warning-bg)",
              color: "var(--color-warning-text)",
              borderRadius: "4px",
              fontSize: "0.8rem",
            }}
          >
            <strong>Mandatory Review:</strong> OCR extraction is a draft suggestion. Package folds,
            reflections, or small fonts can cause errors. Review and edit all fields below before
            transferring into the analysis form.
          </div>

          {/* Warnings List */}
          {state.ocrResult.warnings.length > 0 && (
            <div style={{ marginBottom: "1rem", fontSize: "0.8rem", color: "#64748b" }}>
              <strong>Notices:</strong>
              <ul style={{ paddingLeft: "1.25rem", marginTop: "0.25rem" }}>
                {state.ocrResult.warnings.map((w, idx) => (
                  <li key={w.code + idx}>{w.message}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Editable Draft Fields */}
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>
                  Serving Size:
                </label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.servingSize}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "servingSize",
                      value: e.target.value,
                    })
                  }
                  placeholder="e.g. 30"
                  style={{
                    width: "100%",
                    padding: "0.35rem 0.5rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem" }}>Unit:</label>
                <select
                  value={state.reviewFields.servingUnit}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "servingUnit",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.35rem 0.5rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <option value="g">Grams (g)</option>
                  <option value="ml">Millilitres (ml)</option>
                  <option value="piece">Piece</option>
                  <option value="portion">Portion</option>
                </select>
              </div>
            </div>

            {/* Nutrients Grid */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
                gap: "0.5rem",
              }}
            >
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Energy (kcal)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.energyKcal}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "energyKcal",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Protein (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.proteinG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "proteinG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Carbs (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.carbohydratesG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "carbohydratesG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Total Sugar (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.totalSugarG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "totalSugarG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Added Sugar (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.addedSugarG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "addedSugarG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Fiber (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.dietaryFiberG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "dietaryFiberG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Total Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.totalFatG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "totalFatG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Sat. Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.saturatedFatG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "saturatedFatG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Trans Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.transFatG}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "transFatG",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Sodium (mg)</label>
                <input
                  type="number"
                  step="any"
                  value={state.reviewFields.sodiumMg}
                  onChange={(e) =>
                    dispatch({
                      type: "FIELD_UPDATED",
                      field: "sodiumMg",
                      value: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "0.25rem 0.4rem",
                    borderRadius: "4px",
                    border: "1px solid var(--color-border)",
                  }}
                />
              </div>
            </div>

            {/* Ingredients Field */}
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  marginBottom: "0.25rem",
                }}
              >
                Ingredients Declaration Statement:
              </label>
              <textarea
                rows={2}
                value={state.reviewFields.ingredientsText}
                onChange={(e) =>
                  dispatch({
                    type: "FIELD_UPDATED",
                    field: "ingredientsText",
                    value: e.target.value,
                  })
                }
                placeholder="Ingredients text detected from packaging..."
                style={{
                  width: "100%",
                  padding: "0.4rem",
                  borderRadius: "4px",
                  border: "1px solid var(--color-border)",
                  fontSize: "0.8rem",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Action to Transfer to Form */}
            <div
              style={{
                marginTop: "0.5rem",
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={handleTransfer}
                className="btn-retry"
                style={{
                  padding: "0.5rem 1rem",
                  backgroundColor: "var(--color-primary)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "0.875rem",
                }}
              >
                ✓ Transfer Verified Values to Analysis Form
              </button>

              {state.transferred && (
                <span
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--color-success-text)",
                    fontWeight: 500,
                  }}
                >
                  Values transferred into analysis form below!
                </span>
              )}
            </div>

            {/* Collapsible Raw Text Reference */}
            <details style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#64748b" }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                View Raw Unprocessed OCR Text
              </summary>
              <pre
                style={{
                  marginTop: "0.25rem",
                  padding: "0.5rem",
                  backgroundColor: "#ffffff",
                  border: "1px solid var(--color-border)",
                  borderRadius: "4px",
                  whiteSpace: "pre-wrap",
                  fontFamily: "monospace",
                  fontSize: "0.75rem",
                  maxHeight: "150px",
                  overflowY: "auto",
                }}
              >
                {state.ocrResult.raw_text}
              </pre>
            </details>
          </div>
        </div>
      )}
    </section>
  );
};
