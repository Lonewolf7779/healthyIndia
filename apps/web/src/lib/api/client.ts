/**
 * healthyIndia API Client Module
 *
 * Provides typed access to the healthyIndia backend service.
 * Designed to communicate only over explicit base URLs without leaking internal secrets.
 */

export interface HealthResponse {
  status: string;
  environment: string;
  version: string;
}

export interface NutritionAnalysisRequest {
  serving_size: number;
  serving_unit?: "g" | "ml" | "piece" | "portion";
  basis?: "per_serving" | "per_100g" | "per_100ml";
  food_form?: "solid" | "liquid";
  energy_kcal?: number | null;
  protein_g?: number | null;
  carbohydrates_g?: number | null;
  total_sugar_g?: number | null;
  added_sugar_g?: number | null;
  dietary_fiber_g?: number | null;
  total_fat_g?: number | null;
  saturated_fat_g?: number | null;
  trans_fat_g?: number | null;
  cholesterol_mg?: number | null;
  sodium_mg?: number | null;
}

export interface NutrientComparison {
  nutrient_key: string;
  display_name: string;
  amount: number | null;
  unit: string;
  reference_amount: number | null;
  reference_unit: string | null;
  percentage_of_daily_value: number | null;
  status: string;
  source_citation: string | null;
}

export interface NutritionFlag {
  id: string;
  severity: "info" | "warning" | "alert";
  title: string;
  explanation: string;
  citation: string;
  metadata?: Record<string, unknown>;
}

export interface NutritionAnalysisResponse {
  status: string;
  serving_size: number;
  serving_unit: string;
  food_form: string;
  per_100: Record<string, number | null>;
  per_serving: Record<string, number | null>;
  daily_value_comparisons: NutrientComparison[];
  flags: NutritionFlag[];
  is_complete: boolean;
  missing_nutrients: string[];
  disclaimer: string;
}

export interface SourceReference {
  title: string;
  url: string;
  source_type: string;
  retrieval_date: string;
}

export interface AdditiveEntry {
  id: string;
  canonical_name: string;
  ins_number: string | null;
  e_number: string | null;
  functional_classes: string[];
  jurisdiction: string;
  regulatory_status: string;
  status_verification: string;
  scope_limitations: string;
  sources: SourceReference[];
}

export interface MatchedIngredient {
  raw_text: string;
  match_type: string;
  confidence: number;
  additive: AdditiveEntry;
}

export interface IngredientAnalysisRequest {
  ingredients_text: string;
}

export interface IngredientAnalysisResponse {
  matched_items: MatchedIngredient[];
  unmatched_items: string[];
  total_tokens_detected: number;
  total_matched: number;
  total_unmatched: number;
  disclaimer: string;
}

export interface ExtractedNutrientCandidate {
  field_name: string;
  raw_text: string;
  value: number | null;
  unit: string | null;
  confidence: number | null;
}

export interface ExtractionWarning {
  code: string;
  message: string;
}

export interface OcrExtractionResponse {
  raw_text: string;
  nutrition_lines: string[];
  ingredients_text: string | null;
  nutrient_candidates: Record<string, ExtractedNutrientCandidate>;
  serving_size_candidate: number | null;
  serving_unit_candidate: string | null;
  overall_confidence: number | null;
  warnings: ExtractionWarning[];
  verification_required: boolean;
  disclaimer: string;
}

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status?: number;

  constructor(message: string, code = "API_ERROR", status?: number) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(
    baseUrl: string = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    timeoutMs = 10000
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeoutMs = timeoutMs;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Fetches backend health status.
   */
  public async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/api/v1/health", {
      method: "GET",
    });
  }

  /**
   * Analyzes nutritional panel information deterministically.
   */
  public async analyzeNutrition(
    data: NutritionAnalysisRequest
  ): Promise<NutritionAnalysisResponse> {
    return this.request<NutritionAnalysisResponse>("/api/v1/nutrition/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
  }

  /**
   * Analyzes food ingredients list deterministically against verified reference datasets.
   */
  public async analyzeIngredients(
    data: IngredientAnalysisRequest
  ): Promise<IngredientAnalysisResponse> {
    return this.request<IngredientAnalysisResponse>("/api/v1/ingredients/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
  }

  /**
   * Uploads a food label photo for local offline OCR text and candidate extraction.
   */
  public async extractOcr(file: File): Promise<OcrExtractionResponse> {
    const formData = new FormData();
    formData.append("file", file);

    return this.request<OcrExtractionResponse>("/api/v1/extraction/ocr", {
      method: "POST",
      body: formData,
    });
  }

  private async request<T>(path: string, options: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers: {
          Accept: "application/json",
          ...options.headers,
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorCode = "HTTP_ERROR";
        let errorMessage = `API request failed with status ${response.status}`;

        try {
          const errorBody = await response.json();
          if (errorBody?.error?.code) {
            errorCode = errorBody.error.code;
          }
          if (errorBody?.error?.message) {
            errorMessage = errorBody.error.message;
          }
        } catch {
          // Fallback to default message
        }

        throw new ApiClientError(errorMessage, errorCode, response.status);
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiClientError("Request timed out", "TIMEOUT_ERROR");
      }
      throw new ApiClientError(
        "Unable to connect to healthyIndia API service",
        "NETWORK_ERROR"
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

// Export singleton instance configured for client application
export const apiClient = new ApiClient();
