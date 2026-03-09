# Security Vulnerabilities Audit

Date: 2026-03-07 (updated 2026-03-09)

## HIGH Priority

### 1. SQL Injection in `form_repo.py` Dynamic Query Building
- **File:** `backend/app/repositories/form_repo.py`
- **Issue:** Dynamic SQL construction for form response queries uses string interpolation instead of parameterized queries when building WHERE clauses from field filters.
- **Risk:** Attackers can inject arbitrary SQL through form field filter values.
- **Fix:** Use parameterized queries (`$1`, `$2`, ...) with a params list for all dynamic WHERE clause values.

### 2. XSS via `v-html` in `PostCard.vue`
- **File:** `frontend/src/components/PostCard.vue`
- **Issue:** Post content preview is rendered using `v-html` without sanitization. If post content contains malicious scripts, they execute in viewers' browsers.
- **Risk:** Stored XSS — any user who can create posts can execute JavaScript in other users' browsers.
- **Fix:** Sanitize with DOMPurify before rendering, or use a text-only preview (strip HTML tags).

### 3. XSS in `html.ts` `renderMentions`
- **File:** `frontend/src/utils/html.ts`
- **Issue:** `renderMentions()` interpolates user display names directly into HTML without escaping. A user with a display name like `<img onerror=alert(1)>` can execute JavaScript.
- **Risk:** Stored XSS through crafted display names.
- **Fix:** HTML-escape display names before interpolation (replace `<`, `>`, `&`, `"`, `'` with their HTML entities).

### 4. CSV Formula Injection in Form Export
- **File:** `backend/app/tasks/form_export.py:65,69,74–80`
- **Issue:** Form export writes user-supplied values to CSV without sanitizing formula-injection characters. If a cell value starts with `=`, `+`, `-`, `@`, or `\t`, spreadsheet applications (Excel, LibreOffice Calc) interpret it as a formula and may execute it.
- **Attack example:** A form answer of `=cmd|'/c calc'!A0` triggers DDE code execution when a Super Admin opens the export in Excel.
- **Two injection surfaces:** (a) question labels in the header row (`question_labels = [q["label"] for q in questions]`), set by SIG admins; (b) answer values submitted by respondents.
- **Risk:** Arbitrary command execution on the machine of any admin who opens the exported file.
- **Fix:** Prefix any cell value whose first character is in `{'=', '+', '-', '@', '\t', '\r'}` with a single apostrophe (`'`), which Excel treats as a text-force escape.

---

## MEDIUM Priority

### 5. Race Condition in `application_repo.py` (Check-Then-Act)
- **File:** `backend/app/repositories/application_repo.py`
- **Issue:** The application approval flow checks if an application exists and is pending, then updates it in a separate query. Between the check and update, another admin could approve/reject the same application.
- **Risk:** Duplicate approvals, inconsistent state.
- **Fix:** Use a single atomic `UPDATE ... WHERE status = 'pending'` and check affected row count, or use `SELECT ... FOR UPDATE`.

### 6. Race Condition in `report_repo.py` (Check-Then-Act)
- **File:** `backend/app/repositories/report_repo.py`
- **Issue:** Similar check-then-act pattern as `application_repo`. Report resolution checks status then updates separately.
- **Risk:** Duplicate resolutions, inconsistent audit trail.
- **Fix:** Atomic `UPDATE` with `WHERE status` conditions, check affected rows.

### 7. SSRF via Unvalidated Redirect in GitHub Avatar Proxy
- **File:** `backend/app/api/v1/endpoints/about.py:86,93`
- **Issue 1 — Open redirect follow:** `_requests.get(github_url, timeout=10, allow_redirects=True)` follows all redirects without domain validation. GitHub's `.png` avatar URL redirects to `avatars.githubusercontent.com`, but if a `github_username` were ever manipulated (e.g. via a compromised Super Admin account), a crafted value could redirect the server to an internal service (metadata endpoints, Redis, other containers).
- **Issue 2 — Response Content-Type not validated:** `content_type = resp.headers.get("content-type", "image/png")` blindly trusts the redirect destination's declared type. A redirect returning HTML or JavaScript would be cached and re-served with that MIME type, enabling content-injection on consumers of the avatar endpoint.
- **Risk:** MEDIUM. `github_username` is only writable by `SUPER_ADMIN`, limiting the attack surface — but a compromised super-admin account directly enables SSRF.
- **Fix:** (a) Set `allow_redirects=False`, inspect the `Location` header, and only follow redirects whose target hostname ends with `.github.com` or `.githubusercontent.com`. (b) Validate that the final `Content-Type` starts with `image/` before caching; return HTTP 502 otherwise.

