# healthyIndia API Specification (v1)

## Overview
The healthyIndia backend provides a versioned, secure REST API built with FastAPI and Pydantic.

- **Local Address:** `http://127.0.0.1:8000`
- **Base Route:** `/api/v1`
- **Data Format:** JSON (`application/json`)

---

## Baseline Security Headers
All API responses include defensive HTTP security headers:
* `X-Content-Type-Options: nosniff`
* `X-Frame-Options: DENY`
* `Referrer-Policy: strict-origin-when-cross-origin`
* `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';`
* `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`

---

## Endpoints

### 1. Health Probe
Returns service health, deployment environment, and API version. Unauthenticated probe suitable for container orchestrators and frontend connectivity checks.

* **Method:** `GET`
* **Path:** `/api/v1/health`
* **Query Parameters:** None
* **Request Body:** None

#### Response (200 OK)
```json
{
  "status": "ok",
  "environment": "local",
  "version": "0.1.0"
}
```

#### Response Schema
| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | string | Health indicator (e.g. `"ok"`) |
| `environment` | string | Active environment (`"local"`, `"test"`, `"staging"`, or `"production"`) |
| `version` | string | Semantic version of the API |

---

### 2. Deterministic Nutrition Analysis
Analyzes nutritional panel data against FSSAI (2020) and ICMR-NIN (2020) guidelines. Missing values are preserved as `null` and never converted to zero.

* **Method:** `POST`
* **Path:** `/api/v1/nutrition/analyze`
* **Headers:** `Content-Type: application/json`

#### Example Request
```json
{
  "serving_size": 30.0,
  "serving_unit": "g",
  "basis": "per_serving",
  "food_form": "solid",
  "energy_kcal": 140.0,
  "protein_g": 3.0,
  "carbohydrates_g": 20.0,
  "total_sugar_g": 10.0,
  "added_sugar_g": 8.0,
  "dietary_fiber_g": 2.0,
  "total_fat_g": 6.0,
  "saturated_fat_g": 3.0,
  "trans_fat_g": 0.0,
  "sodium_mg": 240.0
}
```

#### Example Response (200 OK)
```json
{
  "status": "complete",
  "serving_size": 30.0,
  "serving_unit": "g",
  "food_form": "solid",
  "per_100": {
    "energy_kcal": 466.67,
    "protein_g": 10.0,
    "carbohydrates_g": 66.67,
    "total_sugar_g": 33.33,
    "added_sugar_g": 26.67,
    "total_fat_g": 20.0,
    "saturated_fat_g": 10.0,
    "trans_fat_g": 0.0,
    "sodium_mg": 800.0,
    "dietary_fiber_g": 6.67,
    "cholesterol_mg": null
  },
  "per_serving": {
    "energy_kcal": 140.0,
    "protein_g": 3.0,
    "carbohydrates_g": 20.0,
    "total_sugar_g": 10.0,
    "added_sugar_g": 8.0,
    "total_fat_g": 6.0,
    "saturated_fat_g": 3.0,
    "trans_fat_g": 0.0,
    "sodium_mg": 240.0,
    "dietary_fiber_g": 2.0,
    "cholesterol_mg": null
  },
  "daily_value_comparisons": [
    {
      "nutrient_key": "added_sugar_g",
      "display_name": "Added Sugar",
      "amount": 8.0,
      "unit": "g",
      "reference_amount": 50.0,
      "reference_unit": "g",
      "percentage_of_daily_value": 16.0,
      "status": "calculated",
      "source_citation": "FSSAI / WHO Guideline (Max 10% of total daily energy)"
    }
  ],
  "flags": [
    {
      "id": "high_added_sugar",
      "severity": "warning",
      "title": "High in Added Sugar",
      "explanation": "Contains 26.67g of added sugar per 100g, exceeding the FSSAI HFSS threshold of 10.0g/100g.",
      "citation": "FSSAI Labelling Regulations (HFSS draft schedule)",
      "metadata": { "measured_per_100": 26.67, "threshold": 10.0 }
    }
  ],
  "is_complete": true,
  "missing_nutrients": [],
  "disclaimer": "healthyIndia calculations are deterministic comparisons..."
}
---

### 3. Food Additive & Ingredient Analysis
Parses declared ingredient strings deterministically against curated FSSAI/Codex additive reference data. Identifies functional classes, regulatory scopes, and source citations without probabilistic guessing.

* **Method:** `POST`
* **Path:** `/api/v1/ingredients/analyze`
* **Headers:** `Content-Type: application/json`

#### Example Request
```json
{
  "ingredients_text": "Wheat Flour, Palm Oil, Salt, Emulsifier (INS 322(i)), Preservative (INS 211)"
}
```

#### Example Response (200 OK)
```json
{
  "matched_items": [
    {
      "raw_text": "Emulsifier (INS 322(i))",
      "match_type": "ins_number",
      "confidence": 1.0,
      "additive": {
        "id": "ins-322",
        "canonical_name": "Lecithins",
        "ins_number": "INS 322",
        "e_number": "E 322",
        "functional_classes": ["Emulsifier", "Stabilizer", "Antioxidant"],
        "jurisdiction": "India (FSSAI) & Codex Alimentarius",
        "regulatory_status": "Permitted under Good Manufacturing Practice (GMP) in various food formulations; must declare botanical source if derived from major allergens.",
        "status_verification": "verified",
        "scope_limitations": "General food usage subject to GMP standards.",
        "sources": [
          {
            "title": "FSSAI Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011",
            "url": "https://www.fssai.gov.in",
            "source_type": "Statutory Regulation",
            "retrieval_date": "2026-10-18"
          }
        ]
      }
    }
  ],
  "unmatched_items": [
    "Wheat Flour",
    "Palm Oil",
    "Salt"
  ],
  "total_tokens_detected": 5,
  "total_matched": 2,
  "total_unmatched": 3,
  "disclaimer": "healthyIndia additive matching is deterministic..."
}
```

---

### 4. Local Food-Label OCR Extraction
Extracts raw text, identifies nutrition facts lines, extracts candidate ingredients statements, and parses draft nutrient candidates from an uploaded food label image using local, offline Tesseract OCR.

* **Method:** `POST`
* **Path:** `/api/v1/extraction/ocr`
* **Content-Type:** `multipart/form-data`
* **Form Field:** `file` (Binary image file)

#### Supported Formats & Upload Limits
* **Formats:** JPEG (`.jpg`, `.jpeg`), PNG (`.png`), WEBP (`.webp`).
* **Max Payload Size:** 10 MB (`MAX_IMAGE_UPLOAD_BYTES: 10485760`).
* **Max Dimensions:** 4096 x 4096 pixels.
* **Max Pixel Density:** 16,000,000 pixels (decompression bomb protection).
* **Privacy & Retention:** Processed purely in memory. Images are **never permanently stored** on disk or logged.

#### Example Request
```bash
curl -X POST http://127.0.0.1:8000/api/v1/extraction/ocr \
  -F "file=@packaging_label.jpg;type=image/jpeg"
