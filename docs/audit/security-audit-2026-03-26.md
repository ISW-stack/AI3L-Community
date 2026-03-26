# AI3L Community Security Audit Report

**Date:** 2026-03-26
**Scope:** Full application — backend (FastAPI), frontend (Vue 3), infrastructure (Docker/nginx), DM system
**Method:** Manual code review across ~540 source files via 6 parallel auditors
**Auditor:** Claude Opus 4.6

---

## Executive Summary

The AI3L Community platform demonstrates strong security posture overall, with proper parameterized SQL, server-side HTML sanitization (nh3 + DOMPurify), HttpOnly cookie authentication, CSRF double-submit protection, timing oracle prevention, and comprehensive rate limiting. However, **7 HIGH-severity** and **21 MEDIUM-severity** findings were identified that should be addressed before production deployment.

### Severity Distribution

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 7     |
| MEDIUM   | 21    |
| LOW      | 25    |
| INFO     | 18    |
| **Total**| **71**|

---

## HIGH Severity Findings

### H-01: Album/DM files bypass virus scan via presigned URLs — ✅ FIXED
- **Location:** `backend/app/converters/album_converter.py:41-45`, `backend/app/services/dm.py:435-440`
- **Description:** Editor files are served through `/api/v1/files/content/{key}` which checks scan status. However, album photos and DM attachments use presigned URLs pointing directly to MinIO, bypassing the application. A file flagged as malicious by VirusTotal remains downloadable via presigned URL until it's deleted from storage (TOCTOU window).
- **Impact:** Users can download malicious files before the VirusTotal scan completes or during the gap between detection and deletion.
- **Recommendation:** Route all file downloads through a proxy endpoint that checks scan status, or only generate presigned URLs for files with `status='clean'`.
- **Resolution:** Added `file_scan_repo.is_clean()` gate before all presigned URL generation in album converter (photos) and DM service (send/edit/list_conversations/list_messages). Files with non-clean status return `null` URL.

### H-02: Async `generate_presigned_url` wrapper silently drops `filename` parameter — ✅ FIXED
- **Location:** `backend/app/core/async_storage.py:53-55`
- **Description:** The async wrapper only accepts `(key, expires_in)` and does not forward `filename` to the sync version. Callers passing `filename=` get a `TypeError` caught by `except Exception`, causing `storage_url` to silently become `None`.
- **Impact:** Album photo downloads always return `storage_url: null`. The `Content-Disposition` header that enforces safe filenames is never applied to album presigned URLs.
- **Recommendation:** Update signature: `async def generate_presigned_url(key, expires_in, filename=None)`.
- **Resolution:** Updated async wrapper to accept and forward `filename` parameter to sync version.

### H-03: `.env` file with real secrets on OneDrive-synced path — ⚠️ OPERATIONAL
- **Location:** `.env` (project root on OneDrive)
- **Description:** The `.env` file contains `SECRET_KEY`, `JWT_SECRET_KEY`, `SUPER_ADMIN_PASSWORD`, database credentials, and MinIO keys. The project directory is on OneDrive, meaning secrets are synced to Microsoft cloud storage. The app emits a startup warning but secrets are already exposed.
- **Impact:** Compromised Microsoft account exposes all application secrets, enabling JWT forgery, database access, and full admin control.
- **Recommendation:** Move the project to a non-synced directory (e.g., `C:\dev\AI3L-Community`), or use a secrets manager.

### H-04: Production nginx `YOUR_DOMAIN` placeholder may remain unsubstituted — ✅ FIXED
- **Location:** `nginx/conf.d/default.conf:133,247`, `nginx/docker-entrypoint.sh:14-19`
- **Description:** The HTTPS server block uses `YOUR_DOMAIN` literal, relying on `sed` substitution via `SERVER_DOMAIN` env var. If unset, the placeholder remains and nginx won't match real domain traffic, causing TLS to malfunction.
- **Impact:** All HTTPS traffic falls through to the HTTP block (no TLS), or the site becomes inaccessible.
- **Recommendation:** Add a validation step in `docker-entrypoint.sh` that aborts if `YOUR_DOMAIN` remains after substitution.
- **Resolution:** Added post-substitution `grep` check in `docker-entrypoint.sh` that aborts with error if `YOUR_DOMAIN` literal remains.

