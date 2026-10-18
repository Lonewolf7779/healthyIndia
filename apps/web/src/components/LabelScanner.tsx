"use client";

import React, { useState, useRef } from "react";
import { apiClient, OcrExtractionResponse } from "../lib/api/client";

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

interface LabelScannerProps {
  onTransferValues: (values: TransferredValues) => void;
}

export const LabelScanner: React.FC<LabelScannerProps> = ({ onTransferValues }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [ocrResult, setOcrResult] = useState<OcrExtractionResponse | null>(null);
  const [transferred, setTransferred] = useState<boolean>(false);

  // Editable review fields
  const [reviewServingSize, setReviewServingSize] = useState<string>("");
  const [reviewServingUnit, setReviewServingUnit] = useState<"g" | "ml" | "piece" | "portion">("g");
  const [reviewEnergyKcal, setReviewEnergyKcal] = useState<string>("");
  const [reviewProteinG, setReviewProteinG] = useState<string>("");
  const [reviewCarbsG, setReviewCarbsG] = useState<string>("");
  const [reviewTotalSugarG, setReviewTotalSugarG] = useState<string>("");
  const [reviewAddedSugarG, setReviewAddedSugarG] = useState<string>("");
  const [reviewFiberG, setReviewFiberG] = useState<string>("");
  const [reviewTotalFatG, setReviewTotalFatG] = useState<string>("");
  const [reviewSatFatG, setReviewSatFatG] = useState<string>("");
  const [reviewTransFatG, setReviewTransFatG] = useState<string>("");
  const [reviewCholesterolMg, setReviewCholesterolMg] = useState<string>("");
  const [reviewSodiumMg, setReviewSodiumMg] = useState<string>("");
  const [reviewIngredientsText, setReviewIngredientsText] = useState<string>("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setOcrResult(null);
    setTransferred(false);

    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    // Client-side quick check
    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) {
      setError("Please select a supported image file (JPEG, PNG, or WEBP).");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("Image file size exceeds the maximum limit of 10 MB.");
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
  };

  const handleExtract = async () => {
    if (!selectedFile) {
      setError("Please select or capture a label image first.");
      return;
    }

    setUploading(true);
    setError(null);
    setTransferred(false);

    try {
      const data = await apiClient.extractOcr(selectedFile);
      setOcrResult(data);

      // Pre-fill review form with candidate values
      setReviewServingSize(
        data.serving_size_candidate !== null && data.serving_size_candidate !== undefined
          ? String(data.serving_size_candidate)
          : ""
      );
      setReviewServingUnit(
        data.serving_unit_candidate === "ml"
          ? "ml"
          : data.serving_unit_candidate === "piece"
          ? "piece"
          : data.serving_unit_candidate === "portion"
          ? "portion"
          : "g"
      );

      const c = data.nutrient_candidates;
      setReviewEnergyKcal(c.energy_kcal?.value !== undefined && c.energy_kcal?.value !== null ? String(c.energy_kcal.value) : "");
      setReviewProteinG(c.protein_g?.value !== undefined && c.protein_g?.value !== null ? String(c.protein_g.value) : "");
      setReviewCarbsG(c.carbohydrates_g?.value !== undefined && c.carbohydrates_g?.value !== null ? String(c.carbohydrates_g.value) : "");
      setReviewTotalSugarG(c.total_sugar_g?.value !== undefined && c.total_sugar_g?.value !== null ? String(c.total_sugar_g.value) : "");
      setReviewAddedSugarG(c.added_sugar_g?.value !== undefined && c.added_sugar_g?.value !== null ? String(c.added_sugar_g.value) : "");
      setReviewFiberG(c.dietary_fiber_g?.value !== undefined && c.dietary_fiber_g?.value !== null ? String(c.dietary_fiber_g.value) : "");
      setReviewTotalFatG(c.total_fat_g?.value !== undefined && c.total_fat_g?.value !== null ? String(c.total_fat_g.value) : "");
      setReviewSatFatG(c.saturated_fat_g?.value !== undefined && c.saturated_fat_g?.value !== null ? String(c.saturated_fat_g.value) : "");
      setReviewTransFatG(c.trans_fat_g?.value !== undefined && c.trans_fat_g?.value !== null ? String(c.trans_fat_g.value) : "");
      setReviewCholesterolMg(c.cholesterol_mg?.value !== undefined && c.cholesterol_mg?.value !== null ? String(c.cholesterol_mg.value) : "");
      setReviewSodiumMg(c.sodium_mg?.value !== undefined && c.sodium_mg?.value !== null ? String(c.sodium_mg.value) : "");
      setReviewIngredientsText(data.ingredients_text || "");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("OCR text extraction failed. Please try a clearer photograph or enter values manually.");
      }
    } finally {
      setUploading(false);
    }
  };

  const handleTransfer = () => {
    onTransferValues({
      servingSize: reviewServingSize,
      servingUnit: reviewServingUnit,
      energyKcal: reviewEnergyKcal,
      proteinG: reviewProteinG,
      carbohydratesG: reviewCarbsG,
      totalSugarG: reviewTotalSugarG,
      addedSugarG: reviewAddedSugarG,
      dietaryFiberG: reviewFiberG,
      totalFatG: reviewTotalFatG,
      saturatedFatG: reviewSatFatG,
      transFatG: reviewTransFatG,
      cholesterolMg: reviewCholesterolMg,
      sodiumMg: reviewSodiumMg,
      ingredientsText: reviewIngredientsText,
    });
    setTransferred(true);
  };

  const handleResetScanner = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setOcrResult(null);
    setError(null);
    setTransferred(false);
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" }}>
        <h3 id="scanner-heading" style={{ fontSize: "1.15rem", margin: 0, color: "var(--color-primary)" }}>
          Scan Label Photograph (Local Offline OCR)
        </h3>
        <span style={{ fontSize: "0.75rem", backgroundColor: "#e2e8f0", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
          Phase 3A
        </span>
      </div>

      <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", marginTop: "0.25rem", marginBottom: "1rem" }}>
        Upload or capture a clear photo of the food packaging nutrition panel and ingredients list. Images are processed locally in memory and never stored permanently.
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
          onChange={handleFileChange}
          style={{ display: "none" }}
        />

        {selectedFile && (
          <span style={{ fontSize: "0.85rem", color: "#334155" }}>
            <strong>{selectedFile.name}</strong> ({(selectedFile.size / 1024).toFixed(0)} KB)
          </span>
        )}

        {selectedFile && (
          <button
            type="button"
            onClick={handleExtract}
            disabled={uploading}
            className="btn-retry"
            style={{
              backgroundColor: "var(--color-primary)",
              color: "#ffffff",
              fontWeight: 600,
            }}
          >
            {uploading ? "Extracting Locally..." : "Extract Text (Offline OCR)"}
          </button>
        )}

        {selectedFile && (
          <button
            type="button"
            onClick={handleResetScanner}
            disabled={uploading}
            className="btn-retry"
            style={{ fontSize: "0.8rem" }}
          >
            Clear Image
          </button>
        )}
      </div>

      {/* Error Banner */}
      {error && (
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
          <strong>Extraction Error:</strong> {error}
        </div>
      )}

      {/* Image Preview */}
      {previewUrl && (
        <div style={{ marginTop: "1rem", maxWidth: "320px" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", display: "block", marginBottom: "0.25rem" }}>
            Image Preview:
          </span>
          <img
            src={previewUrl}
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
      {ocrResult && (
        <div
          style={{
            marginTop: "1.25rem",
            padding: "1rem",
            backgroundColor: "#f8fafc",
            border: "1px solid #cbd5e1",
            borderRadius: "8px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" }}>
            <h4 style={{ margin: 0, fontSize: "1rem" }}>Review &amp; Verify Extracted Values</h4>
            {ocrResult.overall_confidence !== null && (
              <span className="status-pill status-loading" style={{ fontSize: "0.75rem" }}>
                OCR Confidence: {ocrResult.overall_confidence}%
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
            <strong>Mandatory Review:</strong> OCR extraction is a draft suggestion. Package folds, reflections, or small fonts can cause errors. Review and edit all fields below before transferring into the analysis form.
          </div>

          {/* Warnings List */}
          {ocrResult.warnings.length > 0 && (
            <div style={{ marginBottom: "1rem", fontSize: "0.8rem", color: "#64748b" }}>
              <strong>Notices:</strong>
              <ul style={{ paddingLeft: "1.25rem", marginTop: "0.25rem" }}>
                {ocrResult.warnings.map((w, idx) => (
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
                  value={reviewServingSize}
                  onChange={(e) => setReviewServingSize(e.target.value)}
                  placeholder="e.g. 30"
                  style={{ width: "100%", padding: "0.35rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem" }}>Unit:</label>
                <select
                  value={reviewServingUnit}
                  onChange={(e) => setReviewServingUnit(e.target.value as "g" | "ml" | "piece" | "portion")}
                  style={{ width: "100%", padding: "0.35rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                >
                  <option value="g">Grams (g)</option>
                  <option value="ml">Millilitres (ml)</option>
                  <option value="piece">Piece</option>
                  <option value="portion">Portion</option>
                </select>
              </div>
            </div>

            {/* Nutrients Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "0.5rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Energy (kcal)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewEnergyKcal}
                  onChange={(e) => setReviewEnergyKcal(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Protein (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewProteinG}
                  onChange={(e) => setReviewProteinG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Carbs (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewCarbsG}
                  onChange={(e) => setReviewCarbsG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Total Sugar (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewTotalSugarG}
                  onChange={(e) => setReviewTotalSugarG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Added Sugar (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewAddedSugarG}
                  onChange={(e) => setReviewAddedSugarG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Fiber (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewFiberG}
                  onChange={(e) => setReviewFiberG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Total Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewTotalFatG}
                  onChange={(e) => setReviewTotalFatG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Sat. Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewSatFatG}
                  onChange={(e) => setReviewSatFatG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Trans Fat (g)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewTransFatG}
                  onChange={(e) => setReviewTransFatG(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem" }}>Sodium (mg)</label>
                <input
                  type="number"
                  step="any"
                  value={reviewSodiumMg}
                  onChange={(e) => setReviewSodiumMg(e.target.value)}
                  style={{ width: "100%", padding: "0.25rem 0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
            </div>

            {/* Ingredients Field */}
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                Ingredients Declaration Statement:
              </label>
              <textarea
                rows={2}
                value={reviewIngredientsText}
                onChange={(e) => setReviewIngredientsText(e.target.value)}
                placeholder="Ingredients text detected from packaging..."
                style={{ width: "100%", padding: "0.4rem", borderRadius: "4px", border: "1px solid var(--color-border)", fontSize: "0.8rem", fontFamily: "inherit" }}
              />
            </div>

            {/* Action to Transfer to Form */}
            <div style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
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

              {transferred && (
                <span style={{ fontSize: "0.85rem", color: "var(--color-success-text)", fontWeight: 500 }}>
                  Values transferred into analysis form below!
                </span>
              )}
            </div>

            {/* Collapsible Raw Text Reference */}
            <details style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#64748b" }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>View Raw Unprocessed OCR Text</summary>
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
                {ocrResult.raw_text}
              </pre>
            </details>
          </div>
        </div>
      )}
    </section>
  );
};
