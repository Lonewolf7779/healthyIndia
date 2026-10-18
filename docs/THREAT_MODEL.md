# healthyIndia Initial Threat Model

## Assets to protect
- Application availability and integrity
- Nutrition calculations and rule/reference-data integrity
- User-uploaded label images and submitted data
- Database credentials, deployment secrets, and admin privileges
- User trust: the application must not produce confidently wrong assessments from uncertain input

## Trust boundaries
- Browser/user input -> public API
- Uploaded image -> decoder/OCR processing
- API service -> database/reference data
- CI pipeline -> build artifact -> deployment environment
- Administrators/reference-data maintainers -> curated content

## Threats and mitigations
- Oversized or malformed uploads exhaust memory/CPU: strict byte/pixel limits, format allow-list, timeouts, resource limits, rate limits, adversarial test cases.
- OCR confusion or malicious label text produces wrong results: treat all extracted text as untrusted input; schema validation, bounds, plausibility checks, provenance, confidence thresholds, human correction; no arbitrary execution.
- API abuse and denial of service: rate limits, request size/time limits, throttling, monitoring, sensible quotas, autoscaling/hosting controls.
- Injection attacks: parameterized DB access, output encoding, strict input schemas, no dynamic evaluation or shell interpolation.
- Cross-site scripting: framework escaping, no unsafe HTML rendering, restrictive CSP, sanitize any future rich content.
- CSRF/session misuse if authentication is added: secure cookie configuration, CSRF tokens/origin checks, session rotation and expiration.
- Secret exposure: environment-managed secrets, secret scanning, least privilege, no secrets in frontend variables or logs.
- Supply-chain compromise: lock files, dependency scanning, minimal dependencies, reviewed updates, protected CI workflows.
- Unauthorized admin or data edits: no hidden bypasses, server-side authorization on every privileged endpoint, audit trail.
- Data leakage: do not retain images by default, minimize logs, explicit retention and deletion policies before storage is introduced.
- Reference data corruption or stale sources: versioned data, source attribution, review process, regression tests, rollback capability.
- Incorrect health claims: evidence-backed transparent rules, versioned methodology, communicate limitations, do not diagnose or prescribe.

## Open decisions before production
- Hosting provider, upload/storage policy, and rate-limit implementation.
- Whether user accounts will exist; avoid accounts for MVP unless needed.
- Data retention and privacy notice, including image processing.
- Reference-value sources and assessment methodology, including review/approval.
- Incident response contact, backups, restore process, and monitoring/alerting.
- Domain purchase and DNS/TLS setup for healthyIndia.com (availability/ownership must be verified separately).

## Security acceptance rule
The system is not "unhackable." It is ready for public beta only after threat-driven tests, dependency/secret scans, safe upload handling, rate limiting, access-control checks, and production configuration review pass.
