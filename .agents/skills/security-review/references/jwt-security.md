# JWT Security Audit Reference (`jwt-decode`, `jwt-encode`, `jwt-validate`)

When the audited codebase issues, stores, forwards, or verifies JSON Web Tokens (JWTs) or session tokens, integrate the companion skills in `.agents/skills/jwt-decode`, `.agents/skills/jwt-encode`, and `.agents/skills/jwt-validate`.

## 1. Companion Skills Matrix

| Skill | Location | Purpose in Security Audit |
|---|---|---|
| `jwt-decode` | `.agents/skills/jwt-decode/SKILL.md` | Inspect token header, payload, timestamps (`exp`, `nbf`, `iat`), nested JWTs (`cty: "JWT"`), and flag unsigned tokens (`alg: none`), missing `exp`, sensitive claims, or header key injection (`jku`, `jwk`, `x5u`). |
| `jwt-encode` | `.agents/skills/jwt-encode/SKILL.md` | Mint controlled test/adversarial tokens (`HS256`, `RS256`, `ES256`) using environment-isolated secrets to probe authentication guards without leaking secrets to shell history. |
| `jwt-validate` | `.agents/skills/jwt-validate/SKILL.md` | Verify 3-part base64url structure, temporal claims (`exp`, `nbf`, `iat` <= 30d, 60s clock skew), expected `iss`/`aud`/`sub`, and cryptographic signatures against HMAC secrets, PEM keys, or JWKS endpoints with explicit algorithm allowlists. |

## 2. Mandatory JWT Audit Checklist (OWASP A02 & A07)

1. **Algorithm Allowlist & `alg: none` (CVE-2015-9235)**:
   - Verifiers MUST pass an explicit `algorithms=[...]` allowlist and reject `none` (case-insensitive) both in configuration and in the unverified JWT header.
2. **Algorithm Confusion (`RS256` -> `HS256`)**:
   - Asymmetric verifiers MUST NOT accept HMAC algorithms signed with the server's public key bytes.
3. **Header Key Injection (`jku`, `jwk`, `x5u`, `kid` traversal)**:
   - Reject any token carrying untrusted `jku`, `jwk`, or `x5u` headers unless verified against a pinned allowlist.
4. **Mandatory Temporal Claims (`exp`, `iat`, `nbf`)**:
   - Token decoders MUST require `exp` (`options={"require": ["exp"]}` in PyJWT) so tokens stripped of `exp` cannot become immortal.
   - Include `iat` on issuance and reject tokens with `iat` in the future (beyond 60s skew) or older than maximum policy age (e.g., 30 days).
5. **Zero Secrets / PII in Payload**:
   - Payloads are base64url-encoded, not encrypted. Flag passwords, API keys, private keys, OTPs, or unmasked credentials in claims.
6. **Transport & Storage**:
   - Never pass JWTs in URL query strings (`?token=...`) where they leak into proxy logs, browser history, and `Referer` headers; require `Authorization: Bearer` headers.
