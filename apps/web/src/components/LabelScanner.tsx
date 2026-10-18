"use client";

import React, { useRef, useEffect, useReducer } from "react";
import { apiClient, OcrExtractionResponse } from "../lib/api/client";

export const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
export const SUPPORTED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];

export interface TransferredValues {
  servingSize?: string;
  servingUnit?: "g" | "ml" | "kg" | "l" | "piece" | "portion";
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
  isConfirmed?: boolean;
  unconfirmedCount?: number;
  basis?: "per_serving" | "per_100g" | "per_100ml";
}

export interface LabelScannerReviewFields {
  servingSize: string;
  servingUnit: "g" | "ml" | "kg" | "l" | "piece" | "portion";
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

export const initialConfirmedFields: Record<keyof LabelScannerReviewFields, boolean> = {
  servingSize: false,
  servingUnit: false,
  energyKcal: false,
  proteinG: false,
  carbohydratesG: false,
  totalSugarG: false,
  addedSugarG: false,
  dietaryFiberG: false,
  totalFatG: false,
  saturatedFatG: false,
  transFatG: false,
  cholesterolMg: false,
  sodiumMg: false,
  ingredientsText: false,
};

export interface ScannerState {
  selectedFile: File | null;
  previewUrl: string | null;
  uploading: boolean;
  error: string | null;
  ocrResult: OcrExtractionResponse | null;
  transferred: boolean;
  reviewFields: LabelScannerReviewFields;
  confirmedFields: Record<keyof LabelScannerReviewFields, boolean>;
  selectedColumn: "per_serving" | "per_100";
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
  | { type: "FIELD_CONFIRMED"; field: keyof LabelScannerReviewFields; confirmed: boolean }
  | { type: "ALL_FIELDS_CONFIRMED" }
  | { type: "COLUMN_BASIS_SELECTED"; basis: "per_serving" | "per_100" }
  | { type: "RESET" };

export const initialScannerState: ScannerState = {
  selectedFile: null,
  previewUrl: null,
  uploading: false,
  error: null,
  ocrResult: null,
  transferred: false,
  reviewFields: initialReviewFields,
  confirmedFields: initialConfirmedFields,
  selectedColumn: "per_serving",
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
  data: OcrExtractionResponse,
  columnBasis: "per_serving" | "per_100" = "per_serving"
): LabelScannerReviewFields {
  let c = data.nutrient_candidates || {};

  // If dual column was detected and user requested per_100 specifically
  if (columnBasis === "per_100" && data.per_100_candidates && Object.keys(data.per_100_candidates).length > 0) {
    c = data.per_100_candidates;
  } else if (columnBasis === "per_serving" && data.per_serving_candidates && Object.keys(data.per_serving_candidates).length > 0) {
    c = data.per_serving_candidates;
  }

  return {
    servingSize:
      data.serving_size_candidate !== null && data.serving_size_candidate !== undefined
        ? String(data.serving_size_candidate)
        : "",
    servingUnit:
      data.serving_unit_candidate === "ml"
        ? "ml"
        : data.serving_unit_candidate === "kg"
        ? "kg"
        : data.serving_unit_candidate === "l"
        ? "l"
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
        confirmedFields: initialConfirmedFields,
        selectedColumn: "per_serving",
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
        confirmedFields: initialConfirmedFields,
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
        confirmedFields: initialConfirmedFields,
      };

    case "EXTRACTION_STARTED":
      return {
        ...state,
        uploading: true,
        error: null,
        transferred: false,
      };

    case "EXTRACTION_SUCCESS": {
      const defaultBasis =
        action.data.column_basis_detected === "per_100g" ? "per_100" : "per_serving";
      return {
        ...state,
        uploading: false,
        error: null,
        ocrResult: action.data,
        transferred: false,
        selectedColumn: defaultBasis,
        reviewFields: buildReviewFieldsFromOcr(action.data, defaultBasis),
        confirmedFields: initialConfirmedFields,
      };
    }

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
        confirmedFields: {
          ...state.confirmedFields,
          [action.field]: false, // Editing a value invalidates any previous confirmation associated with it
        },
      };

    case "FIELD_CONFIRMED":
      return {
        ...state,
        confirmedFields: {
          ...state.confirmedFields,
          [action.field]: action.confirmed,
        },
      };