### H-05: MinIO console exposed on dev (port 19001) — ✅ FIXED
- **Location:** `docker-compose.override.yml:78-79`
- **Description:** The MinIO admin console is exposed on `127.0.0.1:19001`, providing full object storage admin access (upload, delete, browse all files including DM attachments) using `.env` credentials.
- **Impact:** Any local process or malware on the dev machine can access all uploaded files.
- **Recommendation:** Set `MINIO_BROWSER=off` in dev compose, or remove port 19001 exposure.
- **Resolution:** Set `MINIO_BROWSER=off` in base compose and removed port 19001 from dev override.

### H-06: `SECRET_KEY` has no minimum length validation in production — ✅ FIXED
- **Location:** `backend/app/core/config.py:17,164`
- **Description:** The production validator checks `JWT_SECRET_KEY` for 32-char minimum (line 164) but does NOT apply the same check to `SECRET_KEY`, which is used for CSRF token HMAC. A short `SECRET_KEY` enables CSRF token forgery given a known JTI.
- **Impact:** Weak `SECRET_KEY` allows CSRF token computation, enabling cross-site request forgery attacks.
- **Recommendation:** Add `if len(self.SECRET_KEY) < 32: raise ValueError(...)` in the production validator.
- **Resolution:** Added `len(SECRET_KEY) < 32` check in production validator, matching JWT_SECRET_KEY pattern.

### H-07: JWT uses HS256 with single shared key — ✅ MITIGATED
- **Location:** `backend/app/core/config.py:33`, `backend/app/core/security.py:83,90`
- **Description:** JWT tokens use HS256 (symmetric). The same `JWT_SECRET_KEY` signs and verifies tokens. If leaked (see H-03), an attacker can forge tokens for any user/role including SUPER_ADMIN.
- **Impact:** Key leakage = complete authentication bypass.
- **Recommendation:** Consider RS256 (asymmetric) or ensure key rotation and isolation from other secrets.
- **Resolution:** Added `iss=ai3l-community` and `aud=ai3l-api` claims to JWT creation/validation (prevents cross-service token reuse). Added `JWT_ALGORITHM` allowlist validation (`HS256/HS384/HS512` only) to block `none` algorithm attacks. RS256 migration deferred.

---

## MEDIUM Severity Findings

### M-01: Avatar uploads not scanned by VirusTotal — ✅ FIXED
- **Location:** `backend/app/services/user.py:81-174`
- **Description:** Editor files, album photos, DM attachments all trigger `trigger_virus_scan()`. Avatars do not.
- **Impact:** A crafted image passing magic byte validation but containing malware is never detected. Avatars are high-exposure (visible on every post/comment).
- **Resolution:** Added `trigger_virus_scan(key, data)` call in `upload_user_avatar()` after successful upload.

### M-02: No scan status check when serving album/DM presigned URLs — ✅ FIXED
- **Location:** `backend/app/converters/album_converter.py:31-47`, `backend/app/services/dm.py:723-747`
- **Description:** Presigned URLs are generated for every file regardless of scan status. Even `status='malicious'` files get URLs.
- **Resolution:** Fixed via H-01 — `file_scan_repo.is_clean()` gate before all presigned URL generation.

### M-03: GIF polyglot risk — no deep structure validation — ✅ FIXED
- **Location:** `backend/app/core/file_validation.py`
- **Description:** GIF files validated only by magic bytes (`GIF87a`/`GIF89a`). A GIF/HTML polyglot could pass validation and execute JavaScript when served from MinIO (no CSP on presigned URLs).
- **Resolution:** Added `validate_gif_structure()` that re-encodes GIFs via Pillow (preserving animation), stripping all non-image payload data.

