# healthyIndia Architecture

## Product principles
- Version 1 does not depend on a paid generative-AI API.
- Nutrient calculations are deterministic, unit-aware, validated Python code.
- Unknown or missing values must never be silently treated as zero or inferred.
- User-provided package labels are the primary source; external product databases are supplementary and must retain provenance.
- A failed or uncertain extraction must ask for correction or manual entry, not provide a falsely confident result.
- This document is a baseline architecture, not a claim that the application is already secure or production-ready.

## Proposed monorepo
```text
healthyIndia/
├── apps/
│   └── web/                         # Next.js + TypeScript frontend
│       ├── src/app/                 # Pages, layouts, route handlers only when needed
│       ├── src/components/          # Accessible reusable UI
│       ├── src/features/            # scan, manual-entry, results
│       ├── src/lib/api/             # Typed backend client
│       ├── public/
│       ├── tests/
│       ├── package.json
│       └── .env.example
├── services/
│   └── api/                         # Python + FastAPI backend
│       ├── app/
│       │   ├── main.py              # App construction and router registration
│       │   ├── api/v1/              # Versioned HTTP endpoints
│       │   ├── core/                # Settings, logging, security headers
│       │   ├── schemas/              # Pydantic request/response models
│       │   ├── domain/               # Pure domain models and business rules
│       │   ├── nutrition/            # Deterministic calculations and rule engine
│       │   ├── extraction/           # OCR interface and implementations
│       │   ├── ingredients/          # Curated ingredient explanations
│       │   ├── repositories/         # Persistence interfaces/adapters
│       │   └── services/             # Orchestration, no business logic in routes
│       ├── migrations/
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── security/
│       ├── pyproject.toml
│       └── .env.example
├── packages/
│   └── contracts/                   # Shared API schemas/specification if justified
├── data/
│   ├── ingredient_reference/         # Curated, cited, versioned source data only
│   └── fixtures/                    # Synthetic/public test fixtures, not secrets
├── infra/
│   ├── docker/                       # Non-root, minimal, pinned runtime images
│   └── deployment/                   # Environment-specific config, no secrets
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── THREAT_MODEL.md
│   └── API.md
├── .github/
│   └── workflows/                    # CI checks and dependency/security scanning
├── .gitignore
├── .editorconfig
├── .gitattributes
├── .pre-commit-config.yaml           # Add when tools are selected
├── docker-compose.yml               # Local development only
├── Makefile                          # Standard local commands
└── README.md
```

## Architectural boundaries
1. Frontend communicates with the backend over HTTPS using a versioned JSON API.
2. HTTP route handlers only authenticate/validate requests, call services, and return typed responses.
3. Nutrition calculations live in pure Python modules independent of FastAPI, OCR, database, and network.
4. OCR is a replaceable adapter. Extracted fields must retain raw text, normalized value, unit, label basis, extraction confidence, and whether a person confirmed them.
5. Product matching is separate from label extraction; a database match never silently overrides the user's observed label.
6. Reference data must include source, version/retrieval date, and license/usage notes where applicable.
7. No public upload is persisted by default. If persistence is later needed, it requires explicit retention rules and access controls.
8. Start as a modular monolith. Do not add microservices, queues, or caches until measured need exists.

## Environments
- Local: non-production sample data, separate local database, no production secrets.
- CI/test: ephemeral databases and synthetic fixtures; least-privilege test credentials.
- Staging: separate credentials, database, storage, and hostname from production.
- Production: managed secrets, restricted database networking, TLS, backups, monitoring, and documented recovery.
- Never commit .env files, credentials, private keys, user uploads, or database dumps. Commit only .env.example with fake placeholders.
- Fail application startup when mandatory production secrets/configuration are absent or insecure; do not silently use development defaults in production.

## Security baseline
- Validate inputs with strict schemas and explicit bounds. Reject unknown/invalid units and impossible serving sizes rather than guessing.
- Uploads: allow-list raster image formats; verify content rather than trusting extension/MIME alone; cap bytes and decoded pixel dimensions; reject SVG/HTML, corrupted files, decompression bombs, and unsupported formats; randomize storage names; do not execute uploaded content.
- Keep upload processing isolated and resource-limited; use timeouts; avoid permanent storage; do not expose local paths or raw internal errors.
- Rate-limit upload and expensive endpoints per IP/session, apply request size/time limits, and return 429 where appropriate.
- Do not log uploaded images, full nutrition submissions, cookies, authorization headers, secrets, or unnecessary personal data.
- Configure restrictive CORS for known deployed origins only. Do not use wildcard origins with credentials.
- Apply security headers including Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, and an appropriate frame policy. Enable HSTS only when HTTPS is correctly configured.
- Prevent SQL injection through parameterized ORM/database APIs. Never build SQL from raw user strings.
- Keep dependencies minimal and pinned/lock-file managed; scan dependency vulnerabilities; update dependencies deliberately.
- Run containers/processes as non-root, use read-only filesystems where practical, drop unnecessary privileges, and never embed secrets in images or frontend bundles.
- Separate public configuration from server-only secrets. Any NEXT_PUBLIC_* value is public.
- Enforce authentication and authorization on all non-public administrative/data-management operations. Do not build an admin bypass or hardcoded credentials.
- Use generic public error messages; detailed diagnostics belong in protected server logs.
- Add CSRF protection for cookie-authenticated state-changing routes; secure cookies with HttpOnly, Secure, and appropriate SameSite settings.
- Use HTTPS in deployment, least-privilege service accounts, database not publicly exposed, backups, and restore tests.
- Add audit events for privileged changes without recording sensitive content.
- No claim of being "unhackable" is valid. Security is layered, tested, monitored, and continuously maintained.

## Quality gates
- Unit and integration tests run in CI.
- Nutrition tests cover units, serving conversions, missing values, rounding, limits, and reference-rule versions.
- Security tests cover malformed/oversized images, invalid data, rate-limit behavior, authorization, and safe errors.
- Format/lint/type-check both web and API; scan dependencies and secrets.
- Production deploys only from reviewed, green builds. Use branch protection and protected secrets in GitHub Actions.
- Never deploy directly from unreviewed experimental branches.