    case "ALL_FIELDS_CONFIRMED": {
      const allConfirmed: Record<keyof LabelScannerReviewFields, boolean> = {
        servingSize: true,
        servingUnit: true,
        energyKcal: true,
        proteinG: true,
        carbohydratesG: true,
        totalSugarG: true,
        addedSugarG: true,
        dietaryFiberG: true,
        totalFatG: true,
        saturatedFatG: true,
        transFatG: true,
        cholesterolMg: true,
        sodiumMg: true,
        ingredientsText: true,
      };
      return {
        ...state,
        confirmedFields: allConfirmed,
      };
    }

    case "COLUMN_BASIS_SELECTED":
      if (!state.ocrResult) return state;
      return {
        ...state,
        selectedColumn: action.basis,
        reviewFields: buildReviewFieldsFromOcr(state.ocrResult, action.basis),
        confirmedFields: initialConfirmedFields, // Switching calculation basis invalidates previous confirmations
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
    activeRequestIdRef.current++;
    const file = e.target.files?.[0];

    if (!file) {
      cleanupCurrentPreview();
      dispatch({ type: "FILE_CLEARED" });
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const validation = validateImageFile(file);
    if (!validation.valid) {
      cleanupCurrentPreview();
      dispatch({ type: "FILE_REJECTED", error: validation.error! });
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    cleanupCurrentPreview();
    const newPreviewUrl = URL.createObjectURL(file);
    previewUrlRef.current = newPreviewUrl;

    dispatch({ type: "FILE_SELECTED", file, previewUrl: newPreviewUrl });
  };

  const handleExtract = async () => {
    if (state.uploading || !state.selectedFile) return;

    const requestId = ++activeRequestIdRef.current;
    dispatch({ type: "EXTRACTION_STARTED" });

    try {
      const data = await apiClient.extractOcr(state.selectedFile);
      if (activeRequestIdRef.current === requestId) {
        dispatch({ type: "EXTRACTION_SUCCESS", data });
      }
    } catch (err: unknown) {
      if (activeRequestIdRef.current === requestId) {
        const message =
          err instanceof Error
            ? err.message
            : "OCR text extraction failed. Please try a clearer photograph or enter values manually.";
        dispatch({ type: "EXTRACTION_FAILURE", error: message });
      }
    }
  };

  // Count active non-empty fields and their confirmation status
  const activeFields = (
    Object.keys(state.reviewFields) as Array<keyof LabelScannerReviewFields>
  ).filter((k) => state.reviewFields[k] !== "");

  const unconfirmedCount = activeFields.filter((k) => !state.confirmedFields[k]).length;
  const isAllConfirmed = unconfirmedCount === 0 && activeFields.length > 0;

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
      isConfirmed: isAllConfirmed,
      unconfirmedCount,
      basis: state.selectedColumn === "per_100" ? "per_100g" : "per_serving",
    });
    dispatch({ type: "VALUES_TRANSFERRED" });
  };