### 8. CSP Header Contains Hardcoded `localhost:19000` for Production
- **File:** `nginx/snippets/security-headers.conf:3`
- **Issue:** The `Content-Security-Policy` includes `http://localhost:19000` in both `img-src` and `connect-src`. This placeholder is correct for local Docker development (MinIO's host-exposed port) but is committed to the repository as the production value. A deployment that forgets to update it ships with a weakened CSP that whitelists a non-existent origin. Additionally, `upgrade-insecure-requests` in the same CSP will conflict with the HTTP `localhost` entry in production HTTPS environments, potentially breaking image loading silently.
- **Risk:** MEDIUM. Deployment misconfiguration that weakens CSP in production. An existing TODO comment acknowledges the issue but provides no enforcement.
- **Fix:** Replace `http://localhost:19000` with the production MinIO public URL before deploying. Ideally, generate the CSP header dynamically from the `MINIO_PUBLIC_URL` environment variable in the nginx config using `set` + `map` or a templating step.

### 9. Idempotency Middleware Shares Namespace for Unauthenticated Requests
- **File:** `backend/app/middleware/idempotency.py:30–40`
- **Issue:** When a request carries no valid token, `user_id` falls back to the literal string `"anonymous"`. All unauthenticated requests with the same `Idempotency-Key` header value collide in a single Redis key: `idempotency:anonymous:{key}`. Two different users can therefore replay each other's cached responses.
- **Affected endpoints:** `POST /auth/register` and `POST /auth/login` are unauthenticated and CSRF-exempt, making them reachable with an idempotency key. If User A's registration success response is cached, User B sending the same key receives that replay — which may include User A's generated account data in the response body.
- **Risk:** MEDIUM. Requires two independent users to choose the same idempotency key (low probability with random UUIDs, higher if clients derive keys deterministically from inputs such as a username hash).
- **Fix:** Skip idempotency caching for unauthenticated requests — add `if not token: return await call_next(request)` immediately after the token-extraction block — or namespace anonymous requests by `{ip}:{path}` instead of `"anonymous"`.

### 10. Missing CSRF on WebSocket Upgrade — ✅ Resolved
- **Status:** `POST /auth/ws-ticket` is a standard HTTP POST endpoint protected by the CSRF middleware (double-submit cookie pattern). The WebSocket upgrade itself authenticates via a one-time ticket (30 s TTL, single-use, stored in Redis) — no session cookies cross the upgrade. Cross-site WebSocket hijacking is prevented: a cross-origin attacker cannot read the ticket from the HTTP response (Same-Origin Policy), and cannot forge the `X-CSRF-Token` header needed to obtain one.

---

## LOW Priority

### 11. Information Disclosure in Error Responses
- **Issue:** Some endpoints may return raw database error messages or Python tracebacks in 500 responses when `FASTAPI_DEBUG=true`.
- **Fix:** Ensure `FASTAPI_DEBUG=false` in production; confirm all unhandled exceptions return a generic error body.

### 12. Rate Limiting Bypass via `X-Forwarded-For`
- **Issue:** nginx rate limiting uses `$binary_remote_addr`. If deployed behind a load balancer without proper `set_real_ip_from` configuration, attackers can spoof this header and bypass IP-based rate limits.
- **Fix:** Configure `set_real_ip_from` with the trusted proxy CIDR and use `$realip_remote_addr` for rate-limit zone keys.

### 13. CSRF Token Comparison Not Timing-Safe
- **File:** `backend/app/core/csrf.py:64`
- **Issue:** The double-submit check uses Python's `!=` operator (`cookie_token != header_token`). Python string comparison is not constant-time, theoretically enabling a timing side-channel to infer token content character-by-character.
- **Practical severity:** Very low. CSRF tokens are random and fixed-length; HTTP round-trip latency far dominates any per-character timing difference. The fix is trivially cheap.
- **Fix:** Replace with `not secrets.compare_digest(cookie_token, header_token)` (standard library, no new dependency).

### 14. HSTS Not Set in Security Headers Snippet
- **File:** `nginx/snippets/security-headers.conf`
- **Issue:** `Strict-Transport-Security` (HSTS) is absent from the shared security headers snippet. Without HSTS, first-time visitors connecting over HTTP are subject to downgrade or MITM attacks before the HTTP→HTTPS redirect fires. Once HSTS is cached by the browser the risk is negligible, but the first visit is unprotected.
- **Note:** HSTS must only be set on HTTPS server blocks — setting it on HTTP is incorrect. The snippet is included in both; the header must be added only to the HTTPS block directly.
- **Fix:** Add inside the production HTTPS server block in `nginx/conf.d/default.conf`: `add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;`
