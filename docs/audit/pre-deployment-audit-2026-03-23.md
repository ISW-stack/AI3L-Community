# AI3L Community — Pre-Deployment Comprehensive Audit Report

**Date:** 2026-03-23
**Scope:** Full-stack application audit covering authentication, API layer, frontend, infrastructure, database, and DM/WebSocket systems
**Method:** Automated deep code review by 6 parallel analysis agents, each reading source code directly

---

## Executive Summary

| Category | CRITICAL | HIGH | MEDIUM | LOW | INFO | Total |
|---|---|---|---|---|---|---|
| Authentication & Authorization | 0 | 0 | 2 | 2 | 11 | 15 |
| Backend API & Data Integrity | 0 | 0 | 7 | 18 | 7 | 32 |
| Frontend Security & State | 0 | 0 | 3 | 7 | 8 | 18 |
| Infrastructure & Production | 2 | 6 | 11 | 8 | 0 | 27 |
| DM & WebSocket | 0 | 4 | 10 | 8 | 0 | 22 |
| Database & SQL Layer | 0 | 1 | 8 | 12 | 5 | 26 |
| **Total** | **2** | **11** | **41** | **55** | **31** | **140** |

**Overall Assessment:** The application is architecturally sound with strong authentication, consistent error handling, and good transaction safety. However, **infrastructure hardening is the primary blocker for production deployment** — 2 critical and 6 high findings exist in the infrastructure layer. The DM subsystem (newest feature) has the highest density of issues. No SQL injection or critical XSS vulnerabilities were found.

---

## CRITICAL Findings (2)

### INFRA-11 | HTTPS server block contains `YOUR_DOMAIN` placeholder
- **File:** `nginx/conf.d/default.conf:127,236`
- **Description:** The HTTPS server block and HTTP-to-HTTPS redirect both have literal `YOUR_DOMAIN` as the `server_name`. The `docker-entrypoint.sh` uncomments these blocks when TLS certs exist but does NOT substitute the domain name. The operator must manually edit the file.
- **Impact:** HTTPS will not function at all in production without manual intervention. If the operator only enables certs without editing, nginx will not route to the correct server block.

