# Comprehensive Security & Bug Audit Report

**Date:** 2026-03-22
**Scope:** Full application stack (Backend, Frontend, Infrastructure, DM/WebSocket)
**Method:** Automated parallel analysis across 6 domains with manual verification of all MEDIUM+ findings

---

## Executive Summary

This audit examined the entire AI3L Community application across backend authentication, API endpoints, file handling, frontend security, infrastructure configuration, and the DM/WebSocket system. A total of **62 findings** were identified:

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 18    |
| LOW      | 40    |
| INFO     | 4     |

The application demonstrates strong security practices overall: parameterized SQL everywhere, CSRF protection with session-binding, atomic Redis operations, advisory locks for concurrency control, multi-layer file validation, and comprehensive rate limiting. No critical or high-severity vulnerabilities were found. The most impactful findings relate to missing `is_edited` flag on DM edits, potential mXSS from HTML re-serialization, missing VirusTotal scanning on album/DM uploads, and HTTPS configuration gaps.

---

## Table of Contents

1. [Backend Authentication & Authorization](#1-backend-authentication--authorization)
2. [Backend API Endpoints & Data Validation](#2-backend-api-endpoints--data-validation)
3. [File Handling & Storage](#3-file-handling--storage)
4. [Frontend Security & Functional Issues](#4-frontend-security--functional-issues)
5. [Infrastructure & Configuration](#5-infrastructure--configuration)
6. [DM System & WebSocket](#6-dm-system--websocket)
7. [Verified Secure Areas](#7-verified-secure-areas)
8. [Production Deployment Checklist](#8-production-deployment-checklist)

---

## 1. Backend Authentication & Authorization

### A-01: Captcha Verify TOCTOU Race Condition
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `backend/app/services/captcha.py:44-50`
- **Description:** `verify_captcha()` performs `GET` then `DELETE` as two separate Redis operations. Between the GET (line 44) and the DELETE (line 50), a concurrent request could use the same captcha_id and also pass validation. Unlike the WebSocket ticket which uses atomic `getdel`, the captcha uses a non-atomic two-step pattern.
- **Impact:** An attacker could replay the same captcha solution in a narrow time window for multiple login/register attempts, partially undermining brute-force protection.
- **Fix:** Replace `redis.get(key)` + `redis.delete(key)` with `redis.getdel(key)` (Redis 6.2+), matching the pattern already used in `ws.py:31`.

### A-02: Heartbeat CSRF Cookie Missing `path` and `max_age`
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/auth.py:284-291`
- **Description:** The heartbeat endpoint regenerates the CSRF token cookie but omits `path="/"` and `max_age`. Without `path="/"`, the cookie defaults to the request path (`/api/v1/auth/heartbeat`), making the regenerated CSRF cookie invisible to JavaScript on other paths.
- **Impact:** After heartbeat, CSRF validation may fail on subsequent requests until the next full login.
- **Fix:** Add `path="/"` and `max_age=<remaining_session_ttl>` to the heartbeat's `set_cookie` call, or reuse the `_set_auth_cookies` helper.

### A-03: `revoke_user_sessions` Does Not Blacklist JTIs
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `backend/app/services/auth.py:296-301`
- **Description:** `revoke_user_sessions()` deletes Redis session keys but does not blacklist the JTIs. While `destroy_session()` (logout) explicitly blacklists the JTI, `revoke_user_sessions()` (used for password change, ban, role change) skips this step.
- **Impact:** Low in practice since `validate_session` requires the Redis key to exist. However, if Redis restores from an older snapshot after failover, JWTs from revoked sessions could theoretically be reused.
- **Fix:** Scan session keys to read stored JTIs, blacklist each JTI, then delete the session keys.

### A-04: Heartbeat Hardcodes `samesite="lax"`
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/auth.py:289`
- **Description:** The heartbeat CSRF cookie hardcodes `samesite="lax"` instead of using `settings.COOKIE_SAMESITE`. The `_set_auth_cookies` helper correctly uses the config value.
- **Impact:** Cookie attribute inconsistency if `COOKIE_SAMESITE` is changed.
- **Fix:** Use `settings.COOKIE_SAMESITE`.

### A-05: No Password Reset / Account Recovery Flow
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** N/A (missing feature)
- **Description:** No password reset mechanism exists. Users who forget their passwords are permanently locked out. Intentional tradeoff given the "no email service" constraint.
- **Impact:** Locked-out users must contact admins. No admin endpoint to reset passwords either.
- **Fix:** Consider adding a SUPER_ADMIN endpoint to force-reset a user's password (generate temporary password requiring change on next login).

### A-06: WebSocket Session Revalidation Does Not Check JTI
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/ws.py:105-119`
- **Description:** The periodic session revalidation only checks `redis.exists(session_key)`, not whether the stored JTI matches the connection's JTI. If a user logs in from another device, the old WebSocket connection may persist for up to 5 minutes.
- **Impact:** Mitigated by `FORCE_LOGOUT` Pub/Sub, but incomplete fallback if Pub/Sub message is missed.
- **Fix:** Store JTI in WebSocket handler scope and compare during revalidation.

### A-07: CSRF Session-Binding Bypassed When JTI Missing
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/core/csrf.py:109-116`
- **Description:** If `decode_access_token` returns a payload with missing `jti`, the session-binding check is skipped. The request proceeds with only the double-submit check.
- **Impact:** Very low -- `get_current_user` independently validates `jti` presence.
- **Fix:** Return 403 if `payload` is None or `jti` is missing.

### A-08: No Per-Username Login Failure Counter
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/auth.py:97-131`
- **Description:** Login rate limiting is IP-based only (10/min). An attacker with many IPs could target specific accounts.
- **Impact:** Mitigated by captcha requirement and strong password policy.
- **Fix:** Add per-username rate limit (e.g., 5 failures per 15 minutes).

### A-09: No Rate Limit on Admin Account Creation
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/users.py:463-493`
- **Description:** The `admin_create_account` endpoint has no endpoint-specific rate limiting.
- **Fix:** Add rate limiting to the endpoint.

### A-10: `get_client_ip` Single-Proxy Assumption
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/core/rate_limit.py:36-38`
- **Description:** Takes rightmost IP from `X-Forwarded-For`, correct for single nginx proxy but would break if a CDN is added.
- **Fix:** Document assumption. Switch to skipping known proxy IPs if multi-proxy is planned.

---

## 2. Backend API Endpoints & Data Validation

### B-01: DM `edit_message` Missing `is_edited = TRUE`
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/services/dm.py:377`
- **Description:** The SQL `UPDATE dm_messages SET content = $1, updated_at = NOW() WHERE id = $2 AND is_recalled = false` does NOT set `is_edited = TRUE`. The `dm_repo.update_message_content` method does set it, but the service's inline transaction bypasses the repo.
- **Impact:** Edited DM messages are silently modified without the "edited" indicator, violating user trust expectations. This is the most impactful functional bug found.
- **Fix:** Change SQL to `UPDATE dm_messages SET content = $1, is_edited = TRUE, updated_at = NOW() WHERE id = $2 AND is_recalled = false RETURNING *`.

### B-02: Comment `parent_id` Not Validated as UUID
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/schemas/comment.py:6`
- **Description:** `CommentCreateRequest.parent_id` is `str | None` with no UUID format validation. A malformed string causes an unhandled `ValueError` from `uuid.UUID()`, producing a 500 error instead of 422.
- **Fix:** Change to `parent_id: uuid.UUID | None = None`.

### B-03: Album Comment `parent_id` Same Issue
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/schemas/album.py:90`
- **Description:** Same issue as B-02 for `AlbumCommentCreateRequest.parent_id`.
- **Fix:** Change to `parent_id: uuid.UUID | None = None`.

### B-04: Audit Log `date_to` Excludes Most of End Date
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/repositories/audit_repo.py:55-56`
- **Description:** `date_to` condition uses `created_at <= date_to`. Since `date_to` is a `date` type, PostgreSQL casts to `date_to 00:00:00`, excluding all logs on that date except midnight.
- **Impact:** Users filtering audit logs miss most entries on the end date.
- **Fix:** Use `created_at < (date_to + interval '1 day')` instead.

### B-05: `PostSearchRequest.page` Has No Upper Bound
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/schemas/post.py:119`
- **Description:** `page: int = Field(default=1, ge=1)` has no upper bound (GET endpoint has `le=10000`). Large OFFSET causes performance issues.
- **Fix:** Add `le=10000`.

### B-06: `CommentCreateRequest.mentions` Items Lack Length Validation
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/schemas/comment.py:7`
- **Description:** List limited to 20 items, but individual strings have no max length. Could send 20 mentions each 100KB+.
- **Fix:** Add per-item max length (e.g., 50 chars).

### B-07: Guest Form Submission Duplicate Bypass
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/forms.py:362`
- **Description:** Guest `user_id` is ephemeral. Re-login generates new UUID, bypassing duplicate check. Per-IP rate limit (5/hour) partially mitigates.
- **Fix:** Track form submissions by IP for guests.

### B-08: `BulkDeleteNotificationsRequest` No List Size Limit
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/notifications.py:61-66`
- **Description:** `notification_ids` list has no `max_length`. Large `IN (...)` clause.
- **Fix:** Add `max_length=500`.

### B-09: DM Whitespace-Only Content with File Attachment
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/dm.py:123-124`
- **Description:** Whitespace-only content passes falsy check when file is attached.
- **Fix:** Add `content = content.strip() if content else content` before validation.

### B-10: Comment `page_size` Inconsistent Upper Limit (200 vs 100)
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/comments.py:35`
- **Description:** Comments allow `page_size` up to 200; all others cap at 100.
- **Fix:** Reduce to `le=100` for consistency.

### B-11: Guest Access to SIG Posts/Forms/Co-authored Posts
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/sigs.py:277`, `forms.py:91`, `co_authors.py:48`
- **Description:** Several endpoints use `get_current_user` instead of `require_role`, allowing GUEST access.
- **Fix:** Verify this is intended. If not, add role restriction.

---

## 3. File Handling & Storage

### FS-01: No VirusTotal Scan for Album/DM Uploads
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/albums.py` (all upload endpoints), `backend/app/services/dm.py:95-323`
- **Description:** VirusTotal integration only exists for editor file uploads (`/files/upload/editor`). Album photo/ZIP/cover uploads and DM file attachments bypass VirusTotal scanning entirely. These files are served directly via presigned URLs without malware scanning.
- **Impact:** Malicious files (infected PDFs, ZIPs) uploaded through album or DM endpoints can be distributed to other users without antivirus screening.
- **Fix:** Extend VirusTotal pipeline to album and DM uploads. At minimum, insert `file_scans` record and queue `check_virustotal` task for these paths.

### FS-02: `skipped` Scan Status Allows File Serving (Fail-Close Broken)
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/files.py:264-288`
- **Description:** `serve_file` blocks `malicious`, `pending`, `unknown`, `error` statuses but NOT `skipped` (set when `VT_API_KEY` is empty). When VT_API_KEY is not configured, all files bypass scanning and are served freely.
- **Impact:** Fail-close policy is broken for the `skipped` status.
- **Fix:** Add `"skipped"` to blocked statuses, or treat same as `unknown`.

### FS-03: Album Photo Upload Performs MinIO Upload Inside DB Transaction
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/services/album.py:633` (inside transaction at line 593)
- **Description:** `upload_photo` calls `async_upload_file()` inside a DB transaction holding a `FOR UPDATE` lock on the users table. If MinIO is slow/unreachable, the transaction hangs (potentially 60+ seconds), blocking other requests for the same user.
- **Impact:** Slow MinIO uploads cause cascading connection pool exhaustion.
- **Fix:** Restructure: (1) reserve quota in transaction, (2) upload to MinIO outside transaction, (3) insert record in new transaction. Already done correctly for album covers.

### FS-04: Album ZIP Upload Same Issue (MinIO Inside Transaction)
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/services/album.py:768` (inside transaction at line 741)
- **Description:** Same as FS-03 for ZIP uploads.
- **Fix:** Same restructuring approach.

### FS-05: Presigned URLs for DM/Album Files Are Bearer Tokens
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `backend/app/services/dm.py:296-304`, `backend/app/converters/album_converter.py:39-41`
- **Description:** Presigned URLs for DM attachments (1h expiry) and album photos can be shared with anyone. The URL is not bound to the requesting user. DM API checks conversation membership before returning URLs, but the URL itself grants direct MinIO access.
- **Impact:** Conversation participants or site members can extract and share presigned URLs with unauthorized parties.
- **Fix:** This is inherent to presigned URL design. Consider proxying DM files through the backend (like editor files) for per-request access control, or reduce DM presigned URL expiry.

### FS-06: VirusTotal Duplicate Scan Record Race Condition
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/files.py:107-110`, `backend/app/tasks/virustotal.py:82-85`
- **Description:** Upload endpoint inserts pending scan record, Celery task also inserts one. Both use `ON CONFLICT DO UPDATE`. Under rare timing, the endpoint's late insert could reset a completed scan back to "pending".
- **Impact:** File temporarily blocked as "pending" despite completed scan.
- **Fix:** Remove duplicate insert in Celery task or change to `ON CONFLICT DO NOTHING`.

### FS-07: Editor Files Readable by Any Member (No Embedding Check)
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/files.py:251-262`
- **Description:** Any authenticated member can access any editor file by UUID-based key, regardless of whether the file is embedded in a published post. Unpublished draft files remain accessible.
- **Fix:** Accept as simplification or track which files are referenced by published posts.

### FS-08: Album Deletion Does Not Refund Cover Photo Storage
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/services/album.py:165-199`
- **Description:** Album deletion refunds storage for photos but not for the cover photo if it was a dedicated upload. Cover size is not tracked for quota refund.
- **Impact:** Phantom storage usage accumulates over time.
- **Fix:** Track cover uploader and size; refund on deletion.

### FS-09: Orphan Cleanup Does Not Handle Album/DM/Avatar Files
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/tasks/cleanup.py:142`
- **Description:** Only processes `editor/` prefix. Album, DM, and avatar files are not covered. DM has its own cleanup, but DB-MinIO inconsistencies in other prefixes create permanent orphans.
- **Fix:** Add cleanup passes for `dm/`, `albums/`, `avatars/` prefixes.

### FS-10: VirusTotal Storage Key Parsing Fragile
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/tasks/virustotal.py:56-60`
- **Description:** Assumes fixed `parts[1]` structure. If format changes, quota refund silently fails.
- **Fix:** Add validation or use more robust parsing.

### FS-11: File Serving Has No Download Timeout
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/api/v1/endpoints/files.py:320-325`
- **Description:** Streaming downloads have no progress/timeout limits.
- **Fix:** Rely on nginx `proxy_read_timeout` or set timeout on streaming response.

---

## 4. Frontend Security & Functional Issues

### FE-01: `renderMentions` Re-serializes HTML After DOMPurify (mXSS Risk)
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `frontend/src/utils/html.ts:93-155`
- **Description:** Pattern is `renderMentions(DOMPurify.sanitize(content), mentions)`. The function parses sanitized HTML into a DOM tree, manipulates it, then returns `container.innerHTML`. The parse-mutate-serialize cycle is a known mXSS vector where browser-specific DOM parsing differences could produce executable content upon re-serialization.
- **Impact:** In exotic edge cases, crafted HTML passing DOMPurify could achieve script execution after DOM re-serialization.
- **Fix:** Run `DOMPurify.sanitize()` on the *output* of `renderMentions`, or perform mention rendering directly on the DOMPurify-returned DOM without re-serialization.

### FE-02: Content Segments Re-serialized from DOM (Same mXSS Pattern)
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `frontend/src/composables/usePostDetail.ts:180-229`
- **Description:** `contentSegments` sanitizes content, parses into DOM, manipulates, re-serializes with `wrapper.innerHTML`. Each part is re-sanitized, but intermediate re-serialization creates the same mXSS risk.
- **Fix:** Ensure final per-segment `DOMPurify.sanitize(part)` is retained (it is). Consider `RETURN_DOM` mode.

### FE-03: DM Store `updateFromWebSocket` Breaks Conversation List Reactivity
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `frontend/src/stores/dm.ts:170-179`
- **Description:** Mutates `conv.last_message` directly without creating a new object. Vue's reactivity won't trigger re-render for the conversation list sidebar.
- **Impact:** Edited last message preview won't update until another event triggers re-render.
- **Fix:** Use `conversations.value = conversations.value.map(c => ...)` pattern.

### FE-04: DM `recallFromWebSocket` Same Reactivity Issue
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/stores/dm.ts:194-202`
- **Description:** Same direct mutation pattern for conversation `last_message`.
- **Fix:** Same immutable update pattern.

### FE-05: `assertShape` Asserts `content` Field for File-Only DMs
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/api/dm.ts:36`
- **Description:** Asserts `content` key exists. For file-only messages, backend may omit key entirely.
- **Fix:** Remove `'content'` from assertShape keys.

### FE-06: `PostCard.thumbnailUrl` Extracted from Unsanitized Content
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `frontend/src/components/PostCard.vue:142-145`
- **Description:** Regex extracts image URL from raw `post.content` before sanitization. If DOMPurify would strip a URL, thumbnail still displays it.
- **Fix:** Run regex on sanitized content.

### FE-07: DOMPurify Default Config on User Profile Fields
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `frontend/src/views/sigs/SigLayout.vue:256`, `frontend/src/views/forms/FormView.vue:184`, etc.
- **Description:** Profile fields (`bio`, `affiliation`) use default DOMPurify config allowing wide tag set. Users could inject misleading HTML.
- **Fix:** Use restrictive `ALLOWED_TAGS` for profile fields.

### FE-08: `usePostList` Search Debounce Timer Not Cleaned on Unmount
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/composables/usePostList.ts:90`
- **Description:** No `onUnmounted` cleanup for `searchDebounceTimer`.
- **Fix:** Add cleanup hook.

### FE-09: Login Redirect Strips URL Hash
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/views/LoginView.vue:60-70`
- **Description:** Redirect URL constructed as `url.pathname + url.search`, stripping `url.hash`. Deep links with anchors lose the anchor.
- **Fix:** Include `url.hash` in redirect.

### FE-10: No Debounce on `markConversationRead` API Calls
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/views/DMView.vue:127`
- **Description:** Every conversation selection triggers `markConversationRead()` without debouncing. Rapid switching could trigger rate limiter.
- **Fix:** Skip if `unread_count` is already 0, or debounce.

### FE-11: DM Store Encapsulation Violations
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/views/DMView.vue:81-82, 133-136, 188`
- **Description:** Multiple places directly mutate store state from the view instead of using store actions.
- **Fix:** Add store actions (`clearMessages()`, `markConversationReadLocally()`).

### FE-12: DM File Size Mismatch (Frontend 50MB vs Backend 10MB)
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/components/dm/MessageInput.vue:17`, `frontend/src/views/DMView.vue:223`
- **Description:** Frontend allows 50MB (`MAX_FILE_SIZE = 50 * 1024 * 1024`) and error says "max 50 MB", but backend rejects at 10MB.
- **Impact:** Users select 10-50MB files expecting success, get server rejection.
- **Fix:** Change to `10 * 1024 * 1024` and update error message.

### FE-13: Client-Side Role from localStorage Allows Temporary UI Bypass
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `frontend/src/stores/auth.ts:20-21`
- **Description:** Auth store initializes role from localStorage. A user could set `role: 'SUPER_ADMIN'` to briefly see admin UI before `fetchProfile()` corrects it. Backend still blocks all API calls.
- **Impact:** Information disclosure of admin UI layout only.

---

## 5. Infrastructure & Configuration

### I-01: Production HTTPS Block Missing Album/DM Upload Body Size Override
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `nginx/conf.d/default.conf:179-183` (HTTPS section)
- **Description:** The HTTP block has `location ~ ^/api/v1/(albums|dm)/` with `client_max_body_size 110m`, but the commented-out HTTPS block does NOT include this override. When HTTPS is enabled, album and DM uploads over 10MB will fail with 413.
- **Impact:** **File uploads will break in production when HTTPS is enabled.**
- **Fix:** Add the `(albums|dm)` location block to the HTTPS server section with `client_max_body_size 110m` and `proxy_request_buffering off`.

### I-02: Redis `allkeys-lru` Could Evict JWT Blacklist Entries
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `docker-compose.yml:118`
- **Description:** With `allkeys-lru` and 256MB limit, Redis evicts least recently used keys when full. This could evict `jwt:blacklist:jti` entries, allowing revoked JWTs to be used again. Could also evict rate limit counters.
- **Impact:** Revoked JWTs could become valid again under memory pressure.
- **Fix:** Use `volatile-lru` (only evicts keys with TTL), or separate security data into a different Redis DB with `noeviction`.

### I-03: No Container Hardening (no-new-privileges, cap_drop)
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `docker-compose.yml` (all services)
- **Description:** No container uses `security_opt: ["no-new-privileges:true"]` or `cap_drop: ["ALL"]`. Increases blast radius if a container is compromised.
- **Fix:** Add to all services.

### I-04: `minio-init` Uses Default Credentials as Fallback
- **Severity:** MEDIUM | **Type:** SECURITY
- **Location:** `docker-compose.override.yml:92-94`
- **Description:** Uses `${MINIO_ROOT_USER:-minioadmin}` and `${MINIO_ROOT_PASSWORD:-changeme_minio}` as defaults. If `.env` is missing, init container connects with well-known credentials.
- **Fix:** Use `${VAR:?error}` syntax to fail fast.

### I-05: `TRUSTED_HOSTS` Not Configured
- **Severity:** MEDIUM (production-only) | **Type:** SECURITY
- **Location:** `backend/app/main.py:333-339`
- **Description:** Production deployment without `TRUSTED_HOSTS` disables `TrustedHostMiddleware`, allowing Host header attacks.
- **Fix:** Set `TRUSTED_HOSTS=yourdomain.com` before production deployment.

### I-06: HTTPS Block Missing WebSocket Connection Limit
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `nginx/conf.d/default.conf:194-202`
- **Description:** HTTP WebSocket block has `limit_conn ws_conn 5`, but HTTPS block does not.
- **Fix:** Add `limit_conn ws_conn 5;` to HTTPS WebSocket location.

### I-07: No `proxy_hide_header` for Upstream Server/X-Powered-By
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `nginx/snippets/proxy-params.conf`
- **Description:** Upstream `Server` and `X-Powered-By` headers leak through, revealing backend technology.
- **Fix:** Add `proxy_hide_header X-Powered-By;` and `proxy_hide_header Server;`.

### I-08: Database/Redis/MinIO Passwords Still Defaults
- **Severity:** LOW (dev-only) | **Type:** SECURITY
- **Location:** `.env`
- **Description:** `POSTGRES_PASSWORD=changeme_postgres`, `REDIS_PASSWORD=changeme_redis`, `MINIO_ROOT_PASSWORD=changeme_minio`. Production startup guard will reject these.
- **Fix:** Change before any non-local deployment.

### I-09: Single Flat Docker Network
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `docker-compose.yml:236-238`
- **Description:** All services share `ai3l-network`. Nginx can directly reach PostgreSQL and Redis.
- **Fix:** Create separate frontend/backend networks. Only FastAPI bridges both.

### I-10: Redis No ACL Configuration
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `docker-compose.yml` Redis service
- **Description:** Single password auth without ACL. All clients can execute all commands including `FLUSHALL`.
- **Fix:** Configure Redis ACL.

### I-11: No Docker Secrets (Secrets in `.env`)
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `.env`, `docker-compose.yml`
- **Description:** All secrets in `.env` file rather than Docker Secrets or vault.
- **Fix:** Use Docker Secrets for production.

### I-12: `SELECT *` in Multiple Repositories
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `form_repo.py:149`, `category_repo.py:31,38`, `social_repo.py:33,41,51`, `album_repo.py:227,557`, etc.
- **Description:** Many repos use `SELECT *` instead of explicit columns. Future column additions could expose data.
- **Fix:** Replace with explicit column lists.

### I-13: Nginx Request URI Logs WebSocket Tickets
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `nginx/nginx.conf:29`
- **Description:** Access log includes `$request_uri` with query params. WS tickets logged (30s TTL, single-use mitigates).
- **Fix:** Consider stripping query params for WS location.

### I-14: Celery Beat No Single-Instance Lock
- **Severity:** LOW | **Type:** BUG
- **Location:** `docker-compose.yml:161-184`
- **Description:** No file lock or distributed lock for single-instance guarantee. Duplicate tasks during rolling deploy.
- **Fix:** Add `--pidfile` or Redis-based leader election.

### I-15: CSP Requires `MINIO_CSP_ORIGIN` for Production
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `nginx/snippets/security-headers.conf.template:15`
- **Description:** If `MINIO_CSP_ORIGIN` is empty, presigned URLs from MinIO will be blocked by CSP.
- **Fix:** Document as required. Add startup check.

### I-16: `DM_CHAR_CAP_PER_CONVERSATION` Mismatch with Documentation
- **Severity:** INFO | **Type:** BUG
- **Location:** `backend/app/core/constants.py:147`
- **Description:** Code has `DM_CHAR_CAP_PER_CONVERSATION = 20_000` but project memory says "50K char cap".
- **Fix:** Reconcile documentation with code.

### I-17: Celery No `max-tasks-per-child`
- **Severity:** INFO | **Type:** BUG
- **Location:** `docker-compose.yml` celery service
- **Description:** Workers could accumulate memory fragmentation over many tasks.
- **Fix:** Consider `--max-tasks-per-child=1000`.

---

## 6. DM System & WebSocket

### DM-01: No Persistent DB Notification for New DMs
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `backend/app/event_handlers.py:545-553`
- **Description:** The `_on_dm_message_sent` handler only pushes a WebSocket message (`NEW_DM`). It does NOT create a persistent notification in the database (unlike comment, friend request handlers which call `create_notification`). If the recipient is offline, they will never receive a notification about missed DMs.
- **Impact:** Users who are offline miss DM notifications entirely. The unread count badge works (fetched on page load) but there's no notification in the notification dropdown.
- **Fix:** Add `create_notification` call for new DMs when recipient is not viewing the conversation. Add dedup logic to avoid per-message notifications.

### DM-02: No Message Catch-Up After WebSocket Reconnection
- **Severity:** MEDIUM | **Type:** BUG
- **Location:** `frontend/src/composables/useWebSocket.ts:126-136`
- **Description:** When WebSocket disconnects and reconnects, there's no "catch-up" mechanism to fetch messages that arrived during disconnection. Any DM messages pushed during the disconnect window are lost.
- **Impact:** Messages silently missed during brief network interruptions.
- **Fix:** After WS reconnection, trigger `fetchMessages` for active conversation and `fetchUnreadCount` to resync.

### DM-03: WebSocket Invalid JSON Messages Don't Count Against Rate Limit
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/api/v1/endpoints/ws.py:136-147`
- **Description:** Invalid JSON sends error response but continues loop without incrementing rate limit counter. A client can send unlimited invalid JSON.
- **Fix:** Increment counter for invalid messages or close after N consecutive failures.

### DM-04: WS Event Only Sent to Recipient, Not Sender's Other Sessions
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/services/dm.py:307-311`, `backend/app/event_handlers.py:545-553`
- **Description:** When a DM is sent, the WebSocket push only goes to the recipient. Sender's other tabs don't receive the message.
- **Impact:** Multi-tab users won't see their sent message in other tabs until refresh.
- **Fix:** Also emit to sender (frontend already deduplicates).

### DM-05: `dm_friends_only` Not Re-checked in Atomic Transaction
- **Severity:** LOW | **Type:** SECURITY
- **Location:** `backend/app/repositories/dm_repo.py:448-467` vs `backend/app/services/dm.py:140-158`
- **Description:** Block status is re-checked inside advisory lock, but `dm_friends_only` preference is only checked in the outer transaction. Narrow TOCTOU window.
- **Fix:** Optionally re-check inside atomic transaction. Low priority.

### DM-06: Read Receipt `readReceiptFromWebSocket` Doesn't Filter by Sender
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/stores/dm.ts:207-219`
- **Description:** Sets `read_at` on ALL messages without it, not filtering by `sender_id === currentUserId`. Could incorrectly mark received messages in edge cases.
- **Fix:** Filter to only update messages where `msg.sender.id === currentUserId`.

### DM-07: Read Receipt Timestamp from Python, Not DB
- **Severity:** LOW | **Type:** BUG
- **Location:** `backend/app/services/dm.py:602`
- **Description:** WebSocket event uses `datetime.now(timezone.utc)` but DB uses `NOW()`. Slight time discrepancy.
- **Fix:** Return actual `read_at` from DB UPDATE.

### DM-08: Optimistic Recall Doesn't Clear All Attachment Fields
- **Severity:** LOW | **Type:** BUG
- **Location:** `frontend/src/views/DMView.vue:258-264`
- **Description:** Sets `attachment_url: null, attachment_name: null` but not `attachment_size` or `attachment_expires_at`.
- **Fix:** Also null out `attachment_size` and `attachment_expires_at`.

### DM-09: DM Filename Sanitization Discards Original Name
- **Severity:** INFO | **Type:** BUG
- **Location:** `backend/app/services/dm.py:197-200`
- **Description:** Only extension preserved. Downloads have UUID-based names like `abc12345.xlsx`.
- **Fix:** Store original filename (sanitized) in `attachment_name` DB field.

### DM-10: DM Cleanup Counter Logic Possibly Inverted
- **Severity:** INFO | **Type:** BUG
- **Location:** `backend/app/tasks/dm_cleanup.py:37-40`
- **Description:** `if not cleared: deleted += 1` increments when NOT cleared, which seems backwards.
- **Fix:** Verify intended logic and fix condition.

---

## 7. Verified Secure Areas

The following areas were thoroughly reviewed and confirmed properly implemented:

### Authentication & Session
- **Session management:** Dual JWT + Redis session validation with `secrets.compare_digest` for JTI comparison
- **WebSocket auth:** Atomic `getdel` for one-time ticket consumption
- **Password hashing:** Argon2id via passlib, run in threadpool
- **Cookie security:** Auto-derives `COOKIE_SECURE` from environment
- **Production safeguards:** Refuses to start with default secrets
- **Ban enforcement:** Checked on every request with immediate session revocation + WebSocket force-logout
- **Invite code redemption:** Serialized in transactions with `WHERE consumed_at IS NULL AND expires_at > NOW()`

### Data Security
- **All SQL queries** use parameterized placeholders ($1, $2, etc.) -- no SQL injection vectors
- **Dynamic query builders** use strict allowlists with regex validation (`^[a-z_]+$`)
- **HTML sanitization** via `nh3` consistently applied to all user HTML content
- **File uploads:** Magic byte validation, extension allowlists, size limits, PDF sanitization
- **ZIP validation:** Comprehensive bomb detection, path traversal protection, dangerous extension blocklist

### DM System
- **Bilateral block checks** with TOCTOU prevention (double-check inside advisory lock)
- **Advisory lock-based** concurrency control on conversation mutations
- **Atomic quota reservation** prevents storage bypass via concurrent uploads
- **Character cap** enforced with auto-deletion of oldest messages
- **Conversation pair uniqueness** at both schema (`CHECK participant_a < participant_b`) and application level
- **Edit/recall time windows** enforced server-side (12 hours)
- **Read receipts** verified to user permissions (only non-sender messages marked)

### Frontend
- **CSRF Protection:** Axios interceptor correctly injects tokens on all mutating requests
- **WebSocket Security:** Ticket-based auth, message type checking, exponential backoff reconnection
- **Session Cleanup:** `clearSession()` resets all stores, clears localStorage, stops heartbeat
- **DOMPurify Usage:** All `v-html` bindings sanitized; DM messages use text interpolation (`{{ }}`)
- **Timer Cleanup:** Most components properly clean up in `onUnmounted`
- **Open Redirect Prevention:** `LoginView` validates origin before navigating
- **File Attachment Security:** `safeAttachmentUrl()` validates against `javascript:` and `data:` schemes

### Infrastructure
- **Non-root containers** for both backend and frontend
- **Only nginx exposed;** DB, Redis, MinIO internal-only
- **Comprehensive security headers:** CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy
- **Rate limiting:** Auth (5 r/m), write (5 r/m), global (20 r/s)
- **Resource limits:** All containers memory-capped with health checks
- **Celery:** JSON-only serialization, soft/hard timeouts, per-child memory limits, OOM recovery
- **TLS config (when enabled):** TLS 1.2/1.3, ECDHE ciphers, HSTS, OCSP stapling

---

## 8. Production Deployment Checklist

### Must-Fix Before Production (Security)
- [ ] Set `FASTAPI_ENV=production`
- [ ] Change all `changeme_` passwords to strong random values
- [ ] Set `TRUSTED_HOSTS=yourdomain.com`
- [ ] Set `CORS_ORIGINS=https://yourdomain.com`
- [ ] Mount TLS certificates at `/nginx/ssl/`
- [ ] Set `MINIO_PUBLIC_URL` and `MINIO_CSP_ORIGIN` to production URLs
- [ ] Set `COOKIE_DOMAIN` to production domain
- [x] **I-01: Add album/DM upload body size override to HTTPS nginx block** *(fixed 2026-03-22)*
- [x] **I-02: Change Redis eviction to `volatile-lru`** *(fixed 2026-03-22)*

### Should-Fix (Functional Bugs)
- [x] **B-01:** DM edit `is_edited = TRUE` *(fixed 2026-03-22)*
- [x] **A-01:** Captcha `getdel` atomic operation *(fixed 2026-03-22)*
- [x] **A-02:** Heartbeat CSRF cookie `path`/`max_age`/`samesite` *(fixed 2026-03-22)*
- [x] **B-02/B-03:** Comment `parent_id` UUID validation *(fixed 2026-03-22)*
- [x] **B-04:** Audit log `date_to` inclusive end date *(fixed 2026-03-22)*
- [x] **FE-03/FE-04:** DM store reactivity fixes *(fixed 2026-03-22)*
- [x] **FE-12:** DM file size limit alignment (50MB -> 10MB) *(fixed 2026-03-22)*
- [x] **DM-01:** Add persistent DB notifications for DMs *(fixed 2026-03-22)*
- [x] **DM-02:** Message catch-up after WS reconnection *(fixed 2026-03-22)*

### Recommended (Hardening)
- [ ] **FS-01:** Extend VirusTotal to album/DM uploads *(deferred — large feature)*
- [x] **FS-02:** Block `skipped` scan status *(fixed 2026-03-22)*
- [x] **FS-03/FS-04:** Move MinIO uploads outside DB transactions *(fixed 2026-03-22)*
- [x] **A-03:** Blacklist JTIs in `revoke_user_sessions` *(fixed 2026-03-22)*
- [ ] **A-08:** Per-username login failure counter *(deferred — low priority, mitigated by captcha)*
- [x] **FE-01/FE-02:** mXSS prevention (sanitize after DOM re-serialization) *(fixed 2026-03-22)*
- [x] **I-03:** Container hardening (`no-new-privileges`, `cap_drop`) *(fixed 2026-03-22)*
- [ ] **I-10:** Redis ACL configuration *(deferred — production hardening)*

### Additional Items Fixed (2026-03-22)
- [x] **A-04:** Heartbeat `samesite` now uses `settings.COOKIE_SAMESITE`
- [x] **A-07:** CSRF rejects tokens with decoded payload but missing JTI
- [x] **B-05:** `PostSearchRequest.page` upper bound (le=10000)
- [x] **B-06:** Comment mentions per-item max length (50 chars)
- [x] **B-08:** Already had `max_length=100` (false positive)
- [x] **B-09:** DM whitespace-only content stripped before validation
- [x] **B-10:** Comment `page_size` reduced to le=100
- [x] **FS-06:** VirusTotal duplicate scan race (`ON CONFLICT DO NOTHING`)
- [x] **FE-05:** `assertShape` no longer requires `content` for file-only DMs
- [x] **FE-06:** `PostCard.thumbnailUrl` extracted from sanitized content
- [x] **FE-08:** Already fixed (false positive — consumers call `cleanup` on unmount)
- [x] **FE-09:** Login redirect preserves URL hash
- [x] **FE-10:** `markConversationRead` skips API call when `unread_count` is 0
- [x] **FE-11:** DM store encapsulation via `clearMessages()` action
- [x] **DM-03:** WS invalid JSON counts against rate limit
- [x] **DM-04:** WS event sent to sender's other sessions
- [x] **DM-06:** Read receipt only marks sender's own messages
- [x] **DM-07:** Read receipt uses DB timestamp (not Python `datetime.now()`)
- [x] **DM-08:** Optimistic recall clears all attachment fields
- [x] **DM-10:** Cleanup counter logic fixed (no false increment)
- [x] **I-04:** minio-init fails fast on missing credentials
- [x] **I-06:** HTTPS WebSocket block includes `limit_conn ws_conn 5`
- [x] **I-07:** `proxy_hide_header` for `X-Powered-By` and `Server`

---

*Report generated by comprehensive 6-domain parallel analysis with manual verification of all MEDIUM+ findings.*
