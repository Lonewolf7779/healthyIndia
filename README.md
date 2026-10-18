# healthyIndia

healthyIndia is a mobile-first website concept that helps people understand the nutrition information and ingredients on packaged foods, beginning with Indian consumers.

## Product rules
- Version 1 does not require a paid generative-AI API.
- Nutrition calculations are deterministic Python code.
- Label photos and OCR output are untrusted inputs.
- Missing or uncertain values are never silently guessed or treated as zero.
- The user can review/correct extracted values and use manual entry.
- Product databases are supplemental; the user's package label remains the primary source.
- Explanations and any assessment methodology must cite credible sources and communicate limitations.

## Architecture and security
- [Architecture](docs/ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Security baseline](docs/SECURITY.md)

## Planned stack
- Web: Next.js, TypeScript
- API: Python, FastAPI, Pydantic
- Calculations: pure Python modules with pytest coverage
- OCR: replaceable open-source OCR adapter, selected after evaluating representative labels
- Database: PostgreSQL when persistence is needed
- CI: automated tests, lint/type checks, dependency and secret scanning

## Development status
The repository begins with architecture and security documentation. Application code has not yet been implemented.

## Security
No software can be guaranteed to be impossible to hack. Security requires layered controls, careful implementation, testing, monitoring, and maintenance. Do not deploy publicly until the security acceptance criteria in docs/SECURITY.md are reviewed and met.
