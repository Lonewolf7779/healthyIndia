# healthyIndia

healthyIndia is a mobile-first website concept dedicated to helping Indian consumers understand the nutrition information and ingredients on packaged foods clearly and transparently.

## Product Principles
- **Version 1 does not require a paid generative-AI API:** Calculations are deterministic and rule-based.
- **Pure Python nutrition calculations:** Validated, unit-aware, deterministic Python logic.
- **Untrusted inputs:** Label photos and OCR output are treated as untrusted data.
- **No silent zeros:** Missing or uncertain values are never assumed to be zero or inferred.
- **User agency:** The user can review/correct extracted values and use manual entry.
- **Label is primary source:** External product databases are supplemental; physical package labels remain authoritative.
- **Evidence-backed explanations:** Assessment methodologies cite credible sources (e.g. FSSAI, ICMR, WHO) and communicate limitations.

---

## Technology Stack
- **Web Frontend:** Next.js 15, React 19, TypeScript (strict mode), pnpm.
- **Backend API:** Python 3.13, FastAPI, Pydantic v2, pydantic-settings, uv, Uvicorn.
- **Testing & Quality:** pytest, httpx, vitest, Ruff (formatting, linting, bandit security rules).
- **Containerization & CI:** Docker, Docker Compose, GitHub Actions.

---

## Repository Layout
```text
healthyIndia/
├── apps/
│   └── web/                         # Next.js frontend application
│       ├── src/app/                 # Layouts, landing page, styles
│       ├── src/components/          # Accessible UI components (Header, Footer, StatusBanner)
│       ├── src/features/            # Roadmap modules (scan, manual-entry, results)
│       ├── src/lib/api/             # Typed API client module
│       ├── public/                  # Static assets
│       ├── tests/                   # Frontend unit tests (Vitest)
│       ├── package.json             # Pinned frontend dependencies
│       └── .env.example             # Frontend environment template
├── services/
│   └── api/                         # FastAPI backend application
│       ├── app/
│       │   ├── main.py              # Application factory, middlewares, exception handlers
│       │   ├── api/v1/              # Versioned API routes (/api/v1/health)
│       │   ├── core/                # Settings, logging, security middlewares
│       │   ├── schemas/             # Pydantic request/response schemas
│       │   ├── domain/              # Pure domain models (independent of framework)
│       │   ├── nutrition/           # Deterministic calculation engine
│       │   ├── extraction/          # Replaceable OCR adapter interfaces
│       │   ├── ingredients/         # Curated ingredient definitions
│       │   ├── repositories/        # Persistence adapters
│       │   └── services/            # Business orchestration services
│       ├── migrations/              # Database migration definitions (Phase 2+)
│       ├── tests/                   # Unit, integration, and security test suites
│       ├── pyproject.toml           # Backend project config & tool settings
│       └── .env.example             # Backend environment template
├── data/
│   ├── ingredient_reference/        # Curated, cited ingredient reference data
│   └── fixtures/                    # Synthetic test fixtures
├── infra/
│   ├── docker/                      # Minimal, non-root Dockerfile & .dockerignore
│   └── deployment/                  # Environment guidelines & deployment checklists
├── docs/
│   ├── ARCHITECTURE.md              # Architecture baseline & boundaries
│   ├── SECURITY.md                  # Security baseline & requirements
│   ├── THREAT_MODEL.md              # Assets, threats, mitigations
│   └── API.md                       # API v1 specification & testing
├── .github/
│   └── workflows/ci.yml             # GitHub Actions CI pipeline
├── .gitignore                       # Security-focused ignore rules
├── .editorconfig                    # Cross-editor formatting standards
├── docker-compose.yml               # Local development container orchestration
├── Makefile                         # Unified development targets
└── README.md
```

---

## Prerequisites
- **Node.js:** v20.x or higher
- **pnpm:** v12.x or higher
- **Python:** v3.11 or higher (v3.13 recommended)
- **uv:** v0.6 or higher (`pip install uv`)
- **Tesseract OCR:** v5.x (Local offline engine)
  - *Windows:* `winget install --id UB-Mannheim.TesseractOCR`
  - *Ubuntu/Debian:* `sudo apt-get install -y tesseract-ocr`
