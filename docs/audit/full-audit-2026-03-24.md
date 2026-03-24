# Full System Audit Report — 2026-03-24

**Scope:** All backend endpoints, services, repositories, frontend views/stores/composables, infrastructure configs.
**Method:** Deep code review of 100+ files across 6 parallel analysis passes.
**Deduplication:** Cross-referenced all agent findings; removed false positives and duplicates.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH | 12 |
| MEDIUM | 30 |
| LOW | 28 |
| **Total** | **72** |

---

## CRITICAL (2)

### CR-01: mXSS via unsanitized `v-html` in post content segments

**Files:** `frontend/src/composables/usePostDetail.ts:220-233`, `frontend/src/views/forum/PostDetailView.vue:270`
**Category:** Security — XSS

The `contentSegments` computed property sanitizes post content with DOMPurify, then parses the result with `DOMParser`, manipulates the DOM (replacing `<a>` tags with text markers), reads back `wrapper.innerHTML`, and splits the resulting HTML string. The split fragments are passed directly to `v-html` **without re-sanitization**.

This is a textbook mutation XSS (mXSS) vector: the sanitize→parse→serialize→split pipeline can produce HTML that DOMPurify would have stripped, because browser DOM parsing semantics differ from string-level sanitization. The `renderMentions` function in `utils/html.ts` correctly re-sanitizes after similar manipulation; this code path does not.

**Fix:** Run `DOMPurify.sanitize()` on each HTML segment before pushing to `segments`.

---

### CR-02: Redis eviction policy `volatile-lru` will OOM-reject writes instead of evicting

**Files:** `docker-compose.yml:135`, `docker-compose.prod.yml:176`
**Category:** Infrastructure — Availability

Both dev and prod compose files use `--maxmemory-policy volatile-lru`. This policy only evicts keys with an explicit TTL. Keys without TTL (e.g., certain cache keys, pub/sub state) will never be evicted, causing Redis to reject writes with OOM errors when memory is full — potentially breaking authentication, rate limiting, and WebSocket ticket validation.

The MEMORY.md documents the intended policy as `allkeys-lru`, but the actual config is `volatile-lru`.

**Fix:** Change both compose files to `--maxmemory-policy allkeys-lru`.

---

## HIGH (12)

### H-01: User `anonymize_user` — PII wipe and data cleanup are not atomic

**File:** `backend/app/services/user.py:247-464`
**Category:** Bug — Data Integrity / GDPR

The anonymization happens in two phases: (1) `user_repo.anonymize()` wipes PII (line 247), which commits immediately, then (2) a separate transaction cleans up posts/comments/DMs/friendships (lines 259-464). If phase 2 fails, the user's PII is destroyed but all their content remains linked to the anonymized record — violating GDPR (data remains associated) and creating orphaned data.

**Fix:** Wrap both phases in a single transaction, or implement a saga with rollback capability.

---

### H-02: Album operations have TOCTOU race conditions (3 instances)

**File:** `backend/app/services/album.py:145-156, 221-252, 939-996`
**Category:** Bug — Race Condition

In `delete_album`, `set_cover_from_photo`, and `delete_photo`, the permission check (`find_album_by_id` without `FOR UPDATE`) runs outside the transaction. Between the check and the transactional operation, another request could transfer ownership or delete the album/photo. The delete operation would then execute without valid authorization.

**Fix:** Move permission checks inside the transaction using `SELECT ... FOR UPDATE`.

---

### H-03: DM `edit_message` bypasses conversation char cap

**File:** `backend/app/services/dm.py:400-419`
**Category:** Bug — Business Logic

When editing a DM to be longer, `total_chars` is updated by the char delta, but there is no check against `DM_CHAR_CAP_PER_CONVERSATION`. Unlike `send_message` which enforces the cap by deleting old messages, `edit_message` simply increases the counter. A user could repeatedly edit a message to grow a conversation far beyond the 50K char cap.

**Fix:** Add cap check in `edit_message`; reject edits that would exceed the cap, or trigger the same cap-enforcement logic used in `send_message`.

---

### H-04: Form soft-delete leaks file_upload answers in MinIO

**File:** `backend/app/repositories/form_repo.py:563-567`, `backend/app/services/form.py:622`
**Category:** Bug — Resource Leak

When a form is soft-deleted, `form_responses` are hard-deleted from the DB, but file_upload answers pointing to MinIO objects are never cleaned up. The storage quota is never refunded to respondents either. Only the form's banner is cleaned up.

**Fix:** Before deleting responses, scan for `file_upload` type answers, collect their storage keys, delete from MinIO, and refund quotas.

---

### H-05: DM read receipt handler zeroes unread count for wrong direction

