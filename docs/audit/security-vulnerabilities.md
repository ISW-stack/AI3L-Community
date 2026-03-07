# Security Vulnerabilities Audit

Date: 2026-03-07

## HIGH Priority

### 1. SQL Injection in `form_repo.py` Dynamic Query Building
- **File:** `backend/app/repositories/form_repo.py`
- **Issue:** Dynamic SQL construction for form response queries uses string interpolation instead of parameterized queries when building WHERE clauses from field filters.
- **Risk:** Attackers can inject arbitrary SQL through form field filter values.
- **Fix:** Use parameterized queries (`$1`, `$2`, ...) with a params list for all dynamic WHERE clause values.

### 2. XSS via `innerHTML` in `PostCard.vue`
- **File:** `frontend/src/components/PostCard.vue`
- **Issue:** Post content preview is rendered using `v-html` without sanitization. If post content contains malicious scripts, they execute in viewers' browsers.
- **Risk:** Stored XSS — any user who can create posts can execute JavaScript in other users' browsers.
- **Fix:** Sanitize with DOMPurify before rendering, or use a text-only preview (strip HTML tags).

### 3. XSS in `html.ts` `renderMentions`
- **File:** `frontend/src/utils/html.ts`
- **Issue:** `renderMentions()` interpolates user display names directly into HTML without escaping. A user with a display name like `<img onerror=alert(1)>` can execute JavaScript.
- **Risk:** Stored XSS through crafted display names.
- **Fix:** HTML-escape display names before interpolation (e.g., replace `<`, `>`, `&`, `"`, `'`).

## MEDIUM Priority

### 4. Race Condition in `application_repo.py` (Check-Then-Act)
- **File:** `backend/app/repositories/application_repo.py`
- **Issue:** The application approval flow checks if an application exists and is pending, then updates it in a separate query. Between the check and update, another admin could approve/reject the same application.
- **Risk:** Duplicate approvals, inconsistent state.
- **Fix:** Use a single atomic UPDATE with WHERE conditions, or use SELECT ... FOR UPDATE.

### 5. Race Condition in `report_repo.py` (Check-Then-Act)
- **File:** `backend/app/repositories/report_repo.py`
- **Issue:** Similar check-then-act pattern as application_repo. Report resolution checks status then updates separately.
- **Risk:** Duplicate resolutions, inconsistent audit trail.
- **Fix:** Atomic UPDATE with WHERE status conditions.

### 6. Missing CSRF on WebSocket Upgrade
- **Issue:** WebSocket connections use ticket-based auth (Redis key, 30s TTL) but the ticket issuance endpoint may not validate CSRF tokens consistently.
- **Risk:** Cross-site WebSocket hijacking if CSRF is bypassed.
- **Fix:** Ensure POST `/auth/ws-ticket` validates the CSRF header.

## LOW Priority

### 7. Information Disclosure in Error Responses
- **Issue:** Some endpoints return raw database error messages or Python tracebacks in 500 responses during development mode.
- **Fix:** Ensure all unhandled exceptions return generic error messages in production.

### 8. Rate Limiting Bypass via X-Forwarded-For
- **Issue:** nginx rate limiting uses `$binary_remote_addr`. If deployed behind a load balancer without proper `set_real_ip_from` configuration, attackers can bypass rate limits.
- **Fix:** Configure `set_real_ip_from` for trusted proxies and use `$http_x_forwarded_for` appropriately.