### INFRA-19 | `.env` file with real secrets exists on cloud-synced path
- **File:** `.env`
- **Description:** The `.env` file contains real production-grade secrets (`SECRET_KEY`, `JWT_SECRET_KEY`, `SUPER_ADMIN_PASSWORD`). While `.env` is in `.gitignore`, the project directory is on OneDrive (`C:\Users\Leolo\OneDrive\桌面\`), meaning these secrets are synced to Microsoft cloud storage.
- **Impact:** Secret exposure through cloud sync. Anyone with access to the OneDrive account can read production secrets.

---

## HIGH Findings (11)

### INFRA-01 | Backend Dockerfile is not multi-stage
- **File:** `backend/Dockerfile`
- **Description:** Single-stage build retains `gcc` and `libpq-dev` compilation tools in production image.
- **Impact:** Increased attack surface and image size (~200MB overhead).

### INFRA-06 | Single flat Docker network — no tier isolation
- **File:** `docker-compose.prod.yml:250-253`
- **Description:** All containers (nginx, fastapi, postgres, redis, celery) share one `ai3l-network`. Nginx can directly reach PostgreSQL and Redis.
- **Impact:** Violates defense-in-depth; if nginx is compromised, attacker has direct DB/cache access.

### INFRA-12 | Duplicate HSTS headers in production HTTPS
- **Files:** `nginx/conf.d/default.conf:150` + `nginx/snippets/security-headers.conf.template:18`
- **Description:** The HTTPS block adds `Strict-Transport-Security` directly AND includes `security-headers.conf` which also adds it. Duplicate header sent.
- **Impact:** Undefined browser behavior with duplicate HSTS headers.

### INFRA-13 | `CF-Connecting-IP` header trusted from any source
- **File:** `nginx/nginx.conf:14-17`
- **Description:** The `map` directive sets `$real_client_ip` from `$http_cf_connecting_ip` without `set_real_ip_from` restricting which upstream IPs can set this header.
- **Impact:** Any client can forge `CF-Connecting-IP` to spoof their IP, bypassing rate limits and IP bans.

### INFRA-20 | MinIO credentials at weak defaults
- **File:** `.env:47-48,55-56`
- **Description:** `MINIO_ROOT_USER=minioadmin`, `MINIO_ROOT_PASSWORD=changeme_minio`. The startup validator checks `S3_SECRET_ACCESS_KEY` but not MinIO root credentials.
- **Impact:** MinIO could start in production with default credentials, allowing unauthorized file access.

### INFRA-26 | No Docker container log management
- **File:** `docker-compose.prod.yml`
- **Description:** No `logging:` directives on any service. Docker uses `json-file` driver with no log rotation.
- **Impact:** Container logs will fill the production disk over time.

### DM-05 | No rate limiting on `unread-count` endpoint
- **File:** `backend/app/api/v1/endpoints/dm.py:58-64`
- **Description:** `GET /dm/unread-count` has no rate limit. Executes a JOIN query across `dm_messages` and `conversations`.
- **Impact:** DoS vector through rapid polling of a moderately expensive query.

### DM-08 | WebSocket drops silently on role change
- **File:** `backend/app/api/v1/endpoints/ws.py:105-119`
- **Description:** On role change, the old session key is deleted. WebSocket revalidation finds the missing key and closes the connection without sending a `ROLE_CHANGED` event first.
- **Impact:** User's role state becomes stale until reconnection. No notification of why the connection dropped.

### DM-13 | Char cap enforcement permanently orphans files in MinIO
- **File:** `backend/app/services/dm.py:265-283`
- **Description:** When the 20K char cap is exceeded, oldest messages are deleted (including their DB rows). Attachment cleanup runs outside the transaction. If it fails, the message row is already gone — no cleanup task can find the orphaned file.
- **Impact:** Files become permanently orphaned in MinIO with no detection/cleanup mechanism. Storage leak over time.

### DM-18 | No admin endpoint to moderate DM content
- **File:** `backend/app/api/v1/endpoints/dm.py`
- **Description:** All DM endpoints require the caller to be a conversation participant. No admin-level moderation endpoint exists.
- **Impact:** Administrators cannot investigate abuse reports involving DMs.

### DB-19 | Report status filter silently returns unfiltered results
- **File:** `backend/app/repositories/report_repo.py:5`
- **Description:** `_VALID_REPORT_STATUSES = {"PENDING", "REVIEWED", "DISMISSED"}` but the DB CHECK constraint allows `RESOLVED` (not `REVIEWED`). Filtering by "RESOLVED" fails the allowlist check, silently falls back to no filter, returning ALL reports.
- **Impact:** Admin report management is broken — filtering by "RESOLVED" status shows all reports instead.

---

## MEDIUM Findings (41)

### Authentication & Authorization (2)

| ID | Description | File |
|---|---|---|
| AUTH-01 | Username enumeration via timing oracle — non-existent user returns immediately without Argon2 hash, measurable ~100-300ms timing difference | `services/auth.py:20-29` |
| AUTH-02 | `X-Forwarded-For` takes last IP (`[-1]`) instead of first, contradicting its docstring. Mitigated by `X-Real-IP` from nginx | `core/rate_limit.py:39-42` |

### Backend API & Data Integrity (7)

| ID | Description | File |
|---|---|---|
| API-01 | `LoginRequest.username` missing `min_length`, allows empty string to hit DB | `schemas/auth.py:14` |
| API-03 | `AlbumAddMemberRequest.user_id` typed as `str` not UUID — causes 500 instead of 422 on malformed input | `schemas/album.py:86` |
| API-17 | `get_my_response` allows GUEST role — can probe form existence (404 vs 403) | `endpoints/forms.py:153` |
| API-19 | Category deletion does not null out posts' `category_id` — orphan FK references | `endpoints/categories.py:117` |
| API-21 | No per-minute rate limit on `POST /posts` — 20 posts can be created in seconds (daily cap exists) | `endpoints/posts.py:41` |
| API-22 | No rate limit on `PUT /users/me` — rapid profile updates possible | `endpoints/users.py:72` |
| API-24 | No rate limit on `DELETE /users/me` — expensive operation can be hammered | `endpoints/users.py:189` |
| API-31 | No rate limit on `GET /recommendations/friends` | `endpoints/recommendations.py:15` |
| API-37 | `get_sig_posts` allows GUEST access, inconsistent with `get_posts_list` which requires MEMBER+ | `endpoints/sigs.py:277` |

### Frontend Security & State (3)

| ID | Description | File |
|---|---|---|
| FE-01 | `contentSegments` in `usePostDetail` skips re-sanitization after DOM mutation — theoretical mXSS vector | `composables/usePostDetail.ts:184-236` |
| FE-03 | `forum-create` route missing `requiresMember` guard — guests can access post creation UI | `router/index.ts:80` |
| FE-15 | Album photo upload has no client-side file size validation — users upload oversized files, get server rejection after full upload | `components/albums/PhotoUploadModal.vue` |

### Infrastructure (11)

| ID | Description | File |
|---|---|---|
| INFRA-02 | `ddtrace` included unconditionally in production requirements | `backend/requirements.txt:24` |
| INFRA-04 | nginx `conf.d` volume not mounted read-only in production | `docker-compose.prod.yml:40` |
| INFRA-05 | nginx `snippets` volume not mounted read-only | `docker-compose.prod.yml:41` |
| INFRA-08 | `migrate` service uses full backend image for one Alembic command | `docker-compose.prod.yml:62-71` |
| INFRA-10 | Redis `appendonly no` in production — all data lost on restart (sessions, blacklist, rate limits) | `docker-compose.prod.yml:158` |
| INFRA-15 | Dev nginx config missing `write` rate limit zone | `nginx/conf.d.dev/default.conf` |
| INFRA-18 | WebSocket `proxy_read_timeout` 1h in prod vs 24h in dev — prod WS killed after 1 hour | `nginx/conf.d/default.conf:98` |
| INFRA-22 | `.env.production.example` has literal `yourdomain.com` placeholder for `COOKIE_DOMAIN` | `.env.production.example:63` |
| INFRA-23 | No startup validation that `COOKIE_DOMAIN` is set in production | `core/config.py` |
| INFRA-24 | `CORS_ORIGINS` defaults to localhost — no validation for non-localhost in production | `core/config.py:40` |
| INFRA-27 | Backup script creates `pg_dump | gzip` but never verifies backup integrity | `scripts/backup.sh` |
| INFRA-28 | No rollback mechanism beyond full database restore | `scripts/restore-db.sh` |
| INFRA-29 | Migration `downgrade()` functions contain `DROP TABLE CASCADE` — no safeguard against accidental downgrade | `alembic/versions/` |
| INFRA-31 | No monitoring/alerting in production stack (Datadog behind profile gate, Sentry DSN empty) | `docker-compose.prod.yml` |

### DM & WebSocket (10)

| ID | Description | File |
|---|---|---|
| DM-01 | `edit_message` does not reject empty content after sanitization (unlike `send_message`) | `services/dm.py:343-354` |
| DM-02 | Banned user check missing from `send_message` — only checks `is_deleted`, not `is_banned` | `services/dm.py:109-114` |
| DM-04 | `last_pong` closure pattern inconsistent with `activity` dict pattern | `endpoints/ws.py:67,90,164` |
| DM-09 | DM notification deduplication window is 5 minutes — multiple notifications per unread conversation | `event_handlers.py:576-595` |
| DM-12 | Unread count drifts in multi-tab scenarios (decremented twice) | `stores/dm.ts:119-207` |
| DM-15 | WebSocket pushes full message to sender sessions without validating sender_id origin | `event_handlers.py:567-573` |
| DM-16 | Conversation list `LATERAL` join excludes recalled messages — stale preview shown at top of list | `dm_repo.py:130-137` |
| DM-19 | `dm_friends_only` preference not re-checked inside advisory-locked transaction (TOCTOU) | `dm_repo.py:475-494` |
| DM-21 | Text cleanup task deletes messages without WebSocket notification to connected users | `tasks/dm_cleanup.py:78-125` |
| DM-25 | Conversation list query expensive — correlated subqueries for unread count, last message, blocks check | `dm_repo.py:86-166` |

### Database (8)

| ID | Description | File |
|---|---|---|
| DB-07 | `dm_messages` missing index for unread count query (fires on every page load) | `dm_repo.py:353-370` |
| DB-08 | `dm_messages` missing index for `mark_messages_read` and `find_conversations` unread subquery | `dm_repo.py:323-350` |
| DB-13 | `form_repo.find_by_sig` — COUNT and SELECT without transaction wrapper (inconsistent totals) | `form_repo.py:274-307` |
| DB-14 | `audit_repo.find_many` — same two-query pattern without transaction | `audit_repo.py:62-80` |
| DB-15 | `application_repo.find_many` — same pattern | `application_repo.py:28-58` |
| DB-16 | `sig_repo.find_many` — same pattern | `sig_repo.py:56-74` |
| DB-24 | `form_repo.find_by_sig` correlated subquery materializes full `form_responses` aggregate | `form_repo.py:285-306` |
| DB-25 | `album_repo.find_albums` runs 40 correlated subqueries per page (photo_count + member_count) | `album_repo.py:63-77` |
| DB-26 | `find_conversations` correlated subquery for unread count per conversation row | `dm_repo.py:118-124` |
| DB-30 | `form_repo.iter_responses_batched` holds DB connection for entire async iteration | `form_repo.py:448-492` |

---

## LOW Findings (55)

<details>
<summary>Click to expand all LOW findings</summary>

### Authentication (2)
| ID | Description |
|---|---|
| AUTH-03 | CSRF token is deterministic (HMAC of JTI) — no additional entropy beyond JTI binding |
| AUTH-04 | No session rotation on guest-to-member privilege escalation |

### Backend API (18)
| ID | Description |
|---|---|
| API-02 | `LoginRequest.password` missing `min_length` |
| API-04 | `AlbumCoverFromPhotoRequest.photo_id` not validated as UUID |
| API-05 | DM `send_message` content Form() has no length constraints at FastAPI level |
| API-06 | `FormUpdateRequest.questions` missing `min_length=1` — can create form with 0 questions |
| API-08 | DM `EditMessageRequest` no HTML sanitization at schema level (handled in service) |
| API-16 | `get_sig_forms` allows GUEST to view any SIG's form list |
| API-20 | Bulk delete posts cascades comments but not notifications — stale notification records |
| API-23 | No rate limit on avatar upload |
| API-25 | No rate limit on SIG form creation |
| API-26 | No rate limit on form update |
| API-27 | No rate limit on admin endpoints |
| API-28 | No rate limit on album creation |
| API-29 | No rate limit on unfriend |
| API-30 | No rate limit on membership application |
| API-32 | `get_comments` allows GUEST role |
| API-33 | `get_sig` and `get_sigs` allow GUEST role |
| API-35 | `BulkDeleteNotificationsRequest` with None deletes ALL notifications |
| API-36 | `get_posts_list` does not validate `category_id`/`sig_id`/`author_id` as UUIDs — 500 on malformed |

### Frontend (7)
| ID | Description |
|---|---|
| FE-04 | `isAuthenticated` relies on client-side localStorage on page load — brief stale auth flash |
| FE-06 | `requiresSuperAdmin` child routes rely on parent meta merge — structural fragility |
| FE-09 | DM store `fetchConversations` lacks mutual exclusion guard |
| FE-11 | Non-critical API failures silently swallowed (co-authors, citations, DM preferences) |
| FE-13 | Post edit drafts (`post_edit_draft_*`) not cleared on logout — persist in localStorage |
| FE-17 | `useDraft` has no max-age enforcement — weeks-old drafts restored without warning |

### Infrastructure (8)
| ID | Description |
|---|---|
| INFRA-03 | No separate requirements file for dev/test vs production |
| INFRA-07 | Celery Beat has no single-instance lock mechanism |
| INFRA-09 | PostgreSQL data volume has no encryption-at-rest or backup annotations |
| INFRA-16 | No `ssl_dhparam` configured for HTTPS |
| INFRA-17 | `X-Robots-Tag: noindex, nofollow` in production headers — prevents SEO |
| INFRA-25 | `.env.example` defaults `FASTAPI_DEBUG=true` — could be copied to production |
| INFRA-30 | `renew-certs.sh` does not copy renewed certs to nginx paths |
| INFRA-32 | `backup-db.sh` uses bare `docker compose` without `-f docker-compose.prod.yml` |

### DM & WebSocket (8)
| ID | Description |
|---|---|
| DM-03 | `find_messages` uses `SELECT *` exposing internal `attachment_key` to service layer |
| DM-06 | Recalled messages with NULL `attachment_key` match text cleanup query prematurely |
| DM-07 | Total message count includes recalled placeholder messages |
| DM-10 | Blocked users can still read historical messages by calling messages endpoint directly |
| DM-14 | `dm_friends_only` not re-checked on edit/recall operations |
| DM-17 | `handleLoadMore` has brief window for duplicate scroll fetches |
| DM-20 | File cleanup task logs thousands of individual warnings when MinIO is down |
| DM-22 | MEMORY.md says "50MB max" for DM attachments but code limit is 10MB |
| DM-23 | Non-PONG WebSocket client messages consume rate limit budget without effect |
| DM-24 | Presigned attachment URLs in WebSocket payloads expire after 1 hour |

### Database (12)
| ID | Description |
|---|---|
| DB-01 | Dynamic column names in `update_profile` — defended by allowlist + regex but pattern is fragile |
| DB-02 | Same pattern in `preferences_repo.upsert_preferences` |
| DB-03 | Same pattern in `form_repo.update` |
| DB-04 | Same pattern in `album_repo.update_album` and `update_photo` |
| DB-09 | `posts.created_at` standalone index missing for unfiltered listing |
| DB-10 | `invite_codes.created_by` FK not indexed |
| DB-11 | `forms.created_by` not indexed |
| DB-17 | `dm_repo.insert_message` and `increment_char_count` not in same transaction (mitigated by `send_message_atomic`) |
| DB-20 | Irreversible data migration clears all form descriptions (development artifact) |
| DB-21 | Column drop migration loses data on downgrade |
| DB-22 | CASCADE FK migration acquires ACCESS EXCLUSIVE locks — needs maintenance window |
| DB-23 | IP bans dedup keeps highest UUID, not latest `created_at` |
| DB-27 | `SELECT *` in 9+ repositories |
| DB-31 | Pool size actual (min=2, max=20) differs from documentation (min=10, max=30) |

</details>

---

## INFO Findings (31)

<details>
<summary>Click to expand all INFO findings</summary>

### Authentication (11)
- AUTH-05: JWT role claim trusted from token (acceptable — sessions revoked on role change)
- AUTH-06: WebSocket revalidation interval 5 minutes (acceptable tradeoff)
- AUTH-07: WebSocket ticket doesn't re-verify JTI freshness (30s window, no exploit path)
- AUTH-08: `COOKIE_SECURE` defaults to false in dev (correctly enforced in production)
- AUTH-09: `SameSite=Lax` allows top-level GET CSRF (mitigated by double-submit CSRF token)
- AUTH-10: Password policy is solid (8+ chars, upper/lower/digit/special, Argon2id)
- AUTH-11: Brute force protection is multi-layered (captcha + Redis rate limit + nginx rate limit)
- AUTH-12: All admin/sensitive endpoints have correct role enforcement
- AUTH-13: Task status endpoint uses string comparison (correct but fragile)
- AUTH-14: Concurrent session override well-handled (atomic swap + blacklist + Pub/Sub)
- AUTH-15: WebSocket ticket is properly single-use (`getdel`)

### Backend API (7)
- API-07: Keywords max_length on list, per-item validated separately (correct)
- API-10: Reaction toggle uses `FOR UPDATE` correctly
- API-11: Form submission uses advisory lock correctly
- API-12: Post update uses optimistic locking correctly
- API-14: No TODO/FIXME/HACK comments in backend
- API-15: All errors use AppError consistently (no raw HTTPException)
- API-34: DM attachment size constant and error message are consistent (10MB)

### Frontend (8)
- FE-02: All `v-html` usages properly sanitized via DOMPurify
- FE-05: No infinite redirect loop risk; auth guard logic is sound
- FE-07: No sensitive data in reactive state
- FE-08: Stores properly reset on logout
- FE-10: Central 401/403/429 error handling is consistent
- FE-12: No hardcoded secrets or API keys
- FE-14: No admin data fetched client-side for non-admins
- FE-16: All mutation forms use loading state to prevent double-submit
- FE-18: Draft auto-save mechanism is race-safe

### Database (5)
- DB-05: ORDER BY values from hardcoded maps (safe)
- DB-06: All queries use parameterized statements (no SQL injection)
- DB-18: Advisory locks correctly used
- DB-29: `COUNT(*) OVER()` pattern widely and correctly used
- DB-32: Connection leak safety ensured by context managers
- DB-33: No SSL for DB connections (acceptable for same-host Docker)

</details>

---

## Priority Action Items for Production Deployment

### Must Fix Before Deploy (CRITICAL + HIGH)

1. **INFRA-11** — Replace `YOUR_DOMAIN` placeholder with actual domain in nginx config, or add `envsubst` to entrypoint
2. **INFRA-19** — Move `.env` out of OneDrive-synced directory; use a secrets manager or non-synced path
3. **INFRA-13** — Add `set_real_ip_from` directives for Cloudflare IP ranges only
4. **INFRA-06** — Split Docker network into `frontend` (nginx) and `backend` (fastapi, postgres, redis, celery)
5. **INFRA-20** — Add startup validation for MinIO root credentials (reject `changeme` defaults)
6. **INFRA-26** — Add `logging:` directives with `json-file` driver, `max-size: 50m`, `max-file: 5`
7. **INFRA-01** — Convert backend Dockerfile to multi-stage build
8. **INFRA-12** — Remove duplicate HSTS header from either the server block or the security headers snippet
9. **DB-19** — Fix `_VALID_REPORT_STATUSES` to `{"PENDING", "RESOLVED", "DISMISSED"}` (match DB constraint)
10. **DM-13** — Record orphaned file keys before transaction commit; add cleanup mechanism
11. **DM-18** — Add admin DM moderation endpoint (even if read-only)
12. **DM-05** — Add rate limit to `GET /dm/unread-count`
13. **DM-08** — Send `ROLE_CHANGED` WebSocket event before closing connection on role change

### Should Fix Before Deploy (Top MEDIUM items)

14. **INFRA-10** — Enable Redis AOF persistence or RDB snapshots (session loss on restart)
15. **INFRA-31** — Set up monitoring (at minimum: health check pinging, disk usage alerts)
16. **AUTH-01** — Add dummy Argon2 hash for non-existent users to prevent timing oracle
17. **FE-03** — Add `requiresMember: true` to `forum-create` route
18. **API-37** — Change `get_sig_posts` to use `require_role` with MEMBER minimum
19. **DB-07 + DB-08** — Add composite index on `dm_messages` for unread count queries
20. **DM-02** — Add `is_banned` check to `send_message`

### Can Fix Post-Deploy (LOW priority)

- Rate limit gaps on mutation endpoints (API-21 through API-31)
- Client-side file size validation for album uploads (FE-15)
- Two-query pagination patterns without transactions (DB-13 through DB-16)
- Correlated subquery performance (DB-24 through DB-26)
- Draft lifecycle improvements (FE-13, FE-17)
- Minor schema validation gaps (API-03, API-04, API-36)

---

## Architecture Strengths Noted

The audit also identified several well-implemented patterns worth preserving:

- **Zero SQL injection risk** — all queries use parameterized statements with allowlisted dynamic column names
- **Consistent error handling** — all endpoints use `AppError`, no raw `HTTPException`
- **Solid auth design** — Argon2id, HttpOnly cookies, double-submit CSRF, multi-layered brute force protection
- **WebSocket tickets** — properly single-use via Redis `getdel`, 30s TTL
- **Optimistic locking** — post updates use version fields with `SELECT FOR UPDATE`
- **Form submission** — advisory locks prevent duplicate submissions under concurrent load
- **Frontend XSS protection** — DOMPurify on all `v-html`, Vue text interpolation for DM messages
- **Double-submit prevention** — all mutation forms use loading state to disable buttons
- **Session revocation** — role changes trigger immediate session invalidation via Redis

---

*Report generated by 6 parallel analysis agents performing deep source code review.*
*Total files analyzed: ~300+ across backend, frontend, infrastructure, and database layers.*