**File:** `frontend/src/stores/dm.ts:193-207`
**Category:** Bug — Business Logic

`readReceiptFromWebSocket` unconditionally zeroes `conv.unread_count` and decrements `unreadCount` when a `DM_READ` event arrives. But a `DM_READ` event means the **other** user read **your** messages. If you also have unread messages from them, your unread counts are incorrectly zeroed. The unread count should only be zeroed when the current user marks a conversation as read.

**Fix:** Only zero unread count when the current user is the reader (not the sender whose messages were read).

---

### H-06: SIG notification block/dedup checks silently bypassed when Redis uninitialized

**File:** `backend/app/tasks/event_retry.py:175-202`
**Category:** Bug — Security

`_is_blocked_for_sig` and `_check_idempotent_for_sig` call `get_redis()` without `_ensure_redis()`. If Redis wasn't initialized in the Celery worker, exceptions are caught and return `False` / `True` — meaning block checks are bypassed (blocked users receive SIG notifications) and dedup is disabled (duplicate notifications sent).

**Fix:** Call `_ensure_redis()` at the start of `_async_notify_sig_members`, or add it to both helper functions.

---

### H-07: DM event handler — WS failure blocks DB notification creation

**File:** `backend/app/event_handlers.py:560-565`
**Category:** Bug — Reliability

If `send_to_user(recipient_id, ws_payload)` raises (line 562), the exception is re-raised (line 565), which means the persistent DB notification (lines 576-595) is **never created**. When WebSocket is down but DB is healthy, recipients lose both real-time AND persistent notifications. The event bus will retry, but this causes unnecessary delays.

**Fix:** Catch the WS exception without re-raising, so DB notification creation always executes.

---

### H-08: DM conversation list attachment URLs always null (broken feature)

**File:** `backend/app/converters/dm_converter.py:47-73`, `backend/app/services/dm.py:564-584`
**Category:** Bug — Broken Feature

The `async_row_to_conversation` converter does NOT include `attachment_key` in the output dict. The service layer's `list_conversations` accesses `last_msg.get("attachment_key")` which is always absent. Presigned URL generation for the last message's attachment in conversation list view **never fires**. Conversations with file attachments always show `attachment_url: null`.

**Fix:** Include `attachment_key` in the converter output (used internally, stripped before response), or pass the raw row's key to the service layer.

---

### H-09: No SSL/TLS for PostgreSQL and Redis connections in production

**Files:** `backend/app/core/database.py:11-17`, `backend/app/core/redis.py:9-18`, `backend/app/celery_app.py:7-8`
**Category:** Security — Transport Encryption

Database, Redis, and Celery broker connections all use plaintext protocols. In Docker bridge networking, if any container is compromised, an attacker can sniff DB credentials, session tokens, and all query data. There is no configuration path to enable TLS.

**Fix:** Add `ssl` parameter to `asyncpg.create_pool()` gated by env var; support `rediss://` prefix for Redis/Celery.

---

### H-10: Captcha uses `random.choices()` instead of `secrets`

**File:** `backend/app/services/captcha.py:23`
**Category:** Security — Weak Randomness

The captcha code is generated using Python's Mersenne Twister PRNG, which is not cryptographically secure. An attacker observing enough captcha outputs could predict future codes.

**Fix:** Replace `random.choices(chars, k=CAPTCHA_LENGTH)` with `"".join(secrets.choice(chars) for _ in range(CAPTCHA_LENGTH))`.

---

### H-11: Vote score race condition — CTE lacks `FOR UPDATE`

**File:** `backend/app/repositories/vote_repo.py:31-54`
**Category:** Bug — Data Integrity

The `upsert_vote` CTE reads the old vote value (`SELECT vote FROM comment_votes`) without `FOR UPDATE`. Concurrent votes from the same user on the same comment could both see the same old value, calculate the same delta, and both apply it — making the score off by one.

**Fix:** Add `FOR UPDATE` to the old-vote CTE select.

---

### H-12: HSTS header missing `preload` directive

**File:** `nginx/snippets/security-headers.conf.template:18`
**Category:** Security — Transport

Without `preload`, the site is not eligible for browser HSTS preload lists, leaving users vulnerable to SSL stripping on their first visit.

**Fix:** Add `; preload` to the HSTS header.

---

## MEDIUM (30)

### Backend — Auth & Security

| # | File | Issue |
|---|------|-------|
| M-01 | `services/captcha.py:50` | Captcha verification uses `==` instead of `hmac.compare_digest()` — timing side-channel |
| M-02 | `services/auth.py:375` | `RETURNING *` includes `password_hash` in memory (defense-in-depth violation) |
| M-03 | `core/rate_limit.py:41` | `X-Forwarded-For` fallback takes `[-1]` (last proxy) instead of `[0]` (client); docstring contradicts code |
| M-04 | `endpoints/applications.py:40-75` | `apply_for_membership` has no rate limiting or captcha — spam/DoS vector |

