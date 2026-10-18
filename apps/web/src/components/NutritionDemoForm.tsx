"use client";

import React, { useState } from "react";
import {
  apiClient,
  NutritionAnalysisRequest,
  NutritionAnalysisResponse,
  IngredientAnalysisRequest,
  IngredientAnalysisResponse,
} from "../lib/api/client";

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
  const [servingUnit, setServingUnit] = useState<"g" | "ml" | "piece" | "portion">("g");
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
      return;
    }

    if (hasAnyNutrient && !hasServingSize) {
      setGeneralError("Serving size is required to calculate nutrition values.");
      return;
    }

    if (hasServingSize) {
      const parsedServing = Number(servingSize);
      if (Number.isNaN(parsedServing) || parsedServing <= 0) {
        setGeneralError("Serving size must be a positive number.");
        return;
      }
    }

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
        energy_kcal: parseOptionalNumber(energyKcal),
        protein_g: parseOptionalNumber(proteinG),
        carbohydrates_g: parseOptionalNumber(carbohydratesG),
        total_sugar_g: parseOptionalNumber(totalSugarG),
        added_sugar_g: parseOptionalNumber(addedSugarG),
        dietary_fiber_g: parseOptionalNumber(dietaryFiberG),
        total_fat_g: parseOptionalNumber(totalFatG),
        saturated_fat_g: parseOptionalNumber(saturatedFatG),
        trans_fat_g: parseOptionalNumber(transFatG),
        cholesterol_mg: parseOptionalNumber(cholesterolMg),
        sodium_mg: parseOptionalNumber(sodiumMg),
      };

      requests.push(
        apiClient
          .analyzeNutrition(nutritionPayload)
          .then((res) => {
            setNutritionResult(res);
          })
          .catch((err: unknown) => {
            setNutritionResult(null);
            setNutritionError(
              err instanceof Error ? err.message : "Nutrition analysis request failed."
            );
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
            setIngredientResult(res);
          })
          .catch((err: unknown) => {
            setIngredientResult(null);
            setIngredientError(
              err instanceof Error ? err.message : "Ingredient analysis request failed."
            );
          })
      );
    } else {
      setIngredientResult(null);
    }

    try {
      await Promise.all(requests);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card" aria-labelledby="analyzer-heading" style={{ marginTop: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" }}>
        <h2 id="analyzer-heading" style={{ margin: 0 }}>Packaged Food Label Analyzer</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            onClick={handleLoadSample}
            className="btn-retry"
            style={{ fontSize: "0.8rem", padding: "0.25rem 0.5rem" }}
          >
            Load Sample
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="btn-retry"
            style={{ fontSize: "0.8rem", padding: "0.25rem 0.5rem" }}
          >
            Clear
          </button>
        </div>
      </div>

      <p style={{ marginTop: "0.5rem", marginBottom: "1.25rem", color: "var(--color-text-muted)" }}>
        Enter nutrition panel values and ingredients declaration from the physical package. Missing values are preserved as unknown and are never assumed to be zero.
      </p>

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
          <strong>Serving & Label Specification</strong>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.75rem" }}>
            <div>
              <label htmlFor="servingSize" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
                Serving Size:
              </label>
              <input
                id="servingSize"
                type="number"
                step="any"
                min="0.01"
                placeholder="e.g. 30"
                value={servingSize}
                onChange={(e) => setServingSize(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="servingUnit" style={{ display: "block", fontSize: "0.85rem" }}>
                Serving Unit:
              </label>
              <select
                id="servingUnit"
                value={servingUnit}
                onChange={(e) => setServingUnit(e.target.value as "g" | "ml" | "piece" | "portion")}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="g">Grams (g)</option>
                <option value="ml">Millilitres (ml)</option>
                <option value="piece">Piece (Discrete)</option>
                <option value="portion">Portion (Discrete)</option>
              </select>
            </div>

            <div>
              <label htmlFor="basis" style={{ display: "block", fontSize: "0.85rem" }}>
                Declared Basis:
              </label>
              <select
                id="basis"
                value={basis}
                onChange={(e) => setBasis(e.target.value as "per_serving" | "per_100g" | "per_100ml")}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="per_serving">Per Serving</option>
                <option value="per_100g">Per 100g</option>
                <option value="per_100ml">Per 100ml</option>
              </select>
            </div>

            <div>
              <label htmlFor="foodForm" style={{ display: "block", fontSize: "0.85rem" }}>
                Food Form:
              </label>
              <select
                id="foodForm"
                value={foodForm}
                onChange={(e) => setFoodForm(e.target.value as "solid" | "liquid")}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              >
                <option value="solid">Solid Food</option>
                <option value="liquid">Liquid / Beverage</option>
              </select>
            </div>
          </div>
        </div>

        {/* Nutrition Label Values */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.25rem" }}>
            <label style={{ fontWeight: 600, fontSize: "0.875rem" }}>
              Nutrition Facts (Leave blank if missing from label):
            </label>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              Entering 0 is treated as zero; blank is treated as missing.
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.5rem" }}>
            <div>
              <label htmlFor="energyKcal" style={{ display: "block", fontSize: "0.8rem" }}>Energy (kcal)</label>
              <input
                id="energyKcal"
                type="number"
                step="any"
                min="0"
                value={energyKcal}
                onChange={(e) => setEnergyKcal(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="proteinG" style={{ display: "block", fontSize: "0.8rem" }}>Protein (g)</label>
              <input
                id="proteinG"
                type="number"
                step="any"
                min="0"
                value={proteinG}
                onChange={(e) => setProteinG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="carbohydratesG" style={{ display: "block", fontSize: "0.8rem" }}>Carbs (g)</label>
              <input
                id="carbohydratesG"
                type="number"
                step="any"
                min="0"
                value={carbohydratesG}
                onChange={(e) => setCarbohydratesG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="totalSugarG" style={{ display: "block", fontSize: "0.8rem" }}>Total Sugar (g)</label>
              <input
                id="totalSugarG"
                type="number"
                step="any"
                min="0"
                value={totalSugarG}
                onChange={(e) => setTotalSugarG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="addedSugarG" style={{ display: "block", fontSize: "0.8rem" }}>Added Sugar (g)</label>
              <input
                id="addedSugarG"
                type="number"
                step="any"
                min="0"
                value={addedSugarG}
                onChange={(e) => setAddedSugarG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="dietaryFiberG" style={{ display: "block", fontSize: "0.8rem" }}>Fiber (g)</label>
              <input
                id="dietaryFiberG"
                type="number"
                step="any"
                min="0"
                value={dietaryFiberG}
                onChange={(e) => setDietaryFiberG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="totalFatG" style={{ display: "block", fontSize: "0.8rem" }}>Total Fat (g)</label>
              <input
                id="totalFatG"
                type="number"
                step="any"
                min="0"
                value={totalFatG}
                onChange={(e) => setTotalFatG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="saturatedFatG" style={{ display: "block", fontSize: "0.8rem" }}>Sat. Fat (g)</label>
              <input
                id="saturatedFatG"
                type="number"
                step="any"
                min="0"
                value={saturatedFatG}
                onChange={(e) => setSaturatedFatG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="transFatG" style={{ display: "block", fontSize: "0.8rem" }}>Trans Fat (g)</label>
              <input
                id="transFatG"
                type="number"
                step="any"
                min="0"
                value={transFatG}
                onChange={(e) => setTransFatG(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="cholesterolMg" style={{ display: "block", fontSize: "0.8rem" }}>Cholesterol (mg)</label>
              <input
                id="cholesterolMg"
                type="number"
                step="any"
                min="0"
                value={cholesterolMg}
                onChange={(e) => setCholesterolMg(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>

            <div>
              <label htmlFor="sodiumMg" style={{ display: "block", fontSize: "0.8rem" }}>Sodium (mg)</label>
              <input
                id="sodiumMg"
                type="number"
                step="any"
                min="0"
                value={sodiumMg}
                onChange={(e) => setSodiumMg(e.target.value)}
                style={{ width: "100%", padding: "0.375rem 0.5rem", borderRadius: "4px", border: "1px solid var(--color-border)" }}
              />
            </div>
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
            placeholder="Paste the ingredients list from the package, e.g. Wheat Flour, Palm Oil, Sugar, Emulsifier (INS 322(i)), Flavour Enhancer (INS 621)..."
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

        {/* Action Button */}
        <div>
          <button
            type="submit"
            className="btn-retry"
            disabled={loading}
            style={{
              padding: "0.6rem 1.25rem",
              backgroundColor: "var(--color-primary)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "0.95rem",
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
            fontSize: "0.9rem",
          }}
        >
          <strong>Input Error:</strong> {generalError}
        </div>
      )}

      {/* Results Presentation */}
      {(nutritionResult || ingredientResult || nutritionError || ingredientError) && (
        <div style={{ marginTop: "1.75rem", display: "grid", gap: "1.25rem" }}>
          {activeProductName && (
            <h3 style={{ borderBottom: "2px solid var(--color-border)", paddingBottom: "0.5rem" }}>
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

              {/* Nutrition Table */}
              <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--color-border)" }}>
                      <th style={{ padding: "0.5rem 0.25rem" }}>Nutrient</th>
                      <th style={{ padding: "0.5rem 0.25rem" }}>Per Serving ({nutritionResult.serving_size}{nutritionResult.serving_unit})</th>
                      <th style={{ padding: "0.5rem 0.25rem" }}>Per 100{nutritionResult.food_form === "liquid" ? "ml" : "g"}</th>
                      <th style={{ padding: "0.5rem 0.25rem" }}>% Daily Value (ICMR-NIN)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nutritionResult.daily_value_comparisons.map((c) => {
                      const per100Val = nutritionResult.per_100[c.nutrient_key];
                      const perServingVal = nutritionResult.per_serving[c.nutrient_key];

                      return (
                        <tr key={c.nutrient_key} style={{ borderBottom: "1px solid var(--color-border)" }}>
                          <td style={{ padding: "0.375rem 0.25rem", fontWeight: 500 }}>{c.display_name}</td>
                          <td style={{ padding: "0.375rem 0.25rem" }}>
                            {perServingVal !== null && perServingVal !== undefined ? `${perServingVal} ${c.unit}` : <span style={{ color: "#94a3b8" }}>Not provided</span>}
                          </td>
                          <td style={{ padding: "0.375rem 0.25rem" }}>
                            {per100Val !== null && per100Val !== undefined ? `${per100Val} ${c.unit}` : <span style={{ color: "#94a3b8" }}>Not provided</span>}
                          </td>
                          <td style={{ padding: "0.375rem 0.25rem" }}>
                            {c.percentage_of_daily_value !== null ? `${c.percentage_of_daily_value}%` : <span style={{ color: "#94a3b8" }}>—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
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
                        <li key={flag.id} style={{ marginBottom: "0.5rem" }}>
                          <span style={{ backgroundColor: badgeColor, color: textColor, padding: "0.15rem 0.4rem", borderRadius: "4px", fontWeight: 600, fontSize: "0.75rem", marginRight: "0.375rem" }}>
                            {flag.severity.toUpperCase()}
                          </span>
                          <strong>{flag.title}:</strong> {flag.explanation}
                          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.15rem" }}>
                            Source: {flag.citation}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
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

              {/* Matched Additives List */}
              <div style={{ marginBottom: "1rem" }}>
                <strong style={{ fontSize: "0.9rem" }}>Recognized Food Additives:</strong>
                {ingredientResult.matched_items.length === 0 ? (
                  <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", marginTop: "0.25rem" }}>
                    No additives from the verified reference dataset matched the declaration.
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
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                            {item.additive.canonical_name} ({item.additive.ins_number || item.additive.e_number})
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            Matched from: &ldquo;{item.raw_text}&rdquo;
                          </span>
                        </div>

                        <div style={{ marginTop: "0.25rem", color: "var(--color-text-muted)" }}>
                          <strong>Functional Class:</strong> {item.additive.functional_classes.join(", ")}
                        </div>

                        <div style={{ marginTop: "0.25rem" }}>
                          <strong>Regulatory Status:</strong> {item.additive.regulatory_status}
                        </div>

                        <div style={{ marginTop: "0.25rem", color: "#64748b", fontSize: "0.8rem" }}>
                          <strong>Scope Limitations:</strong> {item.additive.scope_limitations}
                        </div>

                        {item.additive.sources.length > 0 && (
                          <div style={{ marginTop: "0.35rem", fontSize: "0.75rem", color: "#475569" }}>
                            <strong>Official Citations:</strong>{" "}
                            {item.additive.sources.map((s, idx) => (
                              <span key={s.url + idx}>
                                {idx > 0 && " | "}
                                <a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-accent)" }}>
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
                  <strong style={{ fontSize: "0.875rem" }}>Other Declared Ingredients:</strong>
                  <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginTop: "0.25rem", marginBottom: "0.5rem" }}>
                    Preserved exactly as declared on the packaging. Unmatched items are not guessed or altered.
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                    {ingredientResult.unmatched_items.map((token, idx) => (
                      <span
                        key={token + idx}
                        style={{
                          backgroundColor: "#f1f5f9",
                          color: "#334155",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
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
  );
};
