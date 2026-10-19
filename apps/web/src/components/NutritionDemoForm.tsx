"use client";

import React, { useState, useRef } from "react";
import {
  apiClient,
  NutritionAnalysisRequest,
  NutritionAnalysisResponse,
  IngredientAnalysisRequest,
  IngredientAnalysisResponse,
  computeNutritionValuesHash,
} from "../lib/api/client";
import { LabelScanner, TransferredValues } from "./LabelScanner";

/**
 * Safely parses optional numeric input.
 * Preserves empty strings as null (missing), while preserving "0" as 0.
 */
export function parseOptionalNumber(val: string): number | null {
  const trimmed = val.trim();
  if (trimmed === "") return null;
  const num = Number(trimmed);
  return Number.isNaN(num) ? null : num;
}

export const NutritionDemoForm: React.FC = () => {
  // Product & Serving Information
  const [productName, setProductName] = useState<string>("Sample Packaged Biscuits");
  const [servingSize, setServingSize] = useState<string>("30");
  const [servingUnit, setServingUnit] = useState<"g" | "ml" | "kg" | "l" | "piece" | "portion">("g");
  const [basis, setBasis] = useState<"per_serving" | "per_100g" | "per_100ml">("per_serving");
  const [foodForm, setFoodForm] = useState<"solid" | "liquid">("solid");

  // Nutrition Values (blank = missing, explicitly "0" = zero)
  const [energyKcal, setEnergyKcal] = useState<string>("140");
  const [proteinG, setProteinG] = useState<string>("2.1");
  const [carbohydratesG, setCarbohydratesG] = useState<string>("21");
  const [totalSugarG, setTotalSugarG] = useState<string>("9");
  const [addedSugarG, setAddedSugarG] = useState<string>("7.5");
  const [dietaryFiberG, setDietaryFiberG] = useState<string>("0.8");
  const [totalFatG, setTotalFatG] = useState<string>("6");
  const [saturatedFatG, setSaturatedFatG] = useState<string>("2.8");
  const [transFatG, setTransFatG] = useState<string>("0.05");
  const [cholesterolMg, setCholesterolMg] = useState<string>("");
  const [sodiumMg, setSodiumMg] = useState<string>("180");

  // Ingredients Text
  const [ingredientsText, setIngredientsText] = useState<string>(
    "Refined Wheat Flour (Maida), Palm Oil, Sugar, Salt, Emulsifier (INS 322(i)), " +
      "Raising Agent (INS 500(ii)), Flavour Enhancer (INS 621), Preservative (INS 211)"
  );

  // Interaction State
  const [loading, setLoading] = useState<boolean>(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [nutritionError, setNutritionError] = useState<string | null>(null);
  const [ingredientError, setIngredientError] = useState<string | null>(null);
  const [nutritionResult, setNutritionResult] = useState<NutritionAnalysisResponse | null>(null);
  const [ingredientResult, setIngredientResult] = useState<IngredientAnalysisResponse | null>(null);
  const [activeProductName, setActiveProductName] = useState<string>("");
  const activeRequestIdRef = useRef<number>(0);
  const [ocrProvenance, setOcrProvenance] = useState<{
    isOcr: boolean;
    isConfirmed: boolean;
    unconfirmedCount: number;
    extractionId?: string;
    extractionToken?: string;
    confirmedValuesHash?: string;
  } | null>(null);

  const handleFieldChange = (setter: React.Dispatch<React.SetStateAction<string>>, val: string) => {
    setter(val);
    if (ocrProvenance?.isOcr) {
      setOcrProvenance((prev) =>
        prev
          ? {
              ...prev,
              isConfirmed: false,
              confirmedValuesHash: undefined,
              unconfirmedCount: Math.max(1, prev.unconfirmedCount),
            }
          : null
      );
    }
  };

  const handleServingUnitChange = (val: "g" | "ml" | "kg" | "l" | "piece" | "portion") => {
    setServingUnit(val);
    if (ocrProvenance?.isOcr) {
      setOcrProvenance((prev) =>
        prev
          ? {
              ...prev,
              isConfirmed: false,
              confirmedValuesHash: undefined,
              unconfirmedCount: Math.max(1, prev.unconfirmedCount),
            }
          : null
      );
    }
  };

  const handleBasisChange = (val: "per_serving" | "per_100g" | "per_100ml") => {
    setBasis(val);
    if (ocrProvenance?.isOcr) {
      setOcrProvenance((prev) =>
        prev
          ? {
              ...prev,
              isConfirmed: false,
              confirmedValuesHash: undefined,
              unconfirmedCount: Math.max(1, prev.unconfirmedCount),
            }
          : null
      );
    }
  };

  const handleFoodFormChange = (val: "solid" | "liquid") => {
    setFoodForm(val);
    if (ocrProvenance?.isOcr) {
      setOcrProvenance((prev) =>
        prev
          ? {
              ...prev,
              isConfirmed: false,
              confirmedValuesHash: undefined,
              unconfirmedCount: Math.max(1, prev.unconfirmedCount),
            }
          : null
      );
    }
  };

  const handleConfirmOcrValues = async () => {
    const parsedServing = Number(servingSize) || 100.0;
    const nutrientsMap: Record<string, number | null> = {
      added_sugar_g: parseOptionalNumber(addedSugarG),
      carbohydrates_g: parseOptionalNumber(carbohydratesG),
      cholesterol_mg: parseOptionalNumber(cholesterolMg),
      dietary_fiber_g: parseOptionalNumber(dietaryFiberG),
      energy_kcal: parseOptionalNumber(energyKcal),
      protein_g: parseOptionalNumber(proteinG),
      saturated_fat_g: parseOptionalNumber(saturatedFatG),
      sodium_mg: parseOptionalNumber(sodiumMg),
      total_fat_g: parseOptionalNumber(totalFatG),
      total_sugar_g: parseOptionalNumber(totalSugarG),
      trans_fat_g: parseOptionalNumber(transFatG),
    };

    if (ocrProvenance?.isOcr && ocrProvenance.extractionId && ocrProvenance.extractionToken) {
      try {
        const confRes = await apiClient.confirmOcrValues({
          extraction_id: ocrProvenance.extractionId,
          extraction_token: ocrProvenance.extractionToken,
          serving_size: parsedServing,
          serving_unit: servingUnit,
          basis: basis,
          food_form: foodForm,
          ...nutrientsMap,
        });
        setOcrProvenance((prev) =>
          prev
            ? {
                ...prev,
                isConfirmed: true,
                unconfirmedCount: 0,
                confirmedValuesHash: confRes.confirmed_values_hash,
              }
            : null
        );
      } catch (err: unknown) {
        setGeneralError(
          err instanceof Error
            ? `Server confirmation failed: ${err.message}`
            : "Server confirmation failed."
        );
      }
    } else {
      const hash = computeNutritionValuesHash(
        parsedServing,
        servingUnit,
        basis,
        foodForm,
        nutrientsMap
      );
      setOcrProvenance((prev) =>
        prev
          ? {
              ...prev,
              isConfirmed: true,
              unconfirmedCount: 0,
              confirmedValuesHash: hash,
            }
          : null
      );
    }
  };

  const handleClear = () => {
    setProductName("");
    setServingSize("");
    setEnergyKcal("");
    setProteinG("");
    setCarbohydratesG("");
    setTotalSugarG("");
    setAddedSugarG("");
    setDietaryFiberG("");
    setTotalFatG("");
    setSaturatedFatG("");
    setTransFatG("");
    setCholesterolMg("");
    setSodiumMg("");
    setIngredientsText("");
    setGeneralError(null);
    setNutritionError(null);
    setIngredientError(null);
    setNutritionResult(null);
    setIngredientResult(null);
    setActiveProductName("");
    setOcrProvenance(null);
  };

  const handleLoadSample = () => {
    setProductName("Savory Spiced Biscuits");
    setServingSize("30");
    setServingUnit("g");
    setBasis("per_serving");
    setFoodForm("solid");
    setEnergyKcal("142");
    setProteinG("2.2");
    setCarbohydratesG("20");
    setTotalSugarG("8.5");
    setAddedSugarG("7");
    setDietaryFiberG("0.9");
    setTotalFatG("6.2");
    setSaturatedFatG("3.1");
    setTransFatG("0.02");
    setCholesterolMg("");
    setSodiumMg("260");
    setIngredientsText(
      "Refined Wheat Flour, Edible Vegetable Oil (Palm), Sugar, Liquid Glucose, " +
        "Salt, Invert Syrup, Raising Agent (INS 500(ii)), Emulsifier (INS 322(i)), " +
        "Flavour Enhancer (INS 621), Acidity Regulator (INS 330)"
    );
    setGeneralError(null);
    setNutritionError(null);
    setIngredientError(null);
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneralError(null);
    setNutritionError(null);
    setIngredientError(null);

    const hasIngredients = ingredientsText.trim().length > 0;
    const hasServingSize = servingSize.trim().length > 0;
    const hasAnyNutrient = [
      energyKcal,
      proteinG,
      carbohydratesG,
      totalSugarG,
      addedSugarG,
      dietaryFiberG,
      totalFatG,
      saturatedFatG,
      transFatG,
      cholesterolMg,
      sodiumMg,
    ].some((v) => v.trim() !== "");

    if (!hasIngredients && !hasServingSize && !hasAnyNutrient) {
      setGeneralError("Please enter nutrition label values or an ingredients list to analyze.");
      setNutritionResult(null);
      setIngredientResult(null);
      return;
    }

    if (hasAnyNutrient && !hasServingSize) {
      setGeneralError("Serving size is required to calculate nutrition values.");
      setNutritionResult(null);
      setIngredientResult(null);
      return;
    }

    if (hasServingSize) {
      const parsedServing = Number(servingSize);
      if (Number.isNaN(parsedServing) || parsedServing <= 0) {
        setGeneralError("Serving size must be a positive number.");
        setNutritionResult(null);
        setIngredientResult(null);
        return;
      }
    }

    // Failure-safe input consistency checks before API submission
    const parsedAdded = parseOptionalNumber(addedSugarG);
    const parsedTotalSugar = parseOptionalNumber(totalSugarG);
    if (parsedAdded !== null && parsedTotalSugar !== null && parsedAdded > (parsedTotalSugar + 0.05)) {
      setGeneralError(
        `Input Inconsistency: Added sugars (${parsedAdded}g) cannot exceed Total sugars (${parsedTotalSugar}g). ` +
        "Please verify your package label or correct the values."
      );
      setNutritionResult(null);
      setIngredientResult(null);
      return;
    }

    const parsedSat = parseOptionalNumber(saturatedFatG);
    const parsedTotalFat = parseOptionalNumber(totalFatG);
    if (parsedSat !== null && parsedTotalFat !== null && parsedSat > (parsedTotalFat + 0.05)) {
      setGeneralError(
        `Input Inconsistency: Saturated fat (${parsedSat}g) cannot exceed Total fat (${parsedTotalFat}g). ` +
        "Please check the values against the label."
      );
      setNutritionResult(null);
      setIngredientResult(null);
      return;
    }

    if (ocrProvenance?.isOcr && !ocrProvenance.isConfirmed) {
      setGeneralError(
        "Please confirm all scanned and edited values before running nutrition analysis."
      );
      setNutritionResult(null);
      setIngredientResult(null);
      return;
    }

    const nutrientsMap: Record<string, number | null> = {
      added_sugar_g: parseOptionalNumber(addedSugarG),
      carbohydrates_g: parseOptionalNumber(carbohydratesG),
      cholesterol_mg: parseOptionalNumber(cholesterolMg),
      dietary_fiber_g: parseOptionalNumber(dietaryFiberG),
      energy_kcal: parseOptionalNumber(energyKcal),
      protein_g: parseOptionalNumber(proteinG),
      saturated_fat_g: parseOptionalNumber(saturatedFatG),
      sodium_mg: parseOptionalNumber(sodiumMg),
      total_fat_g: parseOptionalNumber(totalFatG),
      total_sugar_g: parseOptionalNumber(totalSugarG),
      trans_fat_g: parseOptionalNumber(transFatG),
    };

    let confirmedHash: string | undefined = undefined;
    if (ocrProvenance?.isOcr) {
      if (!ocrProvenance.isConfirmed || !ocrProvenance.confirmedValuesHash) {
        setGeneralError(
          "Please review and confirm the scanned values before calculating."
        );
        setNutritionResult(null);
        setIngredientResult(null);
        return;
      }
      const currentDigest = computeNutritionValuesHash(
        Number(servingSize),
        servingUnit,
        basis,
        foodForm,
        nutrientsMap
      );
      const parts = ocrProvenance.confirmedValuesHash.split(".");
      const tokenDigest = parts.length === 5 ? parts[2] : ocrProvenance.confirmedValuesHash;
      if (tokenDigest !== currentDigest) {
        setGeneralError(
          "Values have been modified since confirmation. Please review and confirm the updated values before calculating."
        );
        setNutritionResult(null);
        setIngredientResult(null);
        return;
      }
      confirmedHash = ocrProvenance.confirmedValuesHash;
    }

    const requestId = ++activeRequestIdRef.current;
    setLoading(true);
    setActiveProductName(productName.trim());

    const requests: Promise<void>[] = [];

    // 1. Submit nutrition request if serving size provided
    if (hasServingSize) {
      const nutritionPayload: NutritionAnalysisRequest = {
        serving_size: Number(servingSize),
        serving_unit: servingUnit,
        basis: basis,
        food_form: foodForm,
        energy_kcal: nutrientsMap.energy_kcal,
        protein_g: nutrientsMap.protein_g,
        carbohydrates_g: nutrientsMap.carbohydrates_g,
        total_sugar_g: nutrientsMap.total_sugar_g,
        added_sugar_g: nutrientsMap.added_sugar_g,
        dietary_fiber_g: nutrientsMap.dietary_fiber_g,
        total_fat_g: nutrientsMap.total_fat_g,
        saturated_fat_g: nutrientsMap.saturated_fat_g,
        trans_fat_g: nutrientsMap.trans_fat_g,
        cholesterol_mg: nutrientsMap.cholesterol_mg,
        sodium_mg: nutrientsMap.sodium_mg,
        data_source: ocrProvenance?.isOcr ? "ocr" : "manual",
        is_confirmed: ocrProvenance ? ocrProvenance.isConfirmed : true,
        extraction_id: ocrProvenance?.isOcr ? ocrProvenance.extractionId : undefined,
        extraction_token: ocrProvenance?.isOcr ? ocrProvenance.extractionToken : undefined,
        confirmed_values_hash: confirmedHash,
      };

      requests.push(
        apiClient
          .analyzeNutrition(nutritionPayload)
          .then((res) => {
            if (activeRequestIdRef.current === requestId) {
              setNutritionResult(res);
            }
          })
          .catch((err: unknown) => {
            if (activeRequestIdRef.current === requestId) {
              setNutritionResult(null);
              setNutritionError(
                err instanceof Error ? err.message : "Nutrition analysis request failed."
              );
            }
          })
      );
    } else {
      setNutritionResult(null);
    }

    // 2. Submit ingredients request if text provided
    if (hasIngredients) {
      const ingredientPayload: IngredientAnalysisRequest = {
        ingredients_text: ingredientsText.trim(),
      };

      requests.push(
        apiClient
          .analyzeIngredients(ingredientPayload)
          .then((res) => {
            if (activeRequestIdRef.current === requestId) {
              setIngredientResult(res);
            }
          })
          .catch((err: unknown) => {
            if (activeRequestIdRef.current === requestId) {
              setIngredientResult(null);
              setIngredientError(
                err instanceof Error ? err.message : "Ingredient analysis request failed."
              );
            }
          })
      );
    } else {
      setIngredientResult(null);
    }

    try {
      await Promise.all(requests);
    } finally {
      if (activeRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  const handleTransferFromOcr = (values: TransferredValues) => {
    if (values.servingSize !== undefined && values.servingSize !== "") setServingSize(values.servingSize);
    if (values.servingUnit !== undefined) setServingUnit(values.servingUnit);
    if (values.basis !== undefined) setBasis(values.basis);
    if (values.energyKcal !== undefined && values.energyKcal !== "") setEnergyKcal(values.energyKcal);
    if (values.proteinG !== undefined && values.proteinG !== "") setProteinG(values.proteinG);
    if (values.carbohydratesG !== undefined && values.carbohydratesG !== "") setCarbohydratesG(values.carbohydratesG);
    if (values.totalSugarG !== undefined && values.totalSugarG !== "") setTotalSugarG(values.totalSugarG);
    if (values.addedSugarG !== undefined && values.addedSugarG !== "") setAddedSugarG(values.addedSugarG);
    if (values.dietaryFiberG !== undefined && values.dietaryFiberG !== "") setDietaryFiberG(values.dietaryFiberG);
    if (values.totalFatG !== undefined && values.totalFatG !== "") setTotalFatG(values.totalFatG);
    if (values.saturatedFatG !== undefined && values.saturatedFatG !== "") setSaturatedFatG(values.saturatedFatG);
    if (values.transFatG !== undefined && values.transFatG !== "") setTransFatG(values.transFatG);
    if (values.cholesterolMg !== undefined && values.cholesterolMg !== "") setCholesterolMg(values.cholesterolMg);
    if (values.sodiumMg !== undefined && values.sodiumMg !== "") setSodiumMg(values.sodiumMg);
    if (values.ingredientsText !== undefined && values.ingredientsText !== "") setIngredientsText(values.ingredientsText);

    setOcrProvenance({
      isOcr: true,
      isConfirmed: values.isConfirmed ?? false,
      unconfirmedCount: values.unconfirmedCount ?? 0,
      extractionId: values.extractionId,
      extractionToken: values.extractionToken,
      confirmedValuesHash: values.confirmedValuesHash,
    });
  };


  return (
    <>
      <LabelScanner onTransferValues={handleTransferFromOcr} />

      <section className="card" aria-labelledby="analyzer-heading" style={{ marginTop: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" }}>
        <h2 id="analyzer-heading" style={{ margin: 0, fontSize: "clamp(1.1rem, 4vw, 1.25rem)" }}>
          Packaged Food Label Analyzer
        </h2>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={handleLoadSample}
            className="btn-retry"
            style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem", minHeight: "44px" }}
          >
            Load Sample
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="btn-retry"
            style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem", minHeight: "44px" }}
          >
            Clear
          </button>
        </div>
      </div>

      <p style={{ marginTop: "0.5rem", marginBottom: "1.25rem", color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Enter nutrition panel values and ingredients declaration from the physical package. Missing values are preserved as unknown and are never assumed to be zero.
      </p>

      {/* OCR Provenance Notice */}
      {ocrProvenance?.isOcr && (
        <div
          role="status"
          style={{
            marginBottom: "1.25rem",
            padding: "0.75rem",
            backgroundColor: ocrProvenance.isConfirmed ? "#f0fdf4" : "#fffbeb",
            color: ocrProvenance.isConfirmed ? "#166534" : "#92400e",
            border: `1px solid ${ocrProvenance.isConfirmed ? "#86efac" : "#fde68a"}`,
            borderRadius: "6px",
            fontSize: "0.85rem",
          }}
        >
          {ocrProvenance.isConfirmed ? (
            <strong>✓ Values were imported from label OCR and confirmed by the user.</strong>
          ) : (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
              <span style={{ flex: "1 1 100%" }}>
                <strong>Notice:</strong> Values were imported from packaging OCR ({ocrProvenance.unconfirmedCount} unconfirmed or edited). Please check values against your physical package before calculating.
              </span>
              <button
                type="button"
                onClick={handleConfirmOcrValues}
                className="btn-retry"
                style={{
                  fontSize: "0.85rem",
                  padding: "0.5rem 0.85rem",
                  minHeight: "44px",
                  width: "100%",
                  fontWeight: 600,
                  backgroundColor: "#ffffff",
                  border: "1px solid #d97706",
                  color: "#92400e",
                }}
              >
                Confirm Values Against Package
              </button>
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleAnalyze} style={{ display: "grid", gap: "1.25rem" }}>
        {/* Product Identity */}
        <div>
          <label htmlFor="productName" style={{ display: "block", fontWeight: 600, fontSize: "0.875rem", marginBottom: "0.25rem" }}>
            Product Name (Optional):
          </label>
          <input
            id="productName"
            type="text"
            placeholder="e.g. Marie Biscuits, Mango Juice, Corn Flakes"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--color-border)" }}
          />
        </div>

        {/* Serving Size & Form Settings */}
        <div style={{ padding: "0.875rem", backgroundColor: "#f8fafc", borderRadius: "6px", border: "1px solid var(--color-border)", display: "grid", gap: "0.75rem" }}>
          <strong style={{ fontSize: "0.9rem" }}>Serving &amp; Label Specification</strong>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 140px), 1fr))", gap: "0.75rem" }}>
            <div>
              <label htmlFor="servingSize" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                Serving Size:
              </label>
              <input
                id="servingSize"
                type="number"
                step="any"
                min="0.01"
                placeholder="e.g. 30"
                value={servingSize}
                onChange={(e) => handleFieldChange(setServingSize, e.target.value)}
                style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="servingUnit" style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
                Serving Unit:
              </label>
              <select
                id="servingUnit"
                value={servingUnit}
                onChange={(e) =>
                  handleServingUnitChange(
                    e.target.value as "g" | "ml" | "kg" | "l" | "piece" | "portion"
                  )
                }
                style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="g">Grams (g)</option>
                <option value="kg">Kilograms (kg)</option>
                <option value="ml">Millilitres (ml)</option>
                <option value="l">Litres (l)</option>
                <option value="piece">Piece (Discrete)</option>
                <option value="portion">Portion (Discrete)</option>
              </select>
            </div>

            <div>
              <label htmlFor="basis" style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
                Declared Basis:
              </label>
              <select
                id="basis"
                value={basis}
                onChange={(e) =>
                  handleBasisChange(e.target.value as "per_serving" | "per_100g" | "per_100ml")
                }
                style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="per_serving">Per Serving</option>
                <option value="per_100g">Per 100g</option>
                <option value="per_100ml">Per 100ml</option>
              </select>
            </div>

            <div>
              <label htmlFor="foodForm" style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
                Food Form:
              </label>
              <select
                id="foodForm"
                value={foodForm}
                onChange={(e) => handleFoodFormChange(e.target.value as "solid" | "liquid")}
                style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="solid">Solid Food</option>
                <option value="liquid">Liquid / Beverage</option>
              </select>
            </div>
          </div>
        </div>

        {/* Nutrition Label Values */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.25rem", marginBottom: "0.35rem" }}>
            <label style={{ fontWeight: 600, fontSize: "0.875rem" }}>
              Nutrition Facts (Leave blank if missing from label):
            </label>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              0 = zero; blank = missing.
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 140px), 1fr))", gap: "0.6rem" }}>
            {[
              { id: "energyKcal", label: "Energy (kcal)", val: energyKcal, set: setEnergyKcal },
              { id: "proteinG", label: "Protein (g)", val: proteinG, set: setProteinG },
              { id: "carbohydratesG", label: "Carbs (g)", val: carbohydratesG, set: setCarbohydratesG },
              { id: "totalSugarG", label: "Total Sugar (g)", val: totalSugarG, set: setTotalSugarG },
              { id: "addedSugarG", label: "Added Sugar (g)", val: addedSugarG, set: setAddedSugarG },
              { id: "dietaryFiberG", label: "Fiber (g)", val: dietaryFiberG, set: setDietaryFiberG },
              { id: "totalFatG", label: "Total Fat (g)", val: totalFatG, set: setTotalFatG },
              { id: "saturatedFatG", label: "Sat. Fat (g)", val: saturatedFatG, set: setSaturatedFatG },
              { id: "transFatG", label: "Trans Fat (g)", val: transFatG, set: setTransFatG },
              { id: "cholesterolMg", label: "Cholesterol (mg)", val: cholesterolMg, set: setCholesterolMg },
              { id: "sodiumMg", label: "Sodium (mg)", val: sodiumMg, set: setSodiumMg },
            ].map(({ id, label, val, set }) => (
              <div key={id}>
                <label htmlFor={id} style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, marginBottom: "0.2rem" }}>
                  {label}
                </label>
                <input
                  id={id}
                  type="number"
                  step="any"
                  min="0"
                  value={val}
                  onChange={(e) => handleFieldChange(set, e.target.value)}
                  style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Ingredients Declaration Input */}
        <div>
          <label htmlFor="ingredientsText" style={{ display: "block", fontWeight: 600, fontSize: "0.875rem", marginBottom: "0.25rem" }}>
            Declared Ingredients Statement:
          </label>
          <textarea
            id="ingredientsText"
            rows={3}
            placeholder="Paste or review ingredients list from package, e.g. Wheat Flour, Palm Oil, Sugar, Emulsifier (INS 322(i)), Flavour Enhancer (INS 621)..."
            value={ingredientsText}
            onChange={(e) => setIngredientsText(e.target.value)}
            style={{
              width: "100%",
              padding: "0.5rem",
              borderRadius: "6px",
              border: "1px solid var(--color-border)",
              fontFamily: "inherit",
              fontSize: "0.875rem",
            }}
          />
        </div>

        {/* Action Button - Thumb Friendly */}
        <div>
          <button
            type="submit"
            className="btn-retry"
            disabled={loading}
            style={{
              width: "100%",
              minHeight: "48px",
              padding: "0.75rem 1.25rem",
              backgroundColor: "var(--color-primary)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "1rem",
            }}
          >
            {loading ? "Analyzing Deterministically..." : "Analyze Label & Ingredients"}
          </button>
        </div>
      </form>

      {/* General Form Error */}
      {generalError && (
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
          <strong>Input Error:</strong> {generalError}
        </div>
      )}

      {/* Results Presentation */}
      {(nutritionResult || ingredientResult || nutritionError || ingredientError) && (
        <div style={{ marginTop: "1.75rem", display: "grid", gap: "1.25rem" }}>
          {activeProductName && (
            <h3 style={{ borderBottom: "2px solid var(--color-border)", paddingBottom: "0.5rem", fontSize: "1.15rem" }}>
              Analysis Report: {activeProductName}
            </h3>
          )}

          {/* 1. Nutrition Analysis Output */}
          {nutritionError && (
            <div
              role="alert"
              style={{
                padding: "0.75rem",
                backgroundColor: "var(--color-offline-bg)",
                color: "var(--color-offline-text)",
                borderRadius: "6px",
                fontSize: "0.875rem",
              }}
            >
              <strong>Nutrition Analysis Failed:</strong> {nutritionError}
            </div>
          )}

          {nutritionResult && (
            <article className="card" style={{ backgroundColor: "#f8fafc" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
                <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Nutrition Fact Assessment</h4>
                <span className={nutritionResult.is_complete ? "status-pill status-online" : "status-pill status-offline"}>
                  {nutritionResult.is_complete ? "Complete Data" : "Incomplete Data"}
                </span>
              </div>

              {!nutritionResult.is_complete && (
                <div style={{ marginBottom: "0.75rem", padding: "0.5rem 0.75rem", backgroundColor: "var(--color-warning-bg)", color: "var(--color-warning-text)", borderRadius: "4px", fontSize: "0.85rem" }}>
                  <strong>Missing on label:</strong> {nutritionResult.missing_nutrients.join(", ")}. Missing values are tracked as unknown and never assumed to be zero.
                </div>
              )}

              {/* Mobile-Friendly Stacked Nutrition Cards (Visible on Small Screens) */}
              <div style={{ display: "grid", gap: "0.5rem", marginBottom: "1rem" }}>
                <div className="responsive-table-wrapper">
                  <table style={{ width: "100%", minWidth: "320px", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ borderBottom: "2px solid var(--color-border)", backgroundColor: "#f1f5f9" }}>
                        <th style={{ padding: "0.6rem 0.5rem" }}>Nutrient</th>
                        <th style={{ padding: "0.6rem 0.5rem" }}>Per Serving ({nutritionResult.serving_size}{nutritionResult.serving_unit})</th>
                        <th style={{ padding: "0.6rem 0.5rem" }}>Per 100{nutritionResult.food_form === "liquid" ? "ml" : "g"}</th>
                        <th style={{ padding: "0.6rem 0.5rem" }}>% Daily Value (ICMR)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nutritionResult.daily_value_comparisons.map((c) => {
                        const per100Val = nutritionResult.per_100[c.nutrient_key];
                        const perServingVal = nutritionResult.per_serving[c.nutrient_key];

                        return (
                          <tr key={c.nutrient_key} style={{ borderBottom: "1px solid var(--color-border)" }}>
                            <td style={{ padding: "0.5rem 0.5rem", fontWeight: 500 }}>{c.display_name}</td>
                            <td style={{ padding: "0.5rem 0.5rem" }}>
                              {perServingVal !== null && perServingVal !== undefined ? `${perServingVal} ${c.unit}` : <span style={{ color: "#94a3b8" }}>Not provided</span>}
                            </td>
                            <td style={{ padding: "0.5rem 0.5rem" }}>
                              {per100Val !== null && per100Val !== undefined ? `${per100Val} ${c.unit}` : <span style={{ color: "#94a3b8" }}>Not provided</span>}
                            </td>
                            <td style={{ padding: "0.5rem 0.5rem" }}>
                              {c.percentage_of_daily_value !== null ? `${c.percentage_of_daily_value}%` : <span style={{ color: "#94a3b8" }}>—</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Flags & Regulatory Alerts */}
              <div>
                <strong style={{ fontSize: "0.9rem" }}>FSSAI &amp; Dietary Guidance Flags:</strong>
                {nutritionResult.flags.length === 0 ? (
                  <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", marginTop: "0.25rem" }}>
                    No high-threshold criteria triggered for the declared values.
                  </p>
                ) : (
                  <ul style={{ paddingLeft: "1.25rem", marginTop: "0.5rem", fontSize: "0.85rem" }}>
                    {nutritionResult.flags.map((flag) => {
                      const badgeColor =
                        flag.severity === "alert"
                          ? "var(--color-offline-bg)"
                          : flag.severity === "warning"
                          ? "var(--color-warning-bg)"
                          : "#e0f2fe";
                      const textColor =
                        flag.severity === "alert"
                          ? "var(--color-offline-text)"
                          : flag.severity === "warning"
                          ? "var(--color-warning-text)"
                          : "#0369a1";

                      return (
                        <li key={flag.id} style={{ marginBottom: "0.6rem" }}>
                          <span style={{ backgroundColor: badgeColor, color: textColor, padding: "0.2rem 0.45rem", borderRadius: "4px", fontWeight: 600, fontSize: "0.75rem", marginRight: "0.375rem" }}>
                            {flag.severity.toUpperCase()}
                          </span>
                          <strong>{flag.title}:</strong> {flag.explanation}
                          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.15rem", overflowWrap: "anywhere" }}>
                            Source: {flag.citation}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {/* Everyday Quantity Explanations */}
              {nutritionResult.everyday_explanations && nutritionResult.everyday_explanations.length > 0 && (
                <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--color-border)" }}>
                  <strong style={{ fontSize: "0.9rem", display: "block", marginBottom: "0.5rem" }}>
                    Everyday Quantity Explanations:
                  </strong>
                  <div style={{ display: "grid", gap: "0.6rem" }}>
                    {nutritionResult.everyday_explanations.map((exp, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: "0.6rem 0.75rem",
                          backgroundColor: "#f1f5f9",
                          borderRadius: "6px",
                          fontSize: "0.825rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.25rem" }}>
                          <span style={{ fontWeight: 600, color: "#1e293b" }}>
                            {exp.everyday_comparison}
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            Declared: {exp.original_value} {exp.original_unit}
                          </span>
                        </div>
                        <div style={{ marginTop: "0.2rem", color: "#334155" }}>
                          {exp.plain_language_summary}
                        </div>
                        {exp.formula && (
                          <div style={{ marginTop: "0.2rem", fontSize: "0.75rem", color: "#475569", fontFamily: "monospace", overflowWrap: "anywhere" }}>
                            Formula: {exp.formula}
                          </div>
                        )}
                        {exp.assumptions.length > 0 && (
                          <div style={{ marginTop: "0.2rem", fontSize: "0.725rem", color: "#64748b" }}>
                            <em>Assumptions:</em> {exp.assumptions.join(" ")}
                          </div>
                        )}
                        <div style={{ marginTop: "0.2rem", fontSize: "0.725rem", color: "#64748b" }}>
                          <em>Notice:</em> {exp.limitations_and_uncertainty}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Deterministic Calculation Assumptions & Audit Trail */}
              {nutritionResult.calculation_assumptions && Object.keys(nutritionResult.calculation_assumptions).length > 0 && (
                <details style={{ marginTop: "1rem", fontSize: "0.75rem", color: "#64748b" }}>
                  <summary style={{ cursor: "pointer", fontWeight: 600, padding: "0.25rem 0" }}>
                    Deterministic Calculation Audit &amp; Mathematical Assumptions
                  </summary>
                  <ul style={{ paddingLeft: "1.25rem", marginTop: "0.35rem", marginBottom: 0 }}>
                    {Object.entries(nutritionResult.calculation_assumptions).map(([key, val]) => (
                      <li key={key} style={{ marginBottom: "0.25rem" }}>
                        <strong>{key.replace(/_/g, " ")}:</strong> {val}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </article>
          )}

          {/* 2. Ingredients & Additives Output */}
          {ingredientError && (
            <div
              role="alert"
              style={{
                padding: "0.75rem",
                backgroundColor: "var(--color-offline-bg)",
                color: "var(--color-offline-text)",
                borderRadius: "6px",
                fontSize: "0.875rem",
              }}
            >
              <strong>Ingredient Analysis Failed:</strong> {ingredientError}
            </div>
          )}

          {ingredientResult && (
            <article className="card" style={{ backgroundColor: "#f8fafc" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
                <h4 style={{ margin: 0, fontSize: "1.1rem" }}>Ingredient &amp; Additive Verification</h4>
                <span className="status-pill status-loading">
                  {ingredientResult.total_matched} recognized / {ingredientResult.total_tokens_detected} total declared
                </span>
              </div>

              {/* Category Breakdown Chips (Phase 4A) */}
              {ingredientResult.category_summary && Object.keys(ingredientResult.category_summary).length > 0 && (
                <div style={{ marginBottom: "0.75rem", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                  {Object.entries(ingredientResult.category_summary).map(([cat, count]) => (
                    <span key={cat} className="category-pill category-pill-additive">
                      {cat.replace(/_/g, " ")}: {count}
                    </span>
                  ))}
                </div>
              )}

              {/* Ambiguous Functional Classes Warning Box (Phase 4A) */}
              {ingredientResult.ambiguous_items && ingredientResult.ambiguous_items.length > 0 && (
                <div
                  role="alert"
                  style={{
                    marginBottom: "1rem",
                    padding: "0.75rem",
                    backgroundColor: "#fffbeb",
                    color: "#92400e",
                    border: "1px solid #fde68a",
                    borderRadius: "6px",
                    fontSize: "0.85rem",
                  }}
                >
                  <strong>⚠️ Ambiguous Declarations (Not Guessed):</strong>
                  <div style={{ marginTop: "0.25rem" }}>
                    The following functional terms were declared without an INS or E number qualifier:{" "}
                    <strong>{ingredientResult.ambiguous_items.join(", ")}</strong>.
                  </div>
                  <div style={{ marginTop: "0.25rem", fontSize: "0.775rem", color: "#78350f" }}>
                    To eliminate false positives, healthyIndia never silently guesses additive identities.
                  </div>
                </div>
              )}

              {/* Matched Additives & Ingredients List */}
              <div style={{ marginBottom: "1rem" }}>
                <strong style={{ fontSize: "0.9rem" }}>Recognized Ingredients &amp; Additives:</strong>
                {ingredientResult.matched_items.length === 0 ? (
                  <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", marginTop: "0.25rem" }}>
                    No items from the verified reference dataset matched the declaration.
                  </p>
                ) : (
                  <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.5rem" }}>
                    {ingredientResult.matched_items.map((item) => (
                      <div
                        key={item.additive.id}
                        style={{
                          padding: "0.75rem",
                          backgroundColor: "#ffffff",
                          borderRadius: "6px",
                          border: "1px solid var(--color-border)",
                          fontSize: "0.85rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.25rem" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                            {item.additive.canonical_name}{" "}
                            {item.additive.ins_number || item.additive.e_number ? (
                              <span style={{ color: "#475569" }}>({item.additive.ins_number || item.additive.e_number})</span>
                            ) : null}
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            Matched from: &ldquo;{item.raw_text}&rdquo;
                          </span>
                        </div>

                        {/* Occurrence and Compound Badges */}
                        <div style={{ marginTop: "0.25rem", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                          {item.is_compound && (
                            <span className="category-pill category-pill-fortification">
                              Compound Ingredient
                            </span>
                          )}
                          {item.occurrences && item.occurrences > 1 && (
                            <span className="category-pill category-pill-sweetener">
                              Declared {item.occurrences}x on label
                            </span>
                          )}
                          {item.additive.entity_type && (
                            <span className="category-pill category-pill-additive">
                              {item.additive.entity_type.replace(/_/g, " ")}
                            </span>
                          )}
                        </div>

                        {item.additive.functional_classes && item.additive.functional_classes.length > 0 && (
                          <div style={{ marginTop: "0.25rem", color: "var(--color-text-muted)" }}>
                            <strong>Functional Class:</strong> {item.additive.functional_classes.join(", ")}
                          </div>
                        )}

                        {item.additive.chemical_identity && (
                          <div style={{ marginTop: "0.25rem", color: "#64748b", fontSize: "0.8rem" }}>
                            <strong>Chemical Identity:</strong> {item.additive.chemical_identity}
                          </div>
                        )}

                        <div style={{ marginTop: "0.25rem" }}>
                          <strong>Regulatory Status:</strong> {item.additive.regulatory_status}
                        </div>

                        {item.additive.scope_limitations && (
                          <div style={{ marginTop: "0.25rem", color: "#64748b", fontSize: "0.8rem" }}>
                            <strong>Scope Limitations:</strong> {item.additive.scope_limitations}
                          </div>
                        )}

                        {item.additive.acceptable_daily_intake && (
                          <div style={{ marginTop: "0.25rem", fontSize: "0.8rem" }}>
                            <strong>Acceptable Daily Intake (ADI):</strong> {item.additive.acceptable_daily_intake}
                          </div>
                        )}

                        {item.additive.health_effects_evidence && (
                          <div style={{ marginTop: "0.25rem", fontSize: "0.8rem", color: "#334155" }}>
                            <strong>Scientific Evidence &amp; Health Assessment:</strong> {item.additive.health_effects_evidence}
                          </div>
                        )}

                        {item.additive.population_sensitivities && (
                          <div style={{ marginTop: "0.25rem", fontSize: "0.8rem", color: "#991b1b", backgroundColor: "#fef2f2", padding: "0.35rem 0.5rem", borderRadius: "4px" }}>
                            <strong>Sensitivities &amp; Population Cautions:</strong> {item.additive.population_sensitivities}
                          </div>
                        )}

                        {item.additive.everyday_quantity_explanation && (
                          <div
                            style={{
                              marginTop: "0.4rem",
                              padding: "0.5rem 0.65rem",
                              backgroundColor: "#f0fdf4",
                              border: "1px solid #bbf7d0",
                              borderRadius: "4px",
                              fontSize: "0.8rem",
                            }}
                          >
                            <strong style={{ color: "#166534" }}>Everyday Quantity Explanation:</strong>
                            <div style={{ marginTop: "0.15rem", color: "#15803d", fontWeight: 600 }}>
                              {item.additive.everyday_quantity_explanation.everyday_comparison}
                            </div>
                            <div style={{ marginTop: "0.15rem", color: "#334155", fontSize: "0.775rem" }}>
                              {item.additive.everyday_quantity_explanation.plain_language_summary}
                            </div>
                            {item.additive.everyday_quantity_explanation.formula && (
                              <div style={{ marginTop: "0.15rem", fontSize: "0.725rem", color: "#475569", fontFamily: "monospace", overflowWrap: "anywhere" }}>
                                Calculation: {item.additive.everyday_quantity_explanation.formula}
                              </div>
                            )}
                            <div style={{ marginTop: "0.15rem", fontSize: "0.7rem", color: "#64748b" }}>
                              <em>Limitations:</em> {item.additive.everyday_quantity_explanation.limitations_and_uncertainty}
                            </div>
                          </div>
                        )}

                        {item.additive.sources && item.additive.sources.length > 0 && (
                          <div style={{ marginTop: "0.35rem", fontSize: "0.75rem", color: "#475569", overflowWrap: "anywhere" }}>
                            <strong>Official Citations:</strong>{" "}
                            {item.additive.sources.map((s, idx) => (
                              <span key={s.url + idx}>
                                {idx > 0 && " | "}
                                <a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-accent)", overflowWrap: "anywhere" }}>
                                  {s.title}
                                </a>{" "}
                                ({s.source_type}, reviewed {s.retrieval_date})
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Unmatched Declared Ingredients */}
              {ingredientResult.unmatched_items.length > 0 && (
                <div style={{ marginTop: "1rem", padding: "0.75rem", backgroundColor: "#ffffff", borderRadius: "6px", border: "1px solid var(--color-border)" }}>
                  <strong style={{ fontSize: "0.875rem" }}>Other Declared Ingredients (Preserved Unaltered):</strong>
                  <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginTop: "0.25rem", marginBottom: "0.5rem" }}>
                    Preserved exactly as declared on the packaging. Unmatched items are never guessed or altered.
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                    {ingredientResult.unmatched_items.map((token, idx) => (
                      <span
                        key={token + idx}
                        style={{
                          backgroundColor: "#f1f5f9",
                          color: "#334155",
                          padding: "0.25rem 0.55rem",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          overflowWrap: "anywhere",
                        }}
                      >
                        {token}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </article>
          )}

          {/* 3. Disclaimers & Methodology Transparency */}
          <div style={{ padding: "0.75rem", backgroundColor: "#f1f5f9", borderRadius: "6px", border: "1px solid var(--color-border)", fontSize: "0.8rem", color: "#475569" }}>
            <strong>Regulatory &amp; Scientific Methodology Notice:</strong>
            <p style={{ marginTop: "0.25rem" }}>
              healthyIndia delivers deterministic comparisons against explicit statutory standards (FSSAI) and dietary references (ICMR-NIN). We do not produce an arbitrary &ldquo;safe percentage&rdquo; or declare any product categorically safe or unsafe. Physical packaging declarations remain the primary source of truth.
            </p>
          </div>
        </div>
      )}
    </section>
    </>
  );
};