### Backend — Business Logic

| # | File | Issue |
|---|------|-------|
| M-05 | `services/dm.py:143-167→243` | DM friendship check and `send_message_atomic` run in separate transactions — narrow TOCTOU on `dm_friends_only` |
| M-06 | `services/post.py:188-265` | `update_post` does not sanitize HTML or check for empty content after sanitization |
| M-07 | `services/album.py:473-508` | `approve_member` permission check and status update not in a single transaction |
| M-08 | `services/comment.py:42-44` | Parent self-reply check `parent_uuid == comment_id` is dead code (always false — comment_id is freshly generated) |
| M-09 | `services/form.py:578-582` | Form `file_upload` answer key not validated for file ownership — potential IDOR |
| M-10 | `endpoints/posts.py:194-205` | Post reaction endpoint has no blocked-user check |
| M-11 | `endpoints/comments.py:117-134` | Comment reaction endpoint has no blocked-user check |
| M-12 | `repositories/comment_repo.py:183-208` | Deleting parent comment — child soft-delete count and `answer_count` may drift |
| M-13 | `services/notification.py:13-44` | No rate limiting on notification creation — flood vector via event bus |
| M-14 | `services/form.py:259` | `multiple_choice` percentage can sum >100% — misleading stats |
| M-15 | `schemas/form.py:14-61` | Rating question missing `min`/`max` cross-validation (min could exceed max) |
| M-16 | `repositories/user_repo.py:210-240` | `list_all` returns `total=0` on empty last page instead of real count |

### Backend — Tasks & Infrastructure

| # | File | Issue |
|---|------|-------|
| M-17 | `tasks/cleanup.py:179-189` | Non-atomic file-delete + quota-decrement — quota drift on partial failure |
| M-18 | `tasks/dm_cleanup.py:89-122` | Text cleanup race condition — concurrent runs may double-decrement `total_chars` |
| M-19 | `converters/dm_converter.py:6-31` | Recalled message content not stripped by converter — relies entirely on DB NULL; replication lag could expose content |
| M-20 | `tasks/view_sync.py:33-43` | Fragile `result.split()[-1]` parsing of asyncpg UPDATE return value |
| M-21 | `tasks/form_export.py:107-126` | Theoretical CSV injection through dict stringification of form answers |
| M-22 | `tasks/recommendations.py:53` | Long-held advisory lock during full recommendation recompute blocks other tasks |
| M-23 | `tasks/cleanup.py + virustotal.py` | `_decrement_owner_storage` and `_ensure_pool` duplicated across 4 files — DRY violation / maintenance hazard |
| M-24 | `services/preferences.py:5-10` | `_DEFAULTS` missing `dm_friends_only: False` — frontend gets `undefined` for new users |

### Frontend

| # | File | Issue |
|---|------|-------|
| M-25 | `stores/auth.ts:20-41` | `expiresAt` in localStorage enables client-side session extension (API calls still fail, but route guards and UI elements can be bypassed) |
| M-26 | `composables/useWebSocket.ts:203-212` | Visibility handler closure leak when multiple consumers register — only last consumer's closure survives |
| M-27 | `composables/useFormBuilder.ts:124-134` | Global `Ctrl+Z`/`Ctrl+Shift+Z` listener steals undo/redo from TiptapEditor and native inputs |
| M-28 | `composables/usePostDetail.ts:620-623` | `scanPollTimers` array grows unbounded for pending image scans |

### Infrastructure

| # | File | Issue |
|---|------|-------|
| M-29 | `nginx/conf.d/default.conf:51` | nginx `client_max_body_size` 110MB vs FastAPI 50MB limit — wastes memory buffering oversized uploads |
| M-30 | `docker-compose.prod.yml:93` | gunicorn `--timeout 120` — 4 concurrent slow requests exhaust all workers |

---

## LOW (28)

### Backend