- **Docker & Docker Compose:** (Optional, for containerized local development)

---

## Local Setup

### 1. Backend Service
```bash
cd services/api

# Install dependencies using uv lockfile
uv sync

# Configure environment
cp .env.example .env

# Start FastAPI development server
uv run python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend health check is accessible at `http://127.0.0.1:8000/api/v1/health`.

### 2. Frontend Application
```bash
cd apps/web

# Install dependencies using pnpm
pnpm install

# Approve permitted build scripts if prompted
pnpm approve-builds --all

# Configure environment
cp .env.example .env.local

# Start Next.js development server
pnpm run dev
```
Frontend application is accessible at `http://localhost:3000`.

---

## Running Tests & Checks

### Backend (pytest + Ruff)
```bash
cd services/api

# Run all tests (unit, integration, security)
uv run python -m pytest -v

# Run Ruff code analysis & security scan
uv run ruff check .

# Check formatting
uv run ruff format --check .
```

### Frontend (Vitest + TypeScript)
```bash
cd apps/web

# Strict TypeScript type checking
pnpm run type-check

# Run unit tests
pnpm run test

# Test production build
pnpm run build
```

---

## Current Implementation Status
* **Phase 1: Foundation (COMPLETED):**
  * Monorepo structure established.
  * Next.js web application scaffolded with strict TypeScript and accessible landing page.
  * FastAPI backend service scaffolded with versioned router and typed health endpoint.
  * Baseline HTTP security headers (`nosniff`, `DENY`, CSP, `Permissions-Policy`, `X-XSS-Protection`).
  * Restrictive CORS with explicit origins (wildcard origins prohibited in production).
  * Safe error handlers preventing stack trace or path exposure.
  * Non-root containerization and GitHub Actions CI workflow configured.
* **Phase 2A & 2B: Additive & Nutrition Calculation Engines (COMPLETED):**
  * Pure Python deterministic parser matching INS numbers, E numbers, and exact verified aliases.
  * Deterministic nutrition engine comparing labels against ICMR-NIN (2020) and FSSAI guidelines.
  * Missing values tracked explicitly without silent conversion to zero.
  * Unified frontend analyzer supporting product name, serving details, 11 nutrient fields, and ingredient list.
* **Phase 3A & 3B: Local OCR Pipeline & Verification Benchmark (COMPLETED):**
  * Offline, local OCR execution using Tesseract and Pillow (zero paid generative-AI APIs).
  * Defensive image validation against decompression bombs (max 10 MB, max 4096px, max 16 MP).
  * Strict memory-only processing with zero permanent storage of uploaded images.
  * Fail-closed cryptographic session confirmation tokens binding reviewed values.
  * Physical-photo OCR accuracy remains explicitly marked as **`UNMEASURED`**.
* **Phase 4A through 4E: Security Hardening, Dependency Remediation & Release Gates (COMPLETED):**
  * Extensible ingredient knowledge base (`data/ingredient_reference/ingredients_v1.json`, v2.2.0, 21 records across 8 categories).
  * 5-track independent evidence verification framework (URL recorded, URL accessible, content checked, scientific claim supported, regulatory claim verified).
  * Dependency remediation: critical prototype pollution in `tinypool` eliminated via `vitest@4.1.12`; PostCSS patched to `8.5.31`; backend verified clean via `pip-audit`.
  * In-memory sliding-window rate limiting with anti-spoofing trusted proxy logic, thread safety, and memory bounding (HTTP 429 with `Retry-After`).
  * Request payload size limiting defending against negative, oversized, and misleading small Content-Length headers and chunked transfer DoS (HTTP 413).
  * Strict input validation rejecting non-finite numbers (`NaN`, `Infinity`, `-Infinity`).
  * Comprehensive test suite (264 backend tests + 46 frontend tests passing, 0 lint or typecheck errors).

---

## Security Architecture & Deployment Status
* **System Release Status:** **`NOT READY FOR PRODUCTION`** (Physical packaging photograph benchmark remains **`UNMEASURED`**).
* **Comprehensive Security Guide:** See [docs/SECURITY.md](docs/SECURITY.md) for threat modeling, defense-in-depth controls, rate limiting rules, dependency scan findings, and safe vulnerability reporting instructions.
