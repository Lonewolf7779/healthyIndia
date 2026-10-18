# healthyIndia Security Baseline

This is a baseline for implementation and review, not a security certification.

## Required before public beta
- [ ] Threat model reviewed and updated as features change.
- [ ] Production secrets are stored only in the hosting provider's secret manager.
- [ ] HTTPS enabled; database has no public inbound access unless explicitly justified.
- [ ] CORS permits only known production/staging frontend origins.
- [ ] Upload endpoint has byte, pixel, format, concurrency, and time limits.
- [ ] Uploaded images are processed as untrusted data and not retained by default.
- [ ] Public endpoints have rate limits and request-body limits.
- [ ] Strict request and response schemas; missing values are not converted to zero.
- [ ] Generic client errors; sensitive data and credentials are never logged.
- [ ] Dependency lockfiles and automated vulnerability/secret scanning are in CI.
- [ ] Unit, integration, and security tests pass on the exact release commit.
- [ ] Database backups and restoration are tested if persistent production data exists.
- [ ] Admin and maintenance actions have server-side authorization.
- [ ] Privacy notice and data-retention policy match actual behavior.
- [ ] Release reviewed by a person; no automatic production deployment from arbitrary branches.

## Secure development rules
1. Never commit secrets, tokens, private keys, production data, real user uploads, or .env files.
2. Never trust client-side validation alone.
3. Never trust filename, extension, or Content-Type alone when validating an upload.
4. Never execute OCR output, user input, filenames, or database content as code or shell commands.
5. Never expose stack traces, filesystem paths, SQL errors, or secret configuration to clients.
6. Never use permissive CORS with credentials.
7. Never add an authentication bypass or hardcoded admin credential for convenience.
8. Never treat an unknown nutrition value as zero.
9. Never silently substitute product-database data for values read from the user's package.
10. Record security-relevant events without logging sensitive payloads.

## Incident response
Maintain a contact/owner, deployment rollback instructions, credential rotation steps, and a documented way to disable image uploads or other abused endpoints quickly.
