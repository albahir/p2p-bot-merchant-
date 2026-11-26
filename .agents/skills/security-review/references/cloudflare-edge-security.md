# Cloudflare Edge, DNS & Workers Security Reference (`cloudflare_cloudflare` MCP & `cf-cli`)

When the audited project sits behind Cloudflare (reverse proxy, CDN, WAF, DNS, or Cloudflare Workers), inspect the live Edge configuration during **Phase 5** and **Phase 7** using the **Cloudflare MCP** (`cloudflare_cloudflare`: `whoami`, `search`, `docs`, `execute`) and companion skills (`cloudflare`, `cf-cli`, `workers-best-practices`).

## 1. Companion Tools & Access Discipline

| Tool / Skill | Purpose in Security Audit |
|---|---|
| `cloudflare_cloudflare` (`whoami`, `search`, `docs`, `execute`) | Query OpenAPI specs (`search`) and audit live zones, DNS, SSL/TLS, Rulesets (Cache, Rate Limit, WAF), Tunnels, and Workers (`execute`). |
| `cloudflare` / `cf-cli` / `workers-best-practices` | Architecture guidance, CLI checks, and Workers production security patterns. |

**Least-Privilege Rule**: Run read-only `GET` audits first. If a `PATCH`/`PUT` returns `HTTP 403` due to missing OAuth scopes (e.g., `zone-settings.write`), report the exact missing permission and stop without attempting workarounds.

## 2. Mandatory Cloudflare Audit Checklist (OWASP A02, A05, A07, A10)

1. **SSL / TLS & Transport Enforcement**:
   - Verify `ssl == "strict"` (with valid Origin CA or trusted origin cert), `always_use_https == "on"`, `min_tls_version >= "1.2"`, and `tls_1_3 == "on"`.
   - Verify `security_header.strict_transport_security` (`enabled: true`, `max_age >= 15552000`, `nosniff: true`). Keep `include_subdomains: false` and `preload: false` if unproxied mail/DNS subdomains (`send.`, `rsend.`) exist.
2. **Edge Cache Isolation (`http_request_cache_settings`)**:
   - Confirm explicit Cache Bypass (`cache: false`) on `/api/*`, `/ws/*`, and `/health` so private financial/user JSON or authenticated responses are never cached at Edge PoPs regardless of query string.
   - Cache only content-hashed immutable static assets (e.g., `/_next/static/*`).
3. **Brute-Force & WAF Protection (`http_ratelimit`, Managed WAF)**:
   - Verify Rate Limiting protects authentication endpoints (`POST /api/auth/login`, `/api/auth/register`) and Managed/DDoS L7 rulesets are active.
4. **DNS & Origin Exposure**:
   - Audit `proxied` status on `A`/`AAAA`/`CNAME` records, verify canonical `www` -> apex redirection (`http_request_dynamic_redirect`) if applicable, and flag unproxied application records that expose the origin VPS IP.
5. **Cloudflare Workers Audit (`workers/scripts`)**:
   - Inspect live Worker scripts (e.g., Telegram API proxies) for **open-proxy** / SSRF risks: enforce strict URL/path allowlists (such as `/bot` and `/file/bot`, returning `403` for everything else), strip untrusted headers where needed, and verify zero hardcoded secrets (use Worker Secrets).
6. **Live Verification**:
   - After any approved Edge change, validate live behavior (`301` HTTP->HTTPS, `HSTS`, `cf-cache-status`, TLS `< 1.2` rejection, and `403` on disallowed Worker paths).