### M-04: Image EXIF metadata not stripped before storage — ✅ FIXED
- **Location:** `backend/app/core/file_validation.py`
- **Description:** Uploaded images retain EXIF data including GPS coordinates, camera serial numbers, timestamps.
- **Resolution:** Added `strip_exif_metadata()` that creates a clean image via Pillow without EXIF data. Applied to JPEG, PNG, WebP in `validate_editor_file()`.

### M-05: ZIP re-write reads all entries into memory (up to 200MB) — ✅ FIXED
- **Location:** `backend/app/core/zip_validation.py:232-239`
- **Description:** ZIP validation re-writes by reading each entry with `zf.read()`. Entries up to 99:1 compression ratio pass. Total uncompressed limit is 200MB.
- **Resolution:** Replaced `zf.read()`/`out_zf.writestr()` with `shutil.copyfileobj(src, dst, length=64*1024)` for streaming 64KB-chunk processing.

### M-06: Editor file upload TOCTOU between storage and scan record — ✅ FIXED
- **Location:** `backend/app/api/v1/endpoints/files.py`
- **Description:** Upload flow: (1) upload to MinIO, (2) increment quota, (3) insert scan record. If step 3 fails (caught silently), file becomes permanently inaccessible "ghost" consuming quota.
- **Resolution:** Added 3-attempt retry loop with 0.5s delay for scan record insertion. Persistent failure logged at ERROR level.

### M-07: DOCX/XLSX/PPTX DM validation accepts any valid ZIP — ✅ FIXED
- **Location:** `backend/app/services/dm.py`, `backend/app/core/file_validation.py`
- **Description:** `.docx`/`.xlsx`/`.pptx` magic check only verifies `PK\x03\x04`. XLSX/PPTX deep validation only checks `[Content_Types].xml` exists, not type-specific directories.
- **Resolution:** Split `validate_ooxml_structure()` into `validate_xlsx_structure()` (checks `xl/`) and `validate_pptx_structure()` (checks `ppt/`). DM service updated to use type-specific validators.

### M-08: CSP `style-src 'unsafe-inline'` allows CSS injection — ⚠️ ACCEPTED RISK
- **Location:** `nginx/snippets/security-headers.conf:15`
- **Description:** Required for Vue `v-show`/transitions, but `unsafe-inline` in styles enables CSS exfiltration attacks.
- **Impact:** CSS injection via stored XSS can exfiltrate CSRF tokens or form values.
- **Mitigation:** HTML sanitization via nh3 + DOMPurify prevents the stored XSS prerequisite. CSS nonce investigation deferred.

### M-09: No read-only filesystem for production containers — ✅ FIXED
- **Location:** `docker-compose.prod.yml`
- **Description:** No container uses `read_only: true`. Compromised containers can write persistent backdoors.
- **Resolution:** Added `read_only: true` + `tmpfs: /tmp:size=100M` to fastapi service in production compose.

### M-10: Dev nginx on both `frontend-net` and `backend-net` — ✅ FIXED
- **Location:** `docker-compose.yml:43-44`
- **Description:** Dev nginx has access to PostgreSQL, Redis, MinIO via `backend-net`.
- **Resolution:** Removed `backend-net` from dev nginx networks — now only on `frontend-net`.

### M-11: Production PostgreSQL `statement_timeout` is 120s — ✅ FIXED
- **Location:** `docker-compose.prod.yml:153`
- **Description:** 4x the dev value (30s). Slow queries hold connections; pool exhaustion possible.
- **Resolution:** Reduced `statement_timeout` from 120000 to 60000 (60s).