| # | File | Issue |
|---|------|-------|
| L-01 | `services/auth.py:90-100` | `destroy_session` does not verify JTI ownership before deleting session key |
| L-02 | `endpoints/ws.py:51-57` | WebSocket `accept()` called before connection limit check — wastes resources on rejected connections |
| L-03 | `schemas/user.py:76` | `CreateAccountRequest.invite_code` has no `max_length` — multi-MB string goes to SQL |
| L-04 | `core/csrf.py:38-44` | CSRF token is deterministic given JTI — heartbeat "regeneration" is a no-op |
| L-05 | `endpoints/notifications.py:59-68` | Bulk delete with empty IDs array deletes ALL user notifications |
| L-06 | `endpoints/files.py:320` | 1-year immutable cache on files conflicts with post-scan malware detection |
| L-07 | `repositories/reaction_helpers.py:20-80` | No limit on reaction types per entity — JSONB column can grow unboundedly |
| L-08 | `services/comment.py:16-22` | `mentions` list has no length limit — thousands of mentions → expensive query + notification flood |
| L-09 | `repositories/sig_repo.py:273-320` | `update_member_role_in_conn` silently inserts new member if not found |
| L-10 | `repositories/album_repo.py:268-294` | `update_member_status` has optional `album_id` parameter — cross-album manipulation if caller omits it |
| L-11 | `core/storage.py:100-111` | Presigned URL `filename` doesn't escape `"` — Content-Disposition header injection |
| L-12 | `tasks/dm_cleanup.py:36-55` | No orphan file cleaner for `dm/` prefix — leaked DM files never cleaned |
| L-13 | `tasks/event_retry.py:51-59` | Redis not initialized for event_retry — retries silently fail on cold worker |
| L-14 | `schemas/user.py:56` | `display_name` update allows empty string `""` — UI display issues |
| L-15 | `services/audit.py:50` | `uuid.UUID(user_id_filter)` not try/excepted — invalid UUID returns 500 instead of 400 |
| L-16 | `endpoints/dm.py:190` | DM attachment filename stored unsanitized — XSS risk if frontend ever uses `v-html` |

### Frontend

| # | File | Issue |
|---|------|-------|
| L-17 | `stores/notifications.ts:48-60` | `markRead`/`markAllRead` log errors unconditionally in production (not gated by `import.meta.env.DEV`) |
| L-18 | `views/DMView.vue` (many lines) | Hardcoded English strings throughout DM views — not using i18n `t()` |
| L-19 | `composables/useDraft.ts:81-101` | Corrupt JSON draft silently removed from localStorage — user loses work with no notification |
| L-20 | `composables/useFormBuilder.ts:523` | `sigId()!` non-null assertion — sends `undefined` to API if route params not loaded |
| L-21 | `views/RegisterView.vue:84-111` | No client-side username format validation |
| L-22 | `utils/apiValidation.ts:1-15` | `assertShape` silently passes invalid data in production — runtime crashes manifest as unrelated errors |

### Infrastructure

| # | File | Issue |
|---|------|-------|
| L-23 | `docker-compose.yml:261-265` | Dev compose uses single flat network — all services can reach Postgres/Redis directly |
| L-24 | `scripts/init-minio.sh:12-13` | Hardcoded default `changeme_minio` if env vars not set |
| L-25 | `scripts/backup.sh:80` | `StrictHostKeyChecking=accept-new` — MITM on first backup connection |
| L-26 | `docker-compose.prod.yml:241` | No `--pidfile` for Celery Beat — duplicate schedulers possible on unclean restart |
| L-27 | `nginx/conf.d/default.conf:88-99` | WebSocket location missing security headers include |
| L-28 | `scripts/compute_stats.py:47` | `subprocess.check_output` with `shell=True` on hardcoded commands |

---

## False Positives Eliminated

| Claim | Reason Rejected |
|-------|----------------|
| Vue Router child `meta` replaces parent `meta` (route guard bypass) | Vue Router 4 **merges** child and parent `meta` via `matched` records. Verified: `to.meta.requiresAuth` is inherited by all admin children. |
| Album `delete_album` uses two separate connections for permission check | Verified: both permission check and transaction use the same `conn` within one `pool.acquire()` block. The TOCTOU is real (no `FOR UPDATE`) but less severe than claimed. |
| DM `send_message_atomic` doesn't re-check friendship | The block re-check inside `send_message_atomic` partially mitigates; only friendship-only preference has a narrow gap. Downgraded from CRITICAL to MEDIUM. |

---

## Top 10 Priority Fixes

1. **CR-01** — mXSS in contentSegments: Add `DOMPurify.sanitize()` on each HTML segment
2. **CR-02** — Redis eviction policy: Change to `allkeys-lru` in both compose files
3. **H-01** — Atomic user anonymization: Wrap PII wipe + cleanup in single transaction
4. **H-05** — DM unread count: Only zero when current user is the reader
5. **H-07** — DM event handler: Don't re-raise WS exception; let DB notification proceed
6. **H-08** — Conversation list attachments: Include `attachment_key` in converter
7. **H-06** — SIG notification Redis init: Add `_ensure_redis()` call
8. **H-10** — Captcha randomness: Switch to `secrets.choice()`
9. **M-24** — Preferences defaults: Add `dm_friends_only: False` to `_DEFAULTS`
10. **M-01** — Captcha timing: Use `hmac.compare_digest()`
