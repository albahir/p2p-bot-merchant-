# Browser DevTools & Live Web Security Reference (`Chrome DevTools` & `Playwright MCP`)

When the audited project exposes a web frontend or API consumed by a browser, use live browser inspection during **Phase 5** (client configuration/storage) and **Phase 7** (passive/authorized DAST) via **Chrome DevTools MCP** (or **Playwright MCP** when desktop Chrome remote debugging `DevToolsActivePort` is unavailable).

## 1. Companion Tools & Fallback Matrix

| Tool / Skill | Location / Server | Purpose in Security Audit |
|---|---|---|
| `chrome-devtools` / `cookie-debugging` | `chrome-devtools-plugin` (`browser` subagent) | Inspect live DOM, console errors, network headers, cookies (`HttpOnly`, `Secure`, `SameSite`) and auth redirects in desktop Chrome. |
| `playwright` MCP | `ServerName: "playwright"` (`browser_navigate`, `browser_snapshot`, `browser_network_requests`, `browser_console_messages`, `browser_evaluate`, `browser_close`) | Deterministic headless/automated browser fallback when `DevToolsActivePort` is missing; captures exact XHR/fetch requests, console warnings/errors, and `localStorage`/`sessionStorage` state. |

## 2. Mandatory Live Browser Audit Checklist (OWASP A01, A02, A05, A07)

1. **Authorization Gate First (Phase 7)**:
   - Run live browser probes only against isolated local test servers (`127.0.0.1` / disposable test DB) or hosts explicitly authorized by the user. Never run destructive mutations against production data.
2. **Network & Transport Hygiene (`browser_network_requests`, `static: false`)**:
   - Confirm JWTs, API keys, and OTPs never appear in URL query strings (`?token=...`) or GET parameters.
   - Verify unauthenticated/public views only call public endpoints (zero unauthorized `POST`/`PUT`/`DELETE` calls and zero background `401`/`403`/`5xx` polling storms).
3. **Multi-User Session & Storage Isolation (`browser_evaluate`)**:
   - Inspect `localStorage`, `sessionStorage`, and cookies across: `login` -> authenticated navigation -> `logout` / `401` -> login as second user.
   - Confirm user-scoped caches, tokens, and bank/settings configs are completely cleared on `logout` and `401` (preventing cross-user data bleed on shared browsers).
4. **DOM, Console & Privilege UI Exposure (`browser_snapshot`, `browser_console_messages`)**:
   - Verify `0` unhandled runtime console errors, `0` CSP violations, and `0` secrets or raw credentials rendered in DOM attributes, inline scripts, or client bundles.
   - Confirm privileged UI controls (e.g., manual capture triggers, admin panels) stay hidden when unauthenticated and backed by server-side authorization checks.
5. **Cleanup**:
   - Always close browser tabs (`browser_close`) and stop any temporary local test servers immediately after verification.
