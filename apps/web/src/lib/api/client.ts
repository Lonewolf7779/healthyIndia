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
  serving_unit?: "g" | "kg" | "ml" | "l" | "piece" | "portion";
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
  data_source?: "manual" | "ocr";
  is_confirmed?: boolean;
  extraction_id?: string | null;
  extraction_token?: string | null;
  confirmed_values_hash?: string | null;
}

export interface OcrConfirmationRequest {
  extraction_id: string;
  extraction_token: string;
  serving_size: number;
  serving_unit?: "g" | "kg" | "ml" | "l" | "piece" | "portion";
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

export interface OcrConfirmationResponse {
  status: string;
  extraction_id: string;
  confirmed_values_hash: string;
  canonical_digest: string;
  user_modified: boolean;
  modified_fields: string[];
  disclaimer: string;
}


function rightRotate(value: number, amount: number): number {
  return (value >>> amount) | (value << (32 - amount));
}

export function sha256Sync(ascii: string): string {
  const maxWord = Math.pow(2, 32);
  let i: number;
  let j: number;
  let result = "";
  const words: number[] = [];
  const asciiBitLength = ascii.length * 8;
  let hash = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  const k = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];

  ascii += "\x80";
  while ((ascii.length % 64) - 56) ascii += "\x00";
  for (i = 0; i < ascii.length; i++) {
    j = ascii.charCodeAt(i);
    words[i >> 2] |= j << (((3 - i) % 4) * 8);
  }
  words[words.length] = (asciiBitLength / maxWord) | 0;
  words[words.length] = asciiBitLength;

  for (j = 0; j < words.length; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = hash;
    hash = hash.slice(0, 8);
    for (i = 0; i < 64; i++) {
      const w15 = w[i - 15];
      const w2 = w[i - 2];
      const a = hash[0];
      const e = hash[4];
      const temp1 =
        (hash[7] +
          (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)) +
          ((e & hash[5]) ^ (~e & hash[6])) +
          k[i] +
          (w[i] =
            i < 16
              ? w[i]
              : (w[i - 16] +
                  (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3)) +
                  w[i - 7] +
                  (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10))) |
                0)) |
        0;
      const temp2 =
        ((rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)) +
          ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]))) |
        0;
      hash = [(temp1 + temp2) | 0].concat(hash);
      hash[4] = (hash[4] + temp1) | 0;
    }
    for (i = 0; i < 8; i++) {
      hash[i] = (hash[i] + oldHash[i]) | 0;
    }
  }

  for (i = 0; i < 8; i++) {
    for (j = 3; j >= 0; j--) {
      const b = (hash[i] >> (8 * j)) & 255;
      result += (b < 16 ? "0" : "") + b.toString(16);
    }
  }
  return result;
}

export function computeNutritionValuesHash(
  servingSize: number,
  servingUnit: string,
  basis: string,
  foodForm: string,
  nutrients: Record<string, number | null | undefined>
): string {
  const items: string[] = [
    `serving_size:${servingSize.toFixed(4)}`,
    `serving_unit:${servingUnit}`,
    `basis:${basis}`,
    `food_form:${foodForm}`,
  ];
  const keys = Object.keys(nutrients).sort();
  for (const k of keys) {
    const v = nutrients[k];
    const valStr = v !== null && v !== undefined ? Number(v).toFixed(4) : "null";
    items.push(`${k}:${valStr}`);
  }
  return sha256Sync(items.join("|"));
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

export interface EverydayExplanation {
  original_value: number | string;
  original_unit: string;
  guidance_type:
    | "actual_serving_quantity"
    | "recommended_dietary_intake"
    | "acceptable_daily_intake"
    | "maximum_permitted_concentration"
    | "exposure_estimate";
  plain_language_summary: string;
  everyday_comparison: string;
  formula?: string | null;
  assumptions: string[];
  reference_source?: string | null;
  limitations_and_uncertainty: string;
  is_conversion_available: boolean;
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
  everyday_explanations?: EverydayExplanation[];
  calculation_assumptions?: Record<string, string>;
}

export interface SourceReference {
  title: string;
  url: string;
  source_type: string;
  retrieval_date: string;
  organization?: string;
  publication_date?: string;
  supported_claims?: string;
  section_or_regulation?: string;
}

export interface AdditiveEntry {
  id: string;
  canonical_name: string;
  entity_type?: string;
  categories?: string[];
  ins_number: string | null;
  e_number: string | null;
  cas_number?: string | null;
  functional_classes: string[];
  jurisdiction: string;
  regulatory_status: string;
  status_verification: string;
  scope_limitations: string;
  chemical_identity?: string;
  health_effects_evidence?: string;
  acceptable_daily_intake?: string;
  population_sensitivities?: string;
  everyday_quantity_explanation?: EverydayExplanation;
  sources: SourceReference[];
}

export interface MatchedIngredient {
  raw_text: string;
  match_type: string;
  confidence: number;
  additive: AdditiveEntry;
  occurrences?: number;
  raw_mentions?: string[];
  is_compound?: boolean;
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
  ambiguous_items?: string[];
  category_summary?: Record<string, number>;
}

export interface ImageQualityMetrics {
  width: number;
  height: number;
  total_pixels: number;
  sharpness_score: number;
  glare_ratio: number;
  mean_luminance: number;
  contrast_std: number;
  estimated_skew_degrees: number;
  min_content_margin_px: number;
}

export interface ImageQualityAssessment {
  is_acceptable: boolean;
  grade: "good" | "fair" | "poor";
  gate_outcome?: "ACCEPT" | "WARN" | "REJECT";
  metrics: ImageQualityMetrics;
  warnings: ExtractionWarning[];
  disclaimer: string;
}

export interface ExtractedNutrientCandidate {
  field_name: string;
  raw_text: string;
  value: number | null;
  unit: string | null;
  confidence: number | null;
  source?: "ocr" | "manual" | "converted";
  status?: "unconfirmed" | "confirmed" | "edited";
  plausibility?: "plausible" | "suspicious" | "contradictory";
  plausibility_warning?: string | null;
  column?: string | null;
}

export interface ExtractionWarning {
  code: string;
  message: string;
}

export interface OcrExtractionResponse {
  raw_text: string;
  pass_a_text?: string | null;
  pass_b_text?: string | null;
  pass_discrepancy?: boolean;
  image_quality?: ImageQualityAssessment | null;
  column_basis_detected?: string;
  nutrition_lines: string[];
  ingredients_text: string | null;
  nutrient_candidates: Record<string, ExtractedNutrientCandidate>;
  per_100_candidates?: Record<string, ExtractedNutrientCandidate>;
  per_serving_candidates?: Record<string, ExtractedNutrientCandidate>;
  serving_size_candidate: number | null;
  serving_unit_candidate: string | null;
  overall_confidence: number | null;
  warnings: ExtractionWarning[];
  verification_required: boolean;
  extraction_id?: string;
  extraction_token?: string;
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

  /**
   * Confirms reviewed OCR values with the server and receives a server-keyed confirmation token.
   */
  public async confirmOcrValues(
    data: OcrConfirmationRequest
  ): Promise<OcrConfirmationResponse> {
    return this.request<OcrConfirmationResponse>("/api/v1/extraction/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
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