### M-12: CORS origin list not format-validated — ✅ FIXED
- **Location:** `backend/app/core/config.py`
- **Description:** Splits comma-separated `CORS_ORIGINS` without validating URL format or protocol.
- **Resolution:** Added validation warnings in `CORS_ORIGINS_LIST` property for origins not starting with `http://`/`https://` and origins containing wildcards.

### M-13: Redis password visible in `/proc` via shell-form command — ⚠️ ACCEPTED RISK
- **Location:** `docker-compose.yml:152-155`, `docker-compose.prod.yml:191-194`
- **Description:** `sh -c 'echo "requirepass $REDIS_PASSWORD"...'` is visible in process info.
- **Impact:** Docker inspect or container filesystem access reveals Redis password.
- **Mitigation:** Requires container-level access which implies already compromised. Docker secrets migration deferred to production hardening phase.

### M-14: No healthcheck for `migrate` service — ✅ FIXED
- **Location:** `docker-compose.yml`, `docker-compose.prod.yml`
- **Description:** Only checks exit code. Partial migration failures that exit 0 go undetected.
- **Resolution:** Changed migrate command to `sh -c "alembic upgrade head && alembic check"` — `alembic check` verifies no pending revisions remain.

### M-15: JWT `iss`/`aud` claims not validated — ✅ FIXED
- **Location:** `backend/app/core/security.py`
- **Description:** `jwt.decode()` validates `exp` but not `iss`/`aud`. If `JWT_SECRET_KEY` shared with another service, cross-application token acceptance is possible.
- **Resolution:** Added `iss="ai3l-community"` and `aud="ai3l-api"` to `create_access_token()` payload and `decode_access_token()` validation (via `issuer=` and `audience=` params).

### M-16: `JWT_ALGORITHM` not validated — could be set to `"none"` — ✅ FIXED
- **Location:** `backend/app/core/config.py`
- **Description:** No validation against an allowlist. PyJWT v2.4+ rejects `"none"` by default, but no defense-in-depth.
- **Resolution:** Added `_VALID_JWT_ALGORITHMS` frozenset and `model_validator` that raises `ValueError` for algorithms not in `{HS256, HS384, HS512}`.

### M-17: Per-account login rate limit enables targeted lockout — ✅ FIXED
- **Location:** `backend/app/api/v1/endpoints/auth.py`
- **Description:** Rate limit key is `rl:login:user:{username}`. An attacker who knows a username can lock them out for 5 minutes with 20 requests.
- **Resolution:** Increased per-account rate limit from 20 to 50 requests per 300s window. Combined with mandatory captcha per attempt, this makes targeted lockout impractical.

### M-18: CSRF heartbeat regeneration is a no-op — ✅ FIXED
- **Location:** `backend/app/api/v1/endpoints/auth.py`
- **Description:** CSRF token is `HMAC(SECRET_KEY, JTI)`. Since JTI doesn't change during a session, regeneration produces the same token. Comment says "so leaked tokens expire" but they never change.
- **Resolution:** Removed misleading "so leaked tokens expire" comment. Updated to accurately describe the cookie re-set as refreshing max-age, not rotating the token value. CSRF token determinism is by design (I-04).

### M-19: PDF sanitization does not recursively strip dangerous keys — ✅ FIXED
- **Location:** `backend/app/core/file_validation.py`
- **Description:** Strips `/JS`, `/JavaScript`, `/AA`, `/OpenAction` from root catalog and pages, but not from annotation objects, embedded file streams, or other nested structures.
- **Resolution:** Added `_strip_dangerous_keys_recursive()` that traverses all PDF dictionaries, arrays, and streams using pikepdf `_type_code` for type detection. Handles circular references via visited set.

### M-20: WebSocket session revalidation only checks key existence — ✅ FIXED
- **Location:** `backend/app/api/v1/endpoints/ws.py`
- **Description:** Periodic check uses `redis.exists(session_key)` but doesn't verify JTI matches. If user logs in from another device, old WS passes revalidation (key exists with new JTI).
- **Resolution:** Changed `r.exists()` to `r.get()` and compares stored JTI with the ticket's JTI. Mismatched JTI sends `FORCE_LOGOUT` with `reason: session_replaced` and closes the connection.

