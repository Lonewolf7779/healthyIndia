# healthyIndia Deployment Architecture & Environment Guidelines

## Environment Separation

| Environment | Purpose | Secrets Management | Network & Origin Policy |
| :--- | :--- | :--- | :--- |
| **Local** | Development and local testing | `.env` from `.env.example` | Origins: `localhost:3000`, `127.0.0.1:3000` |
| **Test / CI** | Automated testing in GitHub Actions | Ephemeral test settings | Mocked / synthetic origins |
| **Staging** | Pre-production validation | Cloud Secret Manager | Restrictive staging origins; HTTPS only |
| **Production** | Public live service | Cloud Secret Manager (high-entropy) | Restrictive production origins; HTTPS + HSTS |

## Production Deployment Checklist
1. **Secret Key:** Provide a 64+ character cryptographically secure `SECRET_KEY`. The backend will refuse startup if default terms or short keys are detected.
2. **TLS / HTTPS:** Terminate TLS at the reverse proxy / ingress (e.g., Cloudflare, NGINX, or cloud load balancer). Enable HTTP Strict Transport Security (HSTS).
3. **CORS:** Ensure `ALLOWED_ORIGINS` contains only verified production domain names (e.g. `https://healthyindia.com`). Wildcards (`*`) and localhost are strictly forbidden.
4. **Non-Root Execution:** Always run container processes as non-root user (`appuser` UID 10001).
5. **Rate Limiting:** Place rate-limiting and DDoS mitigations in front of public endpoints at the edge / reverse-proxy layer.
