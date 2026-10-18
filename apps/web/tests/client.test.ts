import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClient, ApiClientError } from "../src/lib/api/client";

describe("ApiClient", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("normalizes base URL by stripping trailing slashes", () => {
    const client = new ApiClient("http://localhost:8000///");
    expect(client.getBaseUrl()).toBe("http://localhost:8000");
  });

  it("fetches health status successfully", async () => {
    const mockHealth = {
      status: "ok",
      environment: "test",
      version: "0.1.0",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockHealth,
    });

    const client = new ApiClient("http://localhost:8000");
    const result = await client.getHealth();

    expect(result).toEqual(mockHealth);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/health",
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      })
    );
  });

  it("throws ApiClientError on non-200 HTTP response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({
        error: {
          code: "INTERNAL_SERVER_ERROR",
          message: "Internal server error",
        },
      }),
    });

    const client = new ApiClient("http://localhost:8000");
    await expect(client.getHealth()).rejects.toThrow(ApiClientError);
  });

  it("handles network failure cleanly", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Connection refused"));

    const client = new ApiClient("http://localhost:8000");
    await expect(client.getHealth()).rejects.toThrow(
      "Unable to connect to healthyIndia API service"
    );
  });

  it("calls analyzeNutrition endpoint with payload", async () => {
    const mockResponse = {
      status: "complete",
      serving_size: 30,
      serving_unit: "g",
      food_form: "solid",
      per_100: { added_sugar_g: 20 },
      per_serving: { added_sugar_g: 6 },
      daily_value_comparisons: [],
      flags: [],
      is_complete: true,
      missing_nutrients: [],
      disclaimer: "test",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const client = new ApiClient("http://localhost:8000");
    const result = await client.analyzeNutrition({
      serving_size: 30,
      added_sugar_g: 6,
    });

    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/nutrition/analyze",
      expect.objectContaining({
        method: "POST",
      })
    );
  });

  it("calls analyzeIngredients endpoint with payload", async () => {
    const mockResponse = {
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
            regulatory_status: "Permitted under GMP; prohibited in infant foods",
            status_verification: "verified",
            scope_limitations: "Prohibited in foods intended for infants below 12 months",
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
      unmatched_items: ["Wheat Flour", "Palm Oil"],
      total_tokens_detected: 3,
      total_matched: 1,
      total_unmatched: 2,
      disclaimer: "Deterministic additive reference comparison.",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const client = new ApiClient("http://localhost:8000");
    const result = await client.analyzeIngredients({
      ingredients_text: "Wheat Flour, Palm Oil, Flavour Enhancer (INS 621)",
    });

    expect(result).toEqual(mockResponse);
    expect(result.matched_items[0].additive.canonical_name).toBe("Monosodium Glutamate (MSG)");
    expect(result.unmatched_items).toEqual(["Wheat Flour", "Palm Oil"]);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/ingredients/analyze",
      expect.objectContaining({
        method: "POST",
      })
    );
  });
});