### M-21: Login username schema allows `min_length=1` with no pattern validation — ✅ FIXED
- **Location:** `backend/app/schemas/auth.py`
- **Description:** Registration requires `min_length=3` with `^[a-zA-Z0-9_-]+$`. Login accepts any 1-char string, causing unnecessary Argon2 + DB lookups for obviously invalid inputs.
- **Resolution:** Updated `LoginRequest.username` to `min_length=3` with `pattern=r"^[a-zA-Z0-9_-]+$"`, matching registration constraints.

---

## LOW Severity Findings

### L-01: Super admin bootstrap bypasses password policy ✅ FIXED
- **Location:** `backend/app/main.py:40-72`
- **Fix:** Added `validate_password_policy()` call; raises `RuntimeError` in production, warns in dev.

### L-02: `COOKIE_SAMESITE` not validated ✅ FIXED
- **Location:** `backend/app/core/config.py:47`
- **Fix:** Validated against `{"lax", "strict", "none"}`; warns if `"none"` + `COOKIE_SECURE=False`.

### L-03: Username enumeration via registration 409
- **Location:** `backend/app/api/v1/endpoints/auth.py:249-250`
- **Description:** Returns "Username already exists" on 409. Confirms username existence.
- **Recommendation:** Acceptable for invite-only platform. Document as accepted risk.

### L-04: No `X-Content-Type-Options: nosniff` on presigned URL responses
- **Location:** MinIO/S3 bucket config (external)
- **Description:** Presigned URLs bypass nginx security headers. Browsers may MIME-sniff.
- **Recommendation:** Configure MinIO bucket response headers or route downloads through app proxy.

### L-05: Presigned URL for avatars has 7-day expiry ✅ FIXED
- **Location:** `backend/app/core/constants.py:36`
- **Fix:** `PRESIGNED_URL_AVATAR_SECONDS` changed from `86400 * 7` to `3600` (1 hour).

### L-06: Editor file upload lock has 120s TTL without renewal ✅ FIXED
- **Location:** `backend/app/api/v1/endpoints/files.py:54-55`
- **Fix:** Lock TTL extended from 120s to 300s.

### L-07: Form `file_upload` answers don't check scan status ✅ FIXED
- **Location:** `backend/app/services/form.py:550-551`
- **Fix:** Added `_validate_file_scan_status()` which calls `file_scan_repo.is_clean()` for each file answer.

### L-08: CI workflow uses hardcoded test credentials
- **Location:** `.github/workflows/backend-ci.yml:60-71`
- **Description:** Test passwords/JWT secrets in plain text in workflow YAML.
- **Recommendation:** Use GitHub Actions secrets even for test values.

### L-09: `update-stats.yml` has `contents: write` and pushes to main
- **Location:** `.github/workflows/update-stats.yml:14,43-45`
- **Description:** Compromised `compute_stats.py` could inject arbitrary content.
- **Recommendation:** Use PR workflow instead of direct push.

### L-10: Backend Dockerfile `COPY . .` without `.dockerignore` ✅ ALREADY FIXED
- **Location:** `backend/Dockerfile:27`
- **Note:** `backend/.dockerignore` already exists and excludes `.env*`, `tests/`, `__pycache__/`, `.git/`.

### L-11: Backend dependencies use loose version pins
- **Location:** `backend/requirements.txt`
- **Description:** `>=` without upper bounds. Different builds get different versions.
- **Recommendation:** Use `pip-compile` for locked `requirements.txt`.

### L-12: Dev Redis `appendonly no` — session data loss on restart
- **Location:** `redis/redis-dev.conf:6`
- **Recommendation:** Acceptable for dev; documented.

