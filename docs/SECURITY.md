# healthyIndia Security Architecture & Baseline

**Document Version**: 2.1.0  
**Phase**: 4E — Dependency Remediation, Security Verification, and Release-Gate Review  
**Date**: October 19, 2026  
**System Production Status**: **NOT READY FOR PRODUCTION** (Physical OCR benchmark remains **UNMEASURED**)  

---

## 1. Threat Model & Trust Boundaries

healthyIndia evaluates packaged food labels against Indian statutory standards (FSSAI) and dietary references (ICMR-NIN). The application processes untrusted client inputs and food packaging images.

```mermaid
flowchart LR
    subgraph Client ["Untrusted Client Boundary"]
        Browser["User Browser / Mobile Device"]
    end

    subgraph Edge ["Edge / Reverse Proxy (Production Target)"]
        Nginx["TLS Termination / Edge Rate Limiting / WAF"]
    end

    subgraph FrontendApp ["Frontend Application"]
        Next["Next.js 15 (SSR / Static Assets)"]
    end

    subgraph BackendApp ["Backend Application"]
        API["FastAPI Backend (Python 3.13)"]
        Middleware["Security Headers / Rate Limiter / Size Limiter"]
        Validator["Pydantic Schemas / Non-Finite Float Guards"]
        Vision["Pillow / OpenCV Quality Gates & Decompression Bomb Guard"]
        Engine["Deterministic Nutrition & Ingredient Engines"]
        OCR["Local Tesseract OCR Engine (Untrusted Input Source)"]
    end

    Browser -->|HTTPS| Nginx
    Nginx --> Next
    Nginx --> API
    API --> Middleware
    Middleware --> Validator
    Validator --> Engine
    API --> Vision
    Vision --> OCR
    OCR -.->|Untrusted Raw Text| Validator
```

### Trust Boundary Rules
1. **Client is Untrusted**: All data originating from the client (web browser, mobile device, or API client) is treated as potentially adversarial. No client-side assertion or validation is trusted by the backend.
2. **OCR Output is Untrusted**: Text produced by optical character recognition (OCR) is machine-generated draft text. It is never treated as authoritative nutrition data until the user inspects, verifies, and confirms the values through an authenticated session.
3. **Deterministic Separation**: Nutrition calculations and ingredient matching are pure, deterministic Python evaluations. No generative AI or probabilistic cloud APIs are used, preventing prompt injection, hallucinated claims, or unpredictable safety evaluations.

---

## 2. Implemented Defense-in-Depth Controls

### A. Input Validation & Mathematical Plausibility
- **Strict Pydantic V2 Schemas**: All JSON request bodies are validated against rigid schemas (`NutritionAnalysisRequest`, `IngredientAnalysisRequest`, `OcrConfirmationRequest`).
- **Non-Finite Numerical Rejection**: Non-finite float values (`NaN`, `Infinity`, `-Infinity`) are explicitly rejected fail-closed on all numeric fields (serving sizes, nutrient amounts).
- **Physical & Biological Plausibility Checks**:
  - Nutrients cannot be negative.
  - Added sugar cannot exceed total sugar (+ 0.05g tolerance).
  - Total sugar cannot exceed total carbohydrates (+ 0.05g tolerance).
  - Sum of saturated and trans fats cannot exceed total fat (+ 0.05g tolerance).
  - Macronutrient sum cannot exceed 105g on a 100g serving basis.
  - Energy must be plausible relative to declared fat calories (min 8.0 kcal/g fat).
- **Missing vs. Zero Distinction**: Omitted nutrients are preserved as `None` rather than silently defaulted to `0.0`.

### B. Upload & Image Processing Security
- **Strict Size Limits**: Uploaded image payloads are capped at 10 MB (`MAX_IMAGE_UPLOAD_BYTES = 10_485_760`).
- **Content-Based Magic Byte & Structure Verification**: Files are verified using Pillow's `Image.open().verify()` and format detection; client-supplied filenames, extensions, and Content-Type headers are strictly untrusted.
- **Authorized Formats Only**: Allowed formats are restricted to `{"JPEG", "PNG", "WEBP"}`. Executables, scripts, HTML, and vector SVGs are rejected.
- **Decompression Bomb Protection**: Pillow's pixel limit is enforced globally at 16 Megapixels (`Image.MAX_IMAGE_PIXELS = 16_000_000`, `MAX_IMAGE_DIMENSION = 4096`).
- **Disk Retention Lifecycle**:
  - Image payloads <= 1 MB remain strictly in-memory buffers (`io.BytesIO`).
  - Multipart uploads > 1 MB are transiently spooled to an OS temporary file by Starlette's `SpooledTemporaryFile` during multipart body parsing, and are unlinked immediately when the request finishes.
  - No permanent application disk retention exists.