```

#### Example Response (200 OK)
```json
{
  "raw_text": "NUTRITION FACTS\nServing Size: 30g\nEnergy: 145 kcal\nProtein: 2.5g\nCarbohydrates: 21g\nAdded Sugars: 7.5g\nTotal Fat: 6g\nSodium: 180mg\nINGREDIENTS: Wheat Flour, Palm Oil, Salt, Emulsifier (INS 322(i))",
  "nutrition_lines": [
    "Serving Size: 30g",
    "Energy: 145 kcal",
    "Protein: 2.5g",
    "Carbohydrates: 21g",
    "Added Sugars: 7.5g",
    "Total Fat: 6g",
    "Sodium: 180mg"
  ],
  "ingredients_text": "Wheat Flour, Palm Oil, Salt, Emulsifier (INS 322(i))",
  "nutrient_candidates": {
    "energy_kcal": {
      "field_name": "energy_kcal",
      "raw_text": "Energy: 145 kcal",
      "value": 145.0,
      "unit": "kcal",
      "confidence": 92.0
    },
    "added_sugar_g": {
      "field_name": "added_sugar_g",
      "raw_text": "Added Sugars: 7.5g",
      "value": 7.5,
      "unit": "g",
      "confidence": 92.0
    }
  },
  "serving_size_candidate": 30.0,
  "serving_unit_candidate": "g",
  "overall_confidence": 92.0,
  "warnings": [],
  "verification_required": true,
  "disclaimer": "OCR extraction is preliminary and machine-generated. Physical print quality, lighting, reflections, or packaging folds may cause errors. The user must review, verify, and correct all values before submission."
}
```

---

## Error Responses
Error responses follow a consistent, safe structure without leaking internal stack traces or filesystem paths.

### 404 Not Found
```json
{
  "error": {
    "code": "HTTP_ERROR",
    "message": "Not Found"
  }
}
```

### 413 Payload Too Large
Triggered when request payload exceeds `MAX_REQUEST_BODY_BYTES` (default: 1 MB):
```json
{
  "error": {
    "code": "PAYLOAD_TOO_LARGE",
    "message": "Request body exceeds limit of 1048576 bytes."
  }
}
```

### 422 Validation Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request payload failed schema validation.",
    "details": [ ... ]
  }
}
```

### 500 Internal Server Error
Internal server errors log diagnostic tracebacks on the server while returning a generic message to the client:
```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred. Please try again later."
  }
}
```

---

## Running API Tests
Tests are located in `services/api/tests/` and managed with `uv` and `pytest`:

```bash
cd services/api

# Run entire test suite (unit, integration, security)
uv run python -m pytest -v

# Run only security tests
uv run python -m pytest tests/security -v

# Run linting and format checks
uv run ruff check .
uv run ruff format --check .
```
