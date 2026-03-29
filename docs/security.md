# Security Design — AI3L Community Platform

This document describes the security architecture of the AI3L Community Platform. Each section covers a threat domain, the specific risks it addresses, and the controls that mitigate them.

---

## Table of Contents

1. [Authentication & Session Management](#1-authentication--session-management)
2. [Authorization & Role Enforcement](#2-authorization--role-enforcement)
3. [CSRF Protection](#3-csrf-protection)
4. [File Upload Security](#4-file-upload-security)
5. [Input Sanitization & Injection Prevention](#5-input-sanitization--injection-prevention)
6. [Rate Limiting & Abuse Prevention](#6-rate-limiting--abuse-prevention)
7. [Real-Time Connection Security](#7-real-time-connection-security)
8. [Network & Infrastructure Security](#8-network--infrastructure-security)
9. [GDPR & Privacy Compliance](#9-gdpr--privacy-compliance)
10. [Audit Trail](#10-audit-trail)
11. [Threat Model Summary](#11-threat-model-summary)

---

## 1. Authentication & Session Management

### 1.1 Dual-Layer Token Validation

Every authenticated request is validated against two independent conditions:

1. **JWT cryptographic signature** — the token must be signed with the server's `JWT_SECRET_KEY` and must not be expired.
2. **Redis session record** — the token's `jti` (JWT ID) must exist in the active session store in Redis.

A valid signature alone is not sufficient. This means:

- **Logout is immediate.** On `POST /auth/logout`, the `jti` is removed from Redis and added to a blacklist. Any subsequent request using that token — even with a valid signature — is rejected.
- **Forced revocation works.** When an admin bans a user, all of that user's `jti` values are deleted from Redis, terminating every active session instantly.
- **Token theft is bounded.** A stolen token cannot be used indefinitely; it is invalidated the moment the legitimate user logs out or an admin acts.

### 1.2 Password Hashing

Passwords are hashed with **Argon2id** via passlib. Argon2id is the winner of the Password Hashing Competition (PHC) and is resistant to GPU cracking and side-channel attacks. Plain-text passwords are never stored, logged, or transmitted after the initial request.

### 1.3 Cookie Security

The session JWT is delivered as an **HttpOnly, SameSite** cookie:

| Cookie | HttpOnly | Readable by JS | Purpose |
|---|---|---|---|
| `access_token` | Yes | No | Carries the JWT — protected from XSS theft |
| `csrf_token` | No | Yes | Read by the frontend to populate `X-CSRF-Token` headers |

In production (`COOKIE_SECURE=true`), both cookies are set with the `Secure` flag and are only transmitted over HTTPS.

### 1.4 Session TTLs by Role

Sessions are short-lived and differentiated by privilege level:

| Role | Session Duration |
|---|---|
| `GUEST` | 45 minutes |
| `MEMBER` | 3 hours |
| `ADMIN` | 5 hours |
| `SUPER_ADMIN` | 8 hours |

Higher-privilege sessions expire sooner to limit the damage window of a compromised token. The client calls `POST /auth/heartbeat` to extend the TTL while actively using the platform.

### 1.5 CAPTCHA on Authentication Endpoints

`POST /auth/login` and `POST /auth/register` require a valid CAPTCHA answer alongside credentials. The server generates an image challenge (`GET /auth/captcha`), stores the answer server-side with a short TTL, and rejects any login attempt that does not include the correct solution. This prevents automated credential stuffing and bulk registration abuse.

### 1.6 Timing Oracle Prevention

Non-existent or deleted user lookups run the same Argon2id password verification as valid ones. A module-level `_DUMMY_HASH` is computed at import time and used whenever the user is not found in the database. Without this, an attacker could enumerate valid usernames by timing the difference between "user not found" (fast) and "wrong password" (slow, due to hashing). With it, both code paths take the same time.

### 1.7 Password Policy

Passwords are validated on registration and change against five independent requirements:

1. Minimum 8 characters
2. At least one uppercase letter (A–Z)
3. At least one lowercase letter (a–z)
4. At least one digit (0–9)
5. At least one special character: `!@#$%^&*()_+-=[]{}|;:,.<>?/~`

Validation is enforced in `app/core/security.py` (`validate_password_policy()`). The function returns the first failing rule as a user-facing message. Plain-text passwords are never stored, logged, or transmitted after the initial request.

### 1.8 Guest Session Limits

Guest accounts created via invite codes are bounded by two independent caps:

- **Global concurrent cap**: 30 simultaneous guest sessions platform-wide.
- **Per-IP cap**: 3 simultaneous guest sessions per IP address per hour.

Both limits are enforced via Redis atomic counters. Exceeding either returns a `429` error before a session is created.

---

## 2. Authorization & Role Enforcement

### 2.1 Role Hierarchy

```
SUPER_ADMIN
    └── ADMIN
         └── MEMBER
              └── GUEST
```

The `require_role(roles)` FastAPI dependency enforces role checks at the endpoint level before any service logic executes. Roles are stored in the JWT payload and re-validated on every request.

### 2.2 Resource-Level Ownership Checks

Role enforcement alone is not sufficient for resources with per-object ownership. The service layer performs explicit ownership checks before allowing mutations:

- A user can only edit or delete their own posts and comments.
- A SIG admin can only manage forms and members within their own SIG.
- Admin bulk operations are separated into dedicated endpoints (`/bulk`, `/bulk-role`) that require elevated roles and are placed before parameter routes in the router to prevent route collision.

### 2.3 Guest Access Restrictions

Guest sessions are blocked from:

- Creating posts or comments
- Accessing member-only pages (e.g. the About/Contributors page)
- Generating invite codes

The frontend enforces this via route guards (`meta.requiresMember`). The backend enforces it independently via `require_role` — frontend enforcement is defense-in-depth, not the primary control.

---

## 3. CSRF Protection

### Mechanism: Double-Submit Cookie Bound to Session JTI

The platform uses the **double-submit cookie** pattern with a cryptographically bound token:

1. On authentication, the server derives the CSRF token by computing `HMAC-SHA256(SECRET_KEY, jti)`, where `jti` is the unique JWT session identifier. The token is deterministic for a given session but unpredictable to any third party that does not know both the `jti` and the secret key.
2. The derived token is set as a readable (`HttpOnly=False`) cookie named `csrf_token`.
3. The frontend reads this cookie and includes its value in the `X-CSRF-Token` request header on every state-mutating request.
4. The CSRF middleware reads both values and rejects the request if they do not match. On session rotation the token automatically changes because the `jti` changes.

### Why This Works

An attacker on a different origin cannot read the `csrf_token` cookie value (enforced by the browser's Same-Origin Policy), so they cannot forge the `X-CSRF-Token` header. A forged request without the correct header value is rejected by the middleware before reaching any endpoint handler.

Safe HTTP methods (`GET`, `HEAD`, `OPTIONS`) bypass CSRF checks. All mutating methods (`POST`, `PUT`, `PATCH`, `DELETE`) are always checked.

---

## 4. File Upload Security

### 4.1 Magic Byte MIME Type Validation

The declared `Content-Type` header of an upload is **never trusted**. Before any file is written to object storage, `app/core/file_validation.py` reads the file's first bytes and compares them against a whitelist of known magic number signatures:

| Extension | Magic Bytes | Additional Validation |
|---|---|---|
| `.png` | `\x89PNG\r\n\x1a\n` | — |
| `.jpg` / `.jpeg` | `\xFF\xD8\xFF` | — |
| `.pdf` | `%PDF` | Full object-tree sanitization (see §4.2) |
| `.docx` | `PK\x03\x04` | ZIP structure check: must contain `[Content_Types].xml` and `word/` directory |
| `.webp` | `RIFF....WEBP` | Bytes 0–3 must be `RIFF`; bytes 8–11 must be `WEBP` |
| `.gif` | `GIF87a` / `GIF89a` | Re-encoded through Pillow to strip GIF/HTML polyglot payloads |

A mismatch raises `AppError` with code `FILE_001` and the upload is rejected. A renamed executable cannot pass this check. The ZIP structure validation for DOCX prevents JAR, APK, and other ZIP-based file formats from masquerading as Word documents.

### 4.2 PDF Sanitization

PDF files pass through an additional sanitization step using **pikepdf**, backed by the C++ **qpdf** engine. The sanitizer strips:

- `/JS` and `/JavaScript` — embedded JavaScript
- `/AA` and `/OpenAction` — auto-actions triggered on open
- `/Launch`, `/SubmitForm`, `/ImportData` — dangerous action types
- Macros and encrypted objects that cannot be inspected

A corrupted or invalid PDF that cannot be parsed is rejected before reaching storage. Sanitized PDFs are stored without executable content.

### 4.3 VirusTotal Async Scanning

After a file is stored in MinIO, it is queued for asynchronous scanning via the VirusTotal API. The scan result is stored in the `file_scans` table. Clients can poll `GET /files/scan-status/{key}` to retrieve the scan status and verdict (`pending` / `clean` / `malicious`). Files flagged as malicious return HTTP 451 from the content proxy.

This provides a second line of defense against malware that passes magic byte checks (e.g. a valid PDF with malicious content). The UI surfaces the scan status to the user (pending / clean / flagged).

### 4.4 Object Storage Access Control

Files in MinIO are **never publicly accessible**. Read access is served in two ways:

- **Editor-embedded images**: accessed via the stable backend proxy `GET /files/content/{key}`. The proxy streams the file from MinIO and requires authentication. This avoids the expiry problem of embedded presigned URLs.
- **Attachments / on-demand downloads**: the backend generates short-lived **presigned URLs** scoped to a single object. TTLs vary by context:
  - `GET /files/presigned/{key}` — **1-hour TTL** (general file downloads)
  - Album photos and thumbnails — **15-minute TTL** (generated inline when serving album data)
  - Site export archives — **15-minute TTL** (regenerated on each progress poll)

When MinIO is accessed through a different hostname from the browser (e.g. behind Nginx or in Docker development), `MINIO_PUBLIC_URL` rewrites the internal hostname in generated presigned URLs so the browser can reach the file without the internal service name being exposed.

### 4.5 Upload Limits

| Context | Maximum Size | Accepted Types |
|---|---|---|
| Avatar | 2 MB | PNG, JPEG only |
| Editor file attachment | 10 MB | PNG, JPEG, PDF, DOCX, WEBP, GIF |
| Album photo (individual) | 10 MB | PNG, JPEG, WEBP, GIF |
| Album bulk upload | 50 MB | PNG, JPEG, WEBP, GIF |
| DM attachment | 10 MB | PNG, JPEG, PDF, DOCX, WEBP, GIF |

Per-user upload rate is limited to 10 uploads / minute for editor attachments (separate limits apply to album and DM uploads). Upload size limits are enforced both at the Nginx layer and in application middleware before file content is read.

---

## 5. Input Sanitization & Injection Prevention

### 5.1 SQL Injection

All database interactions use **asyncpg parameterized queries**. No raw string interpolation is used anywhere in the repository layer. The query and its parameters are always passed separately to the database driver.

Full-text search uses PostgreSQL's `websearch_to_tsquery('english', $1)` function, which safely handles special characters (`&`, `|`, `!`, quotes) without risk of query injection. The previously used `to_tsquery` was replaced specifically because it crashes on unescaped special input.

### 5.2 XSS Prevention

User-generated HTML is sanitized at two independent layers:

| Layer | Library | When |
|---|---|---|
| Frontend | **DOMPurify** | Before rendering any user content in the browser |
| Backend | **nh3** | Before storing rich-text content in the database |

Both sanitizers strip all script tags, event handlers, and dangerous attributes. The backend sanitization ensures content is safe even if retrieved by a non-browser client or a future client that omits frontend sanitization.

Configuration note: `rel` is excluded from the allowed attributes for `<a>` tags in nh3 — including it causes a panic in the underlying Rust library.

### 5.3 Host Header Injection

In production, Starlette's `TrustedHostMiddleware` validates the `Host` header against the configured domain. Requests with an unrecognized `Host` value are rejected with a `400` response before reaching any endpoint logic.

---

## 6. Rate Limiting & Abuse Prevention

Rate limiting is enforced at two independent layers, so that bypassing one does not eliminate protection.

### 6.1 Nginx Layer (IP-level)

| Zone | Limit | Scope |
|---|---|---|
| `global` | 20 requests / second | All `/api/` endpoints, per IP |
| `write` | 5 requests / minute | POST, PUT, PATCH, DELETE (general), per IP |
| `dm_write` | 30 requests / minute | `/api/v1/dm/*` write operations, per IP |

All zones use `nodelay` burst handling. Clients that exceed the limit receive `429 Too Many Requests`. GET and HEAD requests bypass the `write` zone. The `dm_write` zone is more permissive than `write` because real-time messaging generates higher legitimate write frequency.

### 6.2 Application Layer (Redis-backed, per-endpoint)

Redis atomic counters with fixed TTL windows enforce granular limits per endpoint and per identity (IP or user):

| Endpoint | Limit | Key |
|---|---|---|
| `POST /auth/login` | 10 / min | per IP |
| `POST /auth/login` | 50 / 5 min | per username (account-level) |
| `POST /auth/register` | 5 / min | per IP |
| `POST /auth/guest/{code}` | 10 / min | per IP |
| `POST /auth/invite-code` | 5 / hour | per user |
| `GET /auth/invite-code/{code}` | 30 / min | per IP |
| `POST /files/upload/editor` | 10 / min | per user |
| `POST /forms/{id}/submit` | 5 / min | per user |
| `GET /notifications` | 60 / min | per user |
| `DELETE /notifications` | 30 / min | per user |
| `POST /dm/conversations/{id}/messages` | 30 / min | per user |
| `GET /dm/conversations` | 60 / min | per user |

Post creation is additionally limited to **50 posts per user per day** (Redis counter, resets at midnight UTC). Error code `SYS_429` is returned when this limit is reached.

### 6.3 WebSocket Connection Limits

| Limit | Value |
|---|---|
| Messages per minute per connection | 60 |
| Maximum message size | 64 KB |
| Idle timeout (no PONG response) | 90 seconds |

---

## 7. Real-Time Connection Security

### 7.1 Ticket-Based WebSocket Authentication

WebSocket connections do not use cookie-based authentication because browsers send cookies on the WebSocket upgrade request via `Cookie` headers, which are not CSRF-protected and can be triggered cross-origin.

Instead, the platform uses **one-time tickets**:

1. The authenticated client calls `POST /auth/ws-ticket` (cookie is sent automatically on this standard HTTP request).
2. The server generates a cryptographically random ticket, stores it in Redis with a **30-second TTL**, and returns it.
3. The client connects: `ws://host/api/v1/ws?ticket=<ticket>`
4. The server validates the ticket on connect and **immediately deletes it from Redis** (single-use).

An expired ticket, an already-used ticket, or a missing ticket all result in immediate connection rejection. The 30-second window is narrow enough to prevent replay attacks.

### 7.2 WebSocket Connection Limits and Session Revalidation

Two independent limits protect the WebSocket layer:

| Limit | Value | Enforcement |
|---|---|---|
| Concurrent connections per IP | 5 | Nginx `limit_conn ws_conn` |
| Concurrent connections per authenticated user | 5 | Backend in-memory counter (closes oldest with code 4006) |
| Messages per connection per minute | 60 | Redis rate counter |
| Maximum message size | 64 KB | Backend byte check on receive |
| Idle timeout (no PONG) | 90 seconds | Server-initiated close |

Additionally, the server re-validates each connection's session JTI against Redis every **60 seconds** during the connection lifetime. If the JTI has been revoked (e.g., the user changed their password or an admin force-logged-out the user on a different device), the connection is immediately closed.

### 7.3 Forced Logout Delivery

When a user is banned, the server publishes a `FORCE_LOGOUT` message to the user's Redis Pub/Sub channel. All Uvicorn workers receive the message and push it to any connected WebSocket belonging to that user, regardless of which worker holds the connection. This ensures bans take effect in real time across all active sessions and all workers.

---

## 8. Network & Infrastructure Security

### 8.1 Private Service Network

Services are isolated across two Docker bridge networks (`frontend-net` and `backend-net`). Only Nginx is exposed to the host. The database, cache, and object storage are unreachable from the frontend tier.

```
Internet --> Nginx (:3000 / :3443)
                |
         [frontend-net]
                |-- FastAPI     :8000  (bridges both networks)
                |
         [backend-net]
                |-- FastAPI     :8000  (bridges both networks)
                |-- PostgreSQL  :5432  (internal only)
                |-- Redis       :6379  (internal only)
                `-- MinIO       :9000  (internal only)
```

### 8.2 TLS Termination

TLS is terminated at Nginx. The Let's Encrypt certificate workflow (`scripts/init-letsencrypt.sh`) and automated renewal (`scripts/renew-certs.sh`) are included in the repository. In production, HTTP is redirected to HTTPS at the Nginx level.

### 8.3 Search Engine Blocking

All responses include `X-Robots-Tag: noindex, nofollow`. A `robots.txt` with `Disallow: /` is served. This prevents academic content (which may include unpublished research or restricted discussions) from being indexed by search engines.

### 8.4 Redis Memory Safety

Redis is configured with:

**Development:**
- `maxmemory 256mb` — hard cap to prevent unbounded memory growth
- `maxmemory-policy allkeys-lru` — evicts least-recently-used keys when the cap is reached
- AOF disabled — Redis is used for ephemeral state in development

**Production:**
- `maxmemory 512mb` — larger cap for production workload
- `maxmemory-policy volatile-lru` — only evicts keys that have a TTL set; keys without TTL (e.g., permanent ban entries) are never evicted
- AOF enabled (`appendfsync everysec`) — provides crash recovery; at most one second of data loss
- Dangerous commands disabled: `FLUSHALL`, `FLUSHDB`, `KEYS`, `DEBUG` are removed at startup. `CONFIG` is renamed to an unpublished token to prevent live reconfiguration.

### 8.5 Docker Container Hardening

All application containers run with the principle of least privilege:

| Measure | Applied to | Description |
|---|---|---|
| `cap_drop: ALL` | All services | Drops all Linux capabilities at container start |
| `security_opt: no-new-privileges:true` | All services | Process cannot acquire additional privileges via setuid/setgid |
| `read_only: true` | FastAPI (prod) | Root filesystem is read-only; only `/tmp` and `~appuser` are writable (via `tmpfs`) |
| `tmpfs: /tmp` (100MB) | FastAPI (prod) | In-memory `/tmp` with a hard size cap to prevent disk exhaustion via temp files |
| Minimal capabilities re-added | All services | Only `CHOWN`, `SETGID`, `SETUID`, `DAC_OVERRIDE` are re-added |

### 8.6 Celery Worker Memory Safety

Celery workers are started with `--max-memory-per-child=256000` (KB). A worker that exceeds 256 MB is automatically recycled by Celery, preventing slow memory leaks in long-running task handlers from accumulating indefinitely.

---

## 9. GDPR & Privacy Compliance

### 9.1 Right to Erasure (Article 17)

Account deletion does **not** hard-delete rows. Instead, all personally identifiable information is overwritten:

| Field | Anonymized Value |
|---|---|
| `username` | `Deleted_User_{UUID}` |
| `display_name` | `Deleted User` |
| `email` | `deleted_{UUID}@deleted.invalid` |
| `password_hash` | Replaced with a random invalid hash |
| `avatar_key` | Cleared |
| `bio` | Cleared |

Foreign keys (post author references, comment author references) are preserved, so the database remains consistent. The content itself may be separately moderated or removed, but the user's PII is gone.

### 9.2 Privacy Consent Recording

A privacy consent modal is shown at:

- Registration
- First login
- Every new guest session

Consent is recorded in the `privacy_consents` table (for members) or a Redis key (for guests). The timestamp and IP address are stored with each consent record.

### 9.3 Data Residency Disclosure

The platform discloses its data residency location (single-server, Hong Kong) in the privacy consent modal. Users must acknowledge this before proceeding.

---

## 10. Audit Trail

Every sensitive action is written to the `audit_logs` table with:

| Field | Description |
|---|---|
| `actor_id` | User ID of the person who performed the action |
| `action` | One of the event types listed below |
| `target_id` | ID of the affected entity (user, invite code, etc.) |
| `ip_address` | Client IP at time of action |
| `created_at` | UTC timestamp |

### Audited Event Types

| Event | Trigger |
|---|---|
| `LOGIN` | Successful authentication |
| `LOGOUT` | User-initiated logout |
| `PASSWORD_CHANGE` | Password update |
| `ACCOUNT_DELETE` | GDPR erasure (self-initiated) |
| `ROLE_CHANGE` | Admin changes a single user's role |
| `BULK_ROLE_CHANGE` | Admin changes multiple users' roles at once |
| `BAN` | Admin bans a user |
| `UNBAN` | Admin removes a ban |
| `INVITE_CODE_REVOKE` | Admin soft-revokes an invite code |
| `INVITE_CODE_DELETE` | Admin hard-deletes an invite code |
| `IP_BAN` | Super Admin bans an IP address |
| `IP_UNBAN` | Super Admin removes an IP ban |
| `APPLICATION_REVIEW` | Admin approves or rejects a membership application |
| `ADMIN_DELETE_USER` | Admin hard-deletes a user account |
| `ADMIN_DELETE_POST` | Admin removes a post |
| `BULK_DELETE_POSTS` | Admin bulk-deletes posts |
| `DM_ADMIN_VIEW` | Super Admin reads a DM conversation via the moderation endpoint |
| `SITE_EXPORT_START` | Super Admin initiates a site data export |
| `SITE_EXPORT_DELETE` | Super Admin deletes a site data export archive |
| `file_delete` / `admin_file_delete` | User or Admin deletes an uploaded file |

The audit log is paginated and accessible only to Super Admins at `GET /admin/audit-logs`. It is append-only — no update or delete endpoint exists for audit records.

---

## 11. Idempotency

All `POST` and `PUT` requests support the **`Idempotency-Key`** header. When a client includes this header, the server caches the response in Redis and replays it for any identical re-submission, preventing duplicate side-effects from network retries.

| Property | Value |
|---|---|
| Header name | `Idempotency-Key` |
| Allowed characters | Alphanumeric + dashes, max 256 chars |
| Cache TTL | 5 minutes |
| Key namespace | `idempotency:{user_id}:{key}` (per-user, no cross-user leakage) |
| Concurrent protection | A second request with the same key while the first is still processing returns 409 |
| Cached status codes | 2xx and 4xx (except 429); 5xx responses are not cached so the client can retry |
| Max cached body | 512 KB |

The user ID is extracted from the JWT `sub` claim and prepended to the Redis key, ensuring that two users who accidentally submit the same key string never receive each other's responses.

---

## 12. Threat Model Summary

| Threat | Mitigations |
|---|---|
| Credential stuffing / brute force | CAPTCHA on login, per-IP rate limiting (Nginx + Redis), Argon2id hashing (slow by design) |
| Session hijacking via token theft | HttpOnly cookies (XSS cannot read `access_token`), short TTLs, dual-layer validation |
| Session fixation / replay | Single-use WebSocket tickets (30s TTL), `jti` blacklist on logout |
| CSRF | Double-submit cookie pattern on all mutating requests |
| XSS | DOMPurify (frontend rendering) + nh3 (backend storage), both applied independently |
| SQL injection | asyncpg parameterized queries throughout, `websearch_to_tsquery` for FTS |
| File-based malware | Magic byte validation, PDF sanitization via pikepdf/qpdf, VirusTotal async scanning |
| Privilege escalation | `require_role` dependency on every protected endpoint, service-layer ownership checks |
| Enumeration / scraping | Rate limiting, robots.txt + X-Robots-Tag, guest capacity limits |
| DoS / resource exhaustion | Nginx rate limiting, Redis memory cap + LRU eviction, Celery worker memory recycling, per-context upload size limits (10–50 MB) |
| Data exposure via storage | All MinIO/R2 objects private, short-lived presigned URLs (15 min for albums/exports, 1 h for general files), internal hostname never exposed to browser |
| Unauthorized force-logout evasion | Forced logout delivered over WebSocket (not polling), backed by Redis Pub/Sub across all workers |
| PII leakage in audit/contributor data | GitHub usernames kept server-side only; avatars proxied through backend with 1h cache |