- **No Upload Logging**: Image byte contents, EXIF metadata, and user photos are never written to log files.

### C. API Abuse, Rate Limiting & Request Sizing
- **Thread-Safe In-Memory Sliding-Window Rate Limiter**:
  - Protected by `threading.Lock()` against concurrent race conditions.
  - Bounded memory usage: enforces `max_tracked_clients` with automatic pruning and FIFO eviction of stale client records.
  - Route limits:
    - `/api/v1/extraction/ocr`: 10 requests / minute (heavy local OCR execution)
    - `/api/v1/extraction/confirm`: 30 requests / minute
    - `/api/v1/nutrition/analyze`: 60 requests / minute
    - `/api/v1/ingredients/analyze`: 60 requests / minute
    - General endpoints: 120 requests / minute
- **Anti-Spoofing Client IP Resolution**:
  - `X-Forwarded-For` and `CF-Connecting-IP` headers are **strictly ignored** unless the direct connecting IP address matches a trusted reverse proxy configured in `TRUSTED_PROXIES`.
  - Untrusted clients cannot evade rate limits by rotating forwarded headers.
- **HTTP 429 Responses**: Returns structured JSON error responses with standard `Retry-After` and `X-RateLimit-Remaining` headers.
- **CORS Preflight Bypass**: `OPTIONS` requests are exempt from rate limiting to prevent blocking legitimate cross-origin preflight checks.
- **Request Size Limiting & Streaming Body Bounds**:
  - Standard JSON endpoints are bounded at 1 MB (`MAX_REQUEST_BODY_BYTES = 1_048_576`).
  - Defends against negative `Content-Length` headers (HTTP 400).
  - Defends against misleading small `Content-Length` headers by enforcing running byte limits during stream consumption (HTTP 413).
  - Chunked streaming bodies without `Content-Length` headers are incrementally byte-counted and rejected with HTTP 413 if the limit is exceeded.
  - Handles `ClientDisconnect` safely without 500 server errors.

### D. Session Integrity & Cryptographic Tokens
- **Fail-Closed Session Confirmation**: Confirming reviewed OCR values requires an active, unexpired server session stored in `session_store`. Expired or missing sessions return HTTP 404/400.
- **Server-Keyed HMAC Signatures**:
  - Extraction session token: `v1.<id>.<ts>.<sig>`
  - Confirmation token: `c1.<id>.<digest>.<ts>.<sig>`
  - Uses `hmac.compare_digest` for constant-time string comparison to prevent timing side-channel attacks.
  - Validates canonical UUID structure on all extraction identifiers.
  - Cryptographically binds the canonical SHA-256 digest of confirmed nutrition values to the extraction ID and server secret key. Client tampering alters the expected digest and fails server-side verification.