  const handleResetScanner = () => {
    activeRequestIdRef.current++;
    cleanupCurrentPreview();
    dispatch({ type: "RESET" });
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const q = state.ocrResult?.image_quality;

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
          Scan Food Label (High-Reliability Local OCR)
        </h3>
        <span
          style={{
            fontSize: "0.75rem",
            backgroundColor: "#e2e8f0",
            padding: "0.2rem 0.5rem",
            borderRadius: "4px",
          }}
        >
          Phase 3A Deterministic OCR
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
        Upload or capture a photograph of the nutritional panel and ingredient list.
        All values are processed locally in memory with OpenCV quality gates, multi-pass
        discrepancy detection, and physical plausibility validation.
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
            (e.currentTarget as HTMLInputElement).value = "";
          }}
          onChange={handleFileChange}
          style={{ display: "none" }}
        />

        {state.selectedFile && (
          <span style={{ fontSize: "0.85rem", color: "#334155" }}>
            <strong>{state.selectedFile.name}</strong> ({(state.selectedFile.size / 1024).toFixed(0)} KB)
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
            {state.uploading ? "Analyzing & Extracting..." : "Run Local OCR & Quality Gates"}
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
          {/* Quality Gates Badge & Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              flexWrap: "wrap",
              gap: "0.5rem",
              marginBottom: "0.5rem",
            }}
          >
            <h4 style={{ margin: 0, fontSize: "1.05rem" }}>
              Strict Review &amp; Confirmation Checklist
            </h4>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              {q && (
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    padding: "0.2rem 0.5rem",
                    borderRadius: "4px",
                    backgroundColor:
                      q.grade === "good" ? "#dcfce7" : q.grade === "fair" ? "#fef3c7" : "#fee2e2",
                    color:
                      q.grade === "good" ? "#166534" : q.grade === "fair" ? "#92400e" : "#991b1b",
                  }}
                >
                  CV Quality: {q.gate_outcome || q.grade.toUpperCase()} ({q.metrics.sharpness_score >= 100 ? "Sharp" : "Soft Focus"})
                </span>
              )}
              {state.ocrResult.overall_confidence !== null && (
                <span className="status-pill status-loading" style={{ fontSize: "0.75rem" }}>
                  OCR Confidence: {state.ocrResult.overall_confidence}%
                </span>
              )}
            </div>
          </div>

          {/* Computer Vision Quality Disclaimer */}
          {q && (
            <div
              style={{
                fontSize: "0.75rem",
                color: "#475569",
                marginBottom: "0.75rem",
                padding: "0.4rem 0.6rem",
                backgroundColor: "#f1f5f9",
                borderRadius: "4px",
                borderLeft: "3px solid #64748b",
              }}
            >
              <strong>Quality Gate Metrics:</strong> Sharpness {q.metrics.sharpness_score} · Glare {(q.metrics.glare_ratio * 100).toFixed(1)}% · Skew {q.metrics.estimated_skew_degrees}° · {q.metrics.width}x{q.metrics.height}px.
              <span style={{ display: "block", marginTop: "0.2rem", fontStyle: "italic" }}>
                {q.disclaimer}
              </span>
            </div>
          )}

          {/* Dual Pass Discrepancy Alert */}
          {state.ocrResult.pass_discrepancy && (
            <div
              style={{
                marginBottom: "0.75rem",
                padding: "0.6rem 0.75rem",
                backgroundColor: "#fff7ed",
                color: "#9a3412",
                border: "1px solid #fed7aa",
                borderRadius: "6px",
                fontSize: "0.8rem",
              }}
            >
              <strong>⚠️ Dual-Pass Discrepancy Detected:</strong> Contrast normalization and binarization passes produced differing readings. Please carefully verify each highlighted number against the packaging photo.
            </div>
          )}

          {/* Multi-column Selection Tabs */}
          {state.ocrResult.column_basis_detected === "dual_column" && (
            <div
              style={{
                display: "flex",
                gap: "0.5rem",
                alignItems: "center",
                marginBottom: "0.75rem",
                padding: "0.5rem",
                backgroundColor: "#e2e8f0",
                borderRadius: "6px",
              }}
            >
              <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>Detected Columns:</span>
              <button
                type="button"
                onClick={() => dispatch({ type: "COLUMN_BASIS_SELECTED", basis: "per_serving" })}
                style={{
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  borderRadius: "4px",
                  border: "none",
                  cursor: "pointer",
                  backgroundColor: state.selectedColumn === "per_serving" ? "var(--color-primary)" : "#ffffff",
                  color: state.selectedColumn === "per_serving" ? "#ffffff" : "#334155",
                }}
              >
                Per Serving Column
              </button>
              <button
                type="button"
                onClick={() => dispatch({ type: "COLUMN_BASIS_SELECTED", basis: "per_100" })}
                style={{
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  borderRadius: "4px",
                  border: "none",
                  cursor: "pointer",
                  backgroundColor: state.selectedColumn === "per_100" ? "var(--color-primary)" : "#ffffff",
                  color: state.selectedColumn === "per_100" ? "#ffffff" : "#334155",
                }}
              >
                Per 100g Column
              </button>
            </div>
          )}

          {/* Warnings List */}
          {state.ocrResult.warnings.length > 0 && (
            <div style={{ marginBottom: "1rem", fontSize: "0.8rem", color: "#64748b" }}>
              <strong>Notices &amp; Plausibility Checks:</strong>
              <ul style={{ paddingLeft: "1.25rem", marginTop: "0.25rem", marginBottom: 0 }}>
                {state.ocrResult.warnings.map((w, idx) => (
                  <li key={w.code + idx} style={{ color: w.code.startsWith("PLAUSIBILITY_") ? "#b91c1c" : "inherit" }}>
                    {w.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Quick Confirmation Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.5rem",
              padding: "0.5rem 0.75rem",
              backgroundColor: isAllConfirmed ? "#f0fdf4" : "#fffbeb",
              border: `1px solid ${isAllConfirmed ? "#86efac" : "#fde68a"}`,
              borderRadius: "6px",
              marginBottom: "1rem",
            }}
          >
            <span style={{ fontSize: "0.825rem", color: isAllConfirmed ? "#166534" : "#92400e" }}>
              {isAllConfirmed ? (
                <strong>✓ All active fields confirmed by user! Ready for analysis.</strong>
              ) : (
                <span>
                  <strong>Confirmation Required:</strong> {unconfirmedCount} unverified field(s). Review each field below or confirm all once verified.
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={() => dispatch({ type: "ALL_FIELDS_CONFIRMED" })}
              className="btn-retry"
              style={{
                fontSize: "0.75rem",
                padding: "0.3rem 0.6rem",
                backgroundColor: "#ffffff",
                border: "1px solid #cbd5e1",
              }}
            >
              ✓ Confirm All Extracted Values
            </button>
          </div>

          {/* Detailed Verification Grid */}
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {/* Serving Size & Unit Row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "0.75rem",
                padding: "0.5rem",
                backgroundColor: "#ffffff",
                borderRadius: "6px",
                border: "1px solid #e2e8f0",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>Serving Size:</label>
                  <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={state.confirmedFields.servingSize}
                      onChange={(e) =>
                        dispatch({
                          type: "FIELD_CONFIRMED",
                          field: "servingSize",
                          confirmed: e.target.checked,
                        })
                      }
                    />
                    Confirmed
                  </label>
                </div>
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
                    border: state.confirmedFields.servingSize
                      ? "1px solid #22c55e"
                      : "1px solid #e2e8f0",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>
                  Serving Unit:
                </label>
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
                    border: "1px solid #e2e8f0",
                  }}
                >
                  <option value="g">Grams (g)</option>
                  <option value="kg">Kilograms (kg)</option>
                  <option value="ml">Millilitres (ml)</option>
                  <option value="l">Litres (l)</option>
                  <option value="piece">Piece</option>
                  <option value="portion">Portion</option>
                </select>
              </div>
            </div>

            {/* Nutrients Checklist */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                gap: "0.6rem",
              }}
            >
              {[
                { field: "energyKcal" as const, label: "Energy (kcal)", cand: state.ocrResult.nutrient_candidates.energy_kcal },
                { field: "proteinG" as const, label: "Protein (g)", cand: state.ocrResult.nutrient_candidates.protein_g },
                { field: "carbohydratesG" as const, label: "Carbs (g)", cand: state.ocrResult.nutrient_candidates.carbohydrates_g },
                { field: "totalSugarG" as const, label: "Total Sugar (g)", cand: state.ocrResult.nutrient_candidates.total_sugar_g },
                { field: "addedSugarG" as const, label: "Added Sugar (g)", cand: state.ocrResult.nutrient_candidates.added_sugar_g },
                { field: "dietaryFiberG" as const, label: "Fiber (g)", cand: state.ocrResult.nutrient_candidates.dietary_fiber_g },
                { field: "totalFatG" as const, label: "Total Fat (g)", cand: state.ocrResult.nutrient_candidates.total_fat_g },
                { field: "saturatedFatG" as const, label: "Sat. Fat (g)", cand: state.ocrResult.nutrient_candidates.saturated_fat_g },
                { field: "transFatG" as const, label: "Trans Fat (g)", cand: state.ocrResult.nutrient_candidates.trans_fat_g },
                { field: "cholesterolMg" as const, label: "Cholesterol (mg)", cand: state.ocrResult.nutrient_candidates.cholesterol_mg },
                { field: "sodiumMg" as const, label: "Sodium (mg)", cand: state.ocrResult.nutrient_candidates.sodium_mg },
              ].map(({ field, label, cand }) => {
                const isConfirmed = state.confirmedFields[field];
                const plausibility = cand?.plausibility || "plausible";
                const plausWarn = cand?.plausibility_warning;

                return (
                  <div
                    key={field}
                    style={{
                      padding: "0.45rem",
                      backgroundColor: "#ffffff",
                      borderRadius: "6px",
                      border:
                        plausibility === "contradictory"
                          ? "1px solid #ef4444"
                          : isConfirmed
                          ? "1px solid #86efac"
                          : "1px solid #e2e8f0",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "0.2rem",
                      }}
                    >
                      <span style={{ fontSize: "0.75rem", fontWeight: 600 }}>{label}</span>
                      <label
                        style={{
                          fontSize: "0.7rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.2rem",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isConfirmed}
                          onChange={(e) =>
                            dispatch({
                              type: "FIELD_CONFIRMED",
                              field,
                              confirmed: e.target.checked,
                            })
                          }
                        />
                        ✓
                      </label>
                    </div>

                    <input
                      type="number"
                      step="any"
                      value={state.reviewFields[field]}
                      onChange={(e) =>
                        dispatch({
                          type: "FIELD_UPDATED",
                          field,
                          value: e.target.value,
                        })
                      }
                      style={{
                        width: "100%",
                        padding: "0.25rem 0.4rem",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "0.85rem",
                      }}
                    />

                    {/* Raw OCR snippet */}
                    {cand?.raw_text && (
                      <span
                        style={{
                          display: "block",
                          fontSize: "0.65rem",
                          color: "#64748b",
                          marginTop: "0.2rem",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                        title={`OCR matched: "${cand.raw_text}"`}
                      >
                        OCR: &quot;{cand.raw_text}&quot;
                      </span>
                    )}

                    {/* Plausibility Warning Badge */}
                    {plausWarn && (
                      <span
                        style={{
                          display: "block",
                          fontSize: "0.65rem",
                          color: "#b91c1c",
                          marginTop: "0.15rem",
                        }}
                      >
                        ⚠️ {plausWarn}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Ingredients Declaration Text */}
            <div
              style={{
                padding: "0.5rem",
                backgroundColor: "#ffffff",
                borderRadius: "6px",
                border: "1px solid #e2e8f0",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.25rem",
                }}
              >
                <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                  Ingredients Statement:
                </label>
                <label
                  style={{
                    fontSize: "0.75rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.25rem",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={state.confirmedFields.ingredientsText}
                    onChange={(e) =>
                      dispatch({
                        type: "FIELD_CONFIRMED",
                        field: "ingredientsText",
                        confirmed: e.target.checked,
                      })
                    }
                  />
                  Confirmed
                </label>
              </div>
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
                  border: "1px solid #cbd5e1",
                  fontSize: "0.8rem",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Transfer Action */}
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
                  padding: "0.55rem 1.1rem",
                  backgroundColor: isAllConfirmed ? "var(--color-primary)" : "#0f766e",
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

              {!isAllConfirmed && (
                <span style={{ fontSize: "0.75rem", color: "#d97706" }}>
                  ({unconfirmedCount} unconfirmed fields will be transferred as user-verified on submit)
                </span>
              )}
            </div>

            {/* Collapsible Raw Text Reference */}
            <details style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#64748b" }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                View Raw OCR Text &amp; Multi-Pass Details
              </summary>
              <div style={{ marginTop: "0.5rem" }}>
                {state.ocrResult.pass_a_text && (
                  <div style={{ marginBottom: "0.5rem" }}>
                    <strong>Pass A (Normalized CLAHE):</strong>
                    <pre
                      style={{
                        marginTop: "0.2rem",
                        padding: "0.4rem",
                        backgroundColor: "#ffffff",
                        border: "1px solid var(--color-border)",
                        borderRadius: "4px",
                        whiteSpace: "pre-wrap",
                        fontFamily: "monospace",
                        fontSize: "0.7rem",
                        maxHeight: "100px",
                        overflowY: "auto",
                      }}
                    >
                      {state.ocrResult.pass_a_text}
                    </pre>
                  </div>
                )}
                {state.ocrResult.pass_b_text && (
                  <div style={{ marginBottom: "0.5rem" }}>
                    <strong>Pass B (Deskewed Binary):</strong>
                    <pre
                      style={{
                        marginTop: "0.2rem",
                        padding: "0.4rem",
                        backgroundColor: "#ffffff",
                        border: "1px solid var(--color-border)",
                        borderRadius: "4px",
                        whiteSpace: "pre-wrap",
                        fontFamily: "monospace",
                        fontSize: "0.7rem",
                        maxHeight: "100px",
                        overflowY: "auto",
                      }}
                    >
                      {state.ocrResult.pass_b_text}
                    </pre>
                  </div>
                )}
                <div>
                  <strong>Primary Extracted Text:</strong>
                  <pre
                    style={{
                      marginTop: "0.2rem",
                      padding: "0.4rem",
                      backgroundColor: "#ffffff",
                      border: "1px solid var(--color-border)",
                      borderRadius: "4px",
                      whiteSpace: "pre-wrap",
                      fontFamily: "monospace",
                      fontSize: "0.7rem",
                      maxHeight: "120px",
                      overflowY: "auto",
                    }}
                  >
                    {state.ocrResult.raw_text}
                  </pre>
                </div>
              </div>
            </details>
          </div>
        </div>
      )}
    </section>
  );
};
