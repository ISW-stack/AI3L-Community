# Security Vulnerabilities Audit

Date: 2026-03-07 (updated 2026-03-11)

## HIGH Priority

### 1. SQL Injection in `form_repo.py` Dynamic Query Building — ✅ Resolved
- **Status:** Field names validated against a strict whitelist (`_ALLOWED_FORM_FIELDS`). Values use parameterized queries. No injection possible.

### 2. XSS via `v-html` in `PostCard.vue` — ✅ Resolved
- **Status:** Post content preview uses text interpolation (`{{ stripHtml(...) }}`), not `v-html`. No XSS risk.

### 3. XSS in `html.ts` `renderMentions` — ✅ Resolved (2026-03-11)
- **Status:** Added `escapeHtml()` to HTML-encode `<`, `>`, `&`, `"`, `'` in usernames before interpolation into mention spans.

### 4. CSV Formula Injection in Form Export — ✅ Resolved (2026-03-11)
- **Status:** Added `_sanitize_csv_value()` that prefixes cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` with an apostrophe. Applied to question labels, usernames, display names, and answer values.

---

## MEDIUM Priority

### 5. Race Condition in `application_repo.py` (Check-Then-Act) — ✅ Resolved
- **Status:** Uses `async with conn.transaction()` for atomic check-then-insert. PostgreSQL transaction isolation prevents duplicates.

### 6. Race Condition in `report_repo.py` (Check-Then-Act) — ✅ Resolved
- **Status:** Same transaction-based atomic pattern as `application_repo`.

### 7. SSRF via Unvalidated Redirect in GitHub Avatar Proxy — ✅ Resolved (2026-03-11)
- **Status:** Changed to `allow_redirects=False`. Redirect `Location` is validated against allowed hostnames (`.github.com`, `.githubusercontent.com`). Response `Content-Type` must start with `image/` or request is rejected with 502.

### 8. CSP Header Contains Hardcoded `localhost:19000` for Production
- **File:** `nginx/snippets/security-headers.conf:3`
- **Status:** Intentional for development. Must be replaced with production MinIO URL at deployment time. TODO comment exists in file.

### 9. Idempotency Middleware Shares Namespace for Unauthenticated Requests — ✅ Resolved (2026-03-11)
- **Status:** Unauthenticated requests (no token) now skip idempotency caching entirely, preventing cross-user response leakage.

### 10. Missing CSRF on WebSocket Upgrade — ✅ Resolved
- **Status:** `POST /auth/ws-ticket` is a standard HTTP POST endpoint protected by the CSRF middleware (double-submit cookie pattern). The WebSocket upgrade itself authenticates via a one-time ticket (30 s TTL, single-use, stored in Redis) — no session cookies cross the upgrade.

---

## LOW Priority

### 11. Information Disclosure in Error Responses — ✅ Resolved (2026-03-11)
- **Status:** Added global `@app.exception_handler(Exception)` in `main.py` that catches all unhandled exceptions and returns a generic `{"detail": "Internal server error."}` response. Stack traces are logged server-side only.

### 12. Rate Limiting Bypass via `X-Forwarded-For`
- **Issue:** nginx rate limiting uses `$binary_remote_addr`. If deployed behind a load balancer without proper `set_real_ip_from` configuration, attackers can spoof this header and bypass IP-based rate limits.
- **Fix:** Configure `set_real_ip_from` with the trusted proxy CIDR and use `$realip_remote_addr` for rate-limit zone keys.

### 13. CSRF Token Comparison Not Timing-Safe — ✅ Resolved (2026-03-11)
- **Status:** Replaced `!=` with `secrets.compare_digest()` for constant-time comparison.

### 14. HSTS Not Set in Security Headers Snippet
- **File:** `nginx/snippets/security-headers.conf`
- **Issue:** `Strict-Transport-Security` (HSTS) is absent from the shared security headers snippet. Must only be set on HTTPS server blocks.
- **Fix:** Add inside the production HTTPS server block: `add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;`