### L-13: Dev nginx WebSocket `proxy_read_timeout 86400` (24h) ✅ FIXED
- **Location:** `nginx/conf.d.dev/default.conf:84`
- **Fix:** Changed `proxy_read_timeout` from `86400` to `3600` to match production.

### L-14: Cloudflare IP ranges hardcoded — may become stale
- **Location:** `nginx/nginx.conf:15-29`
- **Recommendation:** Automate periodic updates from `cloudflare.com/ips-v4`.

### L-15: `DATABASE_SSL=false` default — easy to miss for remote DB ✅ FIXED
- **Location:** `backend/app/core/config.py:65`
- **Fix:** Added `model_validator` warning when `POSTGRES_HOST` is not a known local host and `DATABASE_SSL=False`.

### L-16: `PRESIGNED_URL_AVATAR_SECONDS` constant unused ✅ FIXED
- **Location:** `backend/app/core/constants.py:36`, `backend/app/converters/user_converter.py`
- **Fix:** Reduced constant to 3600 (fixes L-05); both `resolve_avatar_url` and `async_resolve_avatar_url` now use `PRESIGNED_URL_AVATAR_SECONDS`.

### L-17: Orphan DM file cleanup doesn't refund storage quota
- **Location:** `backend/app/tasks/dm_cleanup.py:208-241`
- **Recommendation:** Extract user_id from key path and decrement quota.

### L-18: VirusTotal is hash-only — novel files permanently blocked
- **Location:** `backend/app/tasks/virustotal.py:61`
- **Description:** Only queries by SHA-256. Novel files return 404 → `status='unknown'` → permanently blocked.
- **Recommendation:** Add file upload to VT for hash-miss files (with rate limiting).

### L-19: Blacklist TTL `max(28800, 43200)` is dead code ✅ FIXED
- **Location:** `backend/app/services/auth.py:111`
- **Fix:** Simplified to `ex=43200` with explanatory comment.

### L-20: Invite code entropy uses `uuid4` not `secrets`
- **Location:** `backend/app/services/auth.py:315`
- **Description:** `INV-{uuid.uuid4().hex[:16].upper()}` — Python `uuid4` uses `os.urandom()` so entropy is fine.
- **Recommendation:** Informational; no change needed.

### L-21: WebSocket ticket not bound to IP
- **Location:** `backend/app/services/auth.py:339-357`
- **Description:** Stolen ticket (within 30s TTL) usable from any IP.
- **Recommendation:** 30s TTL + single-use is adequate. Optional IP binding.

### L-22: `X-Robots-Tag: noindex` blocks all search indexing
- **Location:** `nginx/snippets/security-headers.conf:30`
- **Recommendation:** Intentional for member-only platform. Document if public pages needed.

### L-23: Dev celery-beat lacks `replicas: 1` ✅ FIXED
- **Location:** `docker-compose.yml`
- **Fix:** Added `deploy: replicas: 1` to `celery-beat` service.

### L-24: Security headers fragile — nginx `add_header` inheritance
- **Location:** `nginx/conf.d/default.conf:111-113`
- **Description:** New location blocks without security snippet include lose all headers.
- **Status:** DEFERRED — requires nginx config restructuring; mitigated by code-review practice of including snippet in new locations.

### L-25: `SUPER_ADMIN_USERNAME` defaults to predictable `superadmin` ✅ FIXED
- **Location:** `backend/app/core/config.py:71`
- **Fix:** Added production warning when `SUPER_ADMIN_USERNAME` equals the default `"superadmin"`.

---

## INFO Findings (18 items)