### E. Browser Security, CORS, and Headers
- **Backend API Security Headers Middleware**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';` (API never renders HTML or executes scripts)
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
  - `X-XSS-Protection: 0`
  - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` (enforced in production)
- **Frontend Web Security Headers (`next.config.mjs`)**:
  - `Content-Security-Policy`:
    ```
    default-src 'self';
    script-src 'self' 'unsafe-inline';
    style-src 'self' 'unsafe-inline';
    img-src 'self' blob: data:;
    font-src 'self';
    connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 https://healthyindia.com;
    frame-ancestors 'none';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    ```
    - `img-src 'self' blob: data:` explicitly permits local client-side image preview URLs generated by the camera scanner without allowing untrusted third-party images.
  - `Permissions-Policy: camera=(self), microphone=(), geolocation=()` to permit HTML5 camera capture while disabling unused device sensors.
- **Restrictive CORS**:
  - Configurable `ALLOWED_ORIGINS` (defaults to local development origins).
  - Wildcard `*` is strictly prohibited in production and staging.
  - Localhost origins (`localhost`, `127.0.0.1`) are prohibited when `ENVIRONMENT=production`.
  - `allow_credentials=False` (anonymous API).

### F. Configuration & Secrets
- **Environment Isolation**:
  - In production and staging, `DEBUG` must be `False`.
  - `SECRET_KEY` must be at least 32 characters and cannot contain insecure placeholder words (`insecure`, `changeme`, `default`).
  - Interactive OpenAPI documentation (`/docs`, `/redoc`, `/openapi.json`) is disabled in production by default.

---

## 3. Dependency Security Audit & Remediation (Phase 4E)

### Frontend Audit Results (`pnpm audit`)

| Advisory ID | Package | Vulnerable Range | Severity | Status in Phase 4E | Remediation / Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GHSA-5gmw-xhrv-c9v3** | `tinypool` | `<=2.1.0` | **Critical** | **RESOLVED** | Upgraded to `vitest@4.1.12`, which completely removes `tinypool` in favor of native worker threads and tinyexec. |
| **GHSA-85c8-ppgw-ccpr** | `tinypool` | `<2.1.2` | **Critical** | **RESOLVED** | Upgraded to `vitest@4.1.12` (tinypool removed from dependency graph). |
| **GHSA-82fw-gwwq-j7x9** | `vitest` / `@vitest/mocker` | `>=2.1.0 <4.1.11` | Moderate | **RESOLVED** | Upgraded to `vitest@4.1.12` (includes `@vitest/mocker@4.1.12`). |
| **GHSA-qx2v-qp2m-jg93** | `postcss` | `<8.5.10` | Moderate | **RESOLVED** | Overridden to `postcss@8.5.31` in `pnpm-workspace.yaml`. |
| **GHSA-6g55-p6wh-862q** | `postcss` | `<=8.5.11` | High | **RESOLVED** | Overridden to `postcss@8.5.31` in `pnpm-workspace.yaml`. |
| **GHSA-fxqj-rqcc-2cmp** | `postcss` | `<=8.5.22` | Moderate | **RESOLVED** | Overridden to `postcss@8.5.31` in `pnpm-workspace.yaml`. |
| **GHSA-r28c-9q8g-f849** | `postcss` | `<=8.5.17` | High | **RESOLVED** | Overridden to `postcss@8.5.31` in `pnpm-workspace.yaml`. |
| **GHSA-vfj7-8cjw-p6xm** | `braces` | `<=3.0.3` | High | **Accepted with Justification** | Transitive dev dependency via `eslint-config-next` (`micromatch -> braces`). Upstream npm registry has no published patched version (`patched_versions: None`). Used strictly during local linting; never executed in production client bundle or server runtime. |

### Backend Python Audit Results (`pip-audit`)
- Tool: `pip-audit` via official PyPI vulnerability database.
- Packages audited: 28 installed packages in backend environment.
- Result: **`No known vulnerabilities found`**.

---

## 4. Knowledge Base Evidence Validator Scope & Boundaries

The automated knowledge base validator (`validate_ingredient_kb.py`) performs deterministic **structural, schema, and lexical verification**:
- **What the automated validator proves**:
  1. Record completeness: all mandatory fields, categories, and identifiers (INS, CAS) are structurally valid and collision-free.
  2. Domain allowlisting: citation URLs belong to recognized public health and regulatory domains (`fssai.gov.in`, `who.int`, `efsa.europa.eu`, `nih.gov`, `codexalimentarius.org`).
  3. Anti-hyperbole rules: prohibits absolute safety assertions ("100% safe", "completely harmless").
  4. Statutory reference completeness: food additives declare mandatory scope limitations and specific statutory acts.
- **What the automated validator does NOT prove**:
  1. It does not perform live network fetching during CI to verify HTTP server response status codes.
  2. It does not replace human domain expertise in evaluating biochemical toxicological reality or legal interpretations of FSSAI schedules.
  3. Provenance flags (`source_content_checked`, `scientific_review_status`, `regulatory_verification_status`) record the completion of manual verification by food-science auditors; they are validated for schema integrity, not computationally generated.

---

## 5. Known Limitations & Residual Risks

1. **Multi-Worker Rate Limiting**: The current in-memory sliding window rate limiter operates within a single Python process. In a distributed multi-worker deployment, an edge reverse proxy (such as Nginx `limit_req` or Cloudflare WAF) or a shared Redis token bucket must be configured to enforce cluster-wide IP rate limits.
2. **Physical OCR Performance**: As benchmarked against synthetic and digital fixture data, physical camera label OCR accuracy remains **UNMEASURED**. OCR must remain strictly an untrusted convenience feature requiring full human verification and manual correction.
3. **Session Store Volatility**: The default in-memory session store resets on application restart. Persistent distributed session stores (e.g., Redis with encryption in transit) are required for high-availability clustered deployments.

---

## 6. Safe Vulnerability Reporting

If you identify a security vulnerability in healthyIndia:
1. **Do not open a public issue** on GitHub.
2. Report the vulnerability privately via GitHub Private Vulnerability Reporting or to project maintainers.
3. Include detailed reproduction steps, request payloads, and affected component versions.
4. Maintain coordinated disclosure until an audited patch has been released.