| ID | Title |
|----|-------|
| I-01 | No password reset / forgot-password flow (intentional for invite-only) |
| I-02 | No multi-factor authentication (MFA/2FA) |
| I-03 | No OAuth/social login |
| I-04 | CSRF token deterministic given JTI (secure by design — HMAC with server secret) |
| I-05 | nginx write rate limit 5r/m may be restrictive for heavy admin use |
| I-06 | `COPY . .` copies Alembic migrations at build time (rebuild needed after changes) |
| I-07 | Dev compose services lack log rotation |
| I-08 | Frontend Dockerfile serve stage references missing `nginx.conf` |
| I-09 | Argon2 password hashing (industry best practice) |
| I-10 | Dual JWT + Redis session validation (excellent defense-in-depth) |
| I-11 | One-time WebSocket tickets with atomic `getdel` |
| I-12 | Cookie config sound (HttpOnly, Secure, SameSite=Lax) |
| I-13 | Timing oracle prevention implemented (`_DUMMY_HASH`) |
| I-14 | Login error does not distinguish username vs password (correct) |
| I-15 | `role` in localStorage non-sensitive — server cross-checks on every request |
| I-16 | Password max 128 chars (Argon2 no 72-byte limit, hash-DoS protected) |
| I-17 | Open redirect prevention in LoginView (validates `url.origin === window.location.origin`) |
| I-18 | DM messages use text interpolation `{{ }}` not `v-html` (XSS-safe) |

---

## Positive Security Observations

The codebase demonstrates many security best practices:

**SQL Injection:** All repositories use parameterized queries via asyncpg `$N` placeholders. Dynamic field updates use strict allowlists + regex validation. `_escape_ilike()` neutralizes LIKE wildcards. `_SORT_MAP` / `_SEARCH_SORT_MAP` prevent ORDER BY injection. `_QUERIES` dict in reaction_helpers eliminates table name interpolation.

**XSS Prevention:** Server-side HTML sanitization via `nh3`. Client-side DOMPurify with centralized `SANITIZE_CONFIG` + `FORCE_BODY` for mXSS prevention. `v-html` usage always wrapped in `sanitizeHtml()` (except content segments which are pre-sanitized in `usePostDetail.ts`). DM messages use text interpolation. `renderMentions()` re-sanitizes after DOM manipulation.

**Authentication:** Argon2 hashing, HttpOnly cookies, JTI-based blacklisting, dual JWT+Redis validation, captcha on all auth endpoints, timing oracle prevention, session revocation on password change/role change.

**Authorization:** `require_role()` dependency on all protected endpoints, server-side role cross-check vs DB on every request, SUPER_ADMIN-only for all destructive admin operations, SIG admin checks for SIG-scoped operations.

**Rate Limiting:** Comprehensive per-user rate limits on login, password change, file upload, DM send, search, reactions, comments, admin operations. Both nginx-level and application-level rate limiting.

**Infrastructure:** `security_opt: no-new-privileges:true` + `cap_drop: ALL` on all containers, non-root user in backend Dockerfile, network tier isolation in production, Redis dangerous commands disabled, resource limits on all containers, OpenAPI docs disabled in production, structured JSON logging.

---

## Remediation Priority

### Immediate (before production deployment)
1. H-01 + M-02: Implement scan-status-gated presigned URL generation
2. H-02: Fix async `generate_presigned_url` signature
3. H-03: Move project off OneDrive-synced path
4. H-06: Add `SECRET_KEY` minimum length validation
5. H-04: Add `YOUR_DOMAIN` substitution validation in entrypoint

### Short-term (first 2 weeks post-launch)
6. M-01: Add VirusTotal scan for avatar uploads
7. M-03 + M-04: GIF validation + EXIF stripping
8. M-07: XLSX/PPTX directory validation
9. M-15 + M-16: JWT `iss`/`aud` claims + algorithm validation
10. M-19: Recursive PDF sanitization
11. M-20: WebSocket JTI revalidation

### Medium-term (first month)
12. M-08: CSP nonce investigation
13. M-09: Read-only container filesystems
14. L-10: `.dockerignore` files
15. L-11: Dependency pinning with `pip-compile`
16. I-02: TOTP-based 2FA for admin accounts
