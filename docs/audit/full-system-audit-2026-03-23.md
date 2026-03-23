# Full System Audit Report — 2026-03-23

**Scope:** Entire AI3L-Community application (backend, frontend, infrastructure)
**Method:** 6 parallel analysis agents covering auth/security, services/repos, frontend, infrastructure, API design, and recent feature changes
**Baseline:** Codebase at commit 34741cd (main branch)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 3 |
| MEDIUM   | 18 |
| LOW      | 19 |
| **Total** | **40** |

Previous audits have addressed the vast majority of common vulnerability classes. SQL injection, auth bypass, and classic XSS are not present. This report focuses on **remaining** functional bugs, logic errors, defense-in-depth gaps, and configuration issues.

---

## HIGH Severity

### H-01: `post_repo.search` fallback count query crashes on empty results

**File:** `backend/app/repositories/post_repo.py:599-604`

The search function builds conditions including `(s.id IS NULL OR s.is_deleted = false)` which references the `s` alias from `LEFT JOIN sigs`. When no results are found on a non-first page, the fallback count query runs:

```python
total = await conn.fetchval(
    f"SELECT COUNT(*) FROM posts p {where}",
    *count_params,
)
```

This query has `FROM posts p` only — no `LEFT JOIN sigs s`. PostgreSQL will raise `column "s" does not exist`, returning a 500 error.

**Impact:** Any search returning zero results on page > 1 causes a server crash.

**Fix:** Add the sigs LEFT JOIN to the fallback query:
```python
f"SELECT COUNT(*) FROM posts p LEFT JOIN sigs s ON p.sig_id = s.id {where}"
```

---

### H-02: `bulk_soft_delete` does not clean up embedded editor files

**File:** `backend/app/services/post.py:488-523`

The single-post `soft_delete_post` calls `_cleanup_post_files()` to remove MinIO objects and decrement `storage_used_bytes`. The `bulk_soft_delete` function cleans up citations, co-authors, and comments, but **skips file cleanup entirely**.

**Impact:** Admin bulk-delete leaves orphaned files in MinIO and inflates uploaders' storage quotas until the weekly orphan cleanup runs (7-day delay).

**Fix:** After the transaction, iterate deleted post IDs and call `_cleanup_post_files` for each (best-effort, matching the single-delete pattern).

---

### H-03: `anonymize_user` reports success on partial cleanup failure

**File:** `backend/app/services/user.py:227-491`

The function first anonymizes PII (sets `is_deleted=true`, overwrites personal fields) in one transaction, then cleans up related data (posts, comments, friendships, etc.) in a second transaction. If the second transaction fails, the exception is logged as a warning and the function returns `True`.

**Impact:** Partial anonymization — profile is wiped but content and social connections remain. The admin caller is not informed of the partial failure. This has GDPR compliance implications.

**Fix:** Either combine both operations into a single transaction, or return a status object indicating which cleanup steps succeeded/failed.

---

## MEDIUM Severity

### M-01: `preferred_language` validator only allows 7 of 17 supported locales

**File:** `backend/app/schemas/user.py:61-62`

```python
preferred_language: str | None = Field(
    None, max_length=10, pattern="^(en|zh-TW|zh-CN|ja|fr|es|de)$"
)
```

The frontend supports 17 locales (`ar`, `hi`, `id`, `it`, `ko`, `nan`, `pt`, `ru`, `tr`, `vi` are missing from the pattern). Users selecting these languages get a 422 validation error when saving preferences.

**Impact:** Functional bug — 10 languages are broken for profile save.

**Fix:** Update pattern to `^(en|zh-TW|zh-CN|ja|fr|es|de|ar|hi|id|it|ko|nan|pt|ru|tr|vi)$`.

---

### M-02: `post_process_citations` is not idempotent

**File:** `backend/app/core/file_validation.py:200-213`

The regex replaces `data-citation="true"` with `data-citation="true" class="citation"`. On a second invocation, the output already contains the match pattern, producing `class="citation" class="citation"` — invalid HTML with duplicate attributes.

**Impact:** Repeated edit-save cycles could accumulate duplicate class attributes on citation links.

**Fix:** Use a negative lookahead to skip already-processed elements:
```python
re.sub(r'data-citation\s*=\s*["\']true["\'](?!\s+class=)', ...)
```

---

### M-03: CSRF JTI-binding skipped when JWT is expired

**File:** `backend/app/core/csrf.py:128-129`

When `decode_access_token()` returns `None` (expired JWT), the middleware falls through to `call_next(request)` — the JTI-to-CSRF-token binding is not verified. The code relies on `get_current_user` to reject the request downstream.

**Impact:** Defense-in-depth gap. If any state-changing endpoint ever uses `get_optional_current_user` or omits auth, CSRF protection is bypassed for expired sessions.

**Fix:** Return 403 when JWT decode fails instead of falling through.

---

### M-04: Rate limiting keys on Cloudflare edge IPs in production

**File:** `backend/app/core/rate_limit.py:36-38`

`get_client_ip()` takes the rightmost `X-Forwarded-For` entry. Behind Cloudflare, nginx's `$proxy_add_x_forwarded_for` appends the Cloudflare edge IP (not the real client IP). The `X-Real-IP` header is correctly set via the `$real_client_ip` map, but `get_client_ip()` checks `X-Forwarded-For` first.

**Impact:** In production behind Cloudflare, rate limits key on a handful of edge IPs instead of real client IPs, making per-IP rate limiting ineffective.

**Fix:** Check `X-Real-IP` before `X-Forwarded-For` in `get_client_ip()`.

---

### M-05: Album cover replacement doesn't refund old uploader's storage

**File:** `backend/app/services/album.py:332-345`

When uploading a new album cover, the old cover file is deleted from MinIO and the new uploader's `storage_used_bytes` is incremented. But the **original uploader's** storage counter is never decremented.

**Impact:** Users' storage quotas silently decrease when others replace their album covers.

**Fix:** Look up the original uploader from the file key and decrement their `storage_used_bytes` before deleting.

---

### M-06: `ip_ban.unban_ip` TOCTOU race

**File:** `backend/app/services/ip_ban.py:38-57`

The function reads the IP address in one query, then deletes the ban in a separate call. Between these two operations, another admin could delete the same ban.

**Impact:** Redis cache may retain a stale "banned" entry for up to 300 seconds after a concurrent unban.

**Fix:** Combine into `DELETE FROM ip_bans WHERE id = $1 RETURNING ip_address`.

---

### M-07: `get_post_by_id` returns pre-increment view count

**File:** `backend/app/services/post.py:141-172`

When `increment_view=True`, the post is fetched first, then the view count is incremented. The response uses the pre-increment data.

**Impact:** The viewer who triggers the increment sees a `view_count` that is 1 less than the actual value.

**Fix:** Increment the count in the returned dict before conversion, or re-fetch after incrementing.

---

### M-08: Orphaned DM conversation rows on blocked-user send attempts

**File:** `backend/app/services/dm.py:224-226`

`find_or_create_conversation()` runs outside the `send_message_atomic()` transaction. If the block re-check inside the transaction rejects the message, the conversation row persists with zero messages.

**Impact:** Empty conversation rows accumulate in the database from blocked-user send attempts.

**Fix:** Move `find_or_create_conversation` inside the atomic transaction, or add periodic cleanup for zero-message conversations.

---

### M-09: `leave_co_authorship` uses fragile `str(None)` comparison

**File:** `backend/app/services/co_author.py:324`

```python
if str(co_author.get("user_id")) != user_id:
```

For external co-authors, `user_id` is `None`, so `str(None)` == `"None"`. If any code path ever passes `user_id="None"` as a string, it would incorrectly match any external co-author.

**Fix:** Add explicit None check:
```python
co_user_id = co_author.get("user_id")
if co_user_id is None or str(co_user_id) != user_id:
```

---

### M-10: `andMore` translation key missing from 16 locale files

**File:** `frontend/src/components/post/CoAuthorBadges.vue:31`

`t('coauthors.andMore', { count: remaining })` only exists in `en.ts`. All other 16 locale files are missing this key.

**Impact:** Non-English users see the raw key string when a post has more than 3 co-authors.

**Fix:** Add `andMore` to all locale files' `coauthors` section.

---

### M-11: Reactions JSONB leaks full user ID lists to all viewers

**File:** `backend/app/repositories/reaction_helpers.py:54-60`, `backend/app/schemas/post.py:70`

The `reactions` field returns `{"LIKE": ["uuid1", "uuid2"], ...}` — every authenticated user can see exactly who reacted to any post or comment.

**Impact:** Social graph leakage; reveals reading and approval patterns.

**Fix:** Return counts per reaction type plus the current user's own reactions, rather than full user ID lists.

---

### M-12: Synchronous boto3 calls in album/social converters block the event loop

**Files:** `backend/app/converters/album_converter.py`, `backend/app/converters/social_converter.py`

These converters call synchronous `generate_presigned_url()` and `resolve_avatar_url()` from async endpoint handlers. Each call blocks the event loop.

**Impact:** Album listings with many photos or large friend/follower lists cause latency spikes under load.

**Fix:** Convert to async versions using `async_resolve_avatar_url` and an async presigned URL generator.

---

### M-13: PostgreSQL has no `statement_timeout` or `idle_in_transaction_session_timeout`

**File:** `docker-compose.yml:98-107`, `docker-compose.prod.yml:114-127`

A runaway query or leaked connection can hold locks indefinitely, consuming all 50 connection slots.

**Fix:** Add `-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000` to postgres command.

---

### M-14: PostgreSQL connection has no SSL/TLS

**File:** `backend/app/core/database.py:7-16`

The asyncpg pool is created without SSL parameters. In production, credentials and query data travel in plaintext over the Docker bridge network.

**Fix:** Add `ssl='require'` to `asyncpg.create_pool()` for production, or document the accepted risk for same-host Docker deployment.

---

### M-15: Redis connection has no TLS

**File:** `docker-compose.yml:127-132`

Redis uses `redis://` (plaintext). Password and cached data (sessions, rate limits) are visible to network sniffers on the Docker bridge.

**Fix:** Configure Redis TLS (`rediss://`) for production, or document the accepted risk.

---

### M-16: `contentSegments` uses sanitize-parse-serialize-resanitize pattern (mXSS risk)

**File:** `frontend/src/composables/usePostDetail.ts:182-231`

Post content goes through: `DOMPurify.sanitize()` -> DOM parse -> `innerHTML` serialization -> split -> `DOMPurify.sanitize(part)` per segment. This parse-serialize cycle is a known mXSS vector in certain browser/DOMPurify versions. The second sanitization pass mitigates the risk.

**Impact:** Defense-in-depth concern; the double sanitization is a good mitigation.

**Fix:** Use `DOMPurify.sanitize(part, { RETURN_DOM_FRAGMENT: true })` to avoid the serialize-reparse cycle.

---

### M-17: `PostCard` thumbnail extracted from raw unsanitized content

**File:** `frontend/src/components/PostCard.vue:144-147`

The regex extracts the first `<img src>` from `props.post.content` (raw, not sanitized) for the thumbnail URL. The regex restricts to `http://` or `https://` protocol, preventing `javascript:` injection.

**Impact:** Could display an image from an attacker-controlled domain (tracking pixel). Backend nh3 sanitizer should strip these, but this is a defense-in-depth gap.

**Fix:** Extract thumbnail from the already-sanitized content.

---

### M-18: HSTS header served in non-TLS nginx configuration

**File:** `nginx/snippets/security-headers.conf:18`

`Strict-Transport-Security` is included in the shared security-headers snippet, which is also applied to HTTP server blocks. If served over HTTP without TLS, browsers could lock users out.

**Fix:** Move HSTS to the HTTPS-only server block context.

---

## LOW Severity

### L-01: DM char cap reduced from 50K to 20K without migration strategy

**File:** `backend/app/core/constants.py:148` — `DM_CHAR_CAP_PER_CONVERSATION = 20_000`

Existing conversations written under the 50K limit may have messages aggressively deleted when new messages are sent.

### L-02: `CitationSearchDialog` loading indicator stuck when input cleared quickly

**File:** `frontend/src/components/post/CitationSearchDialog.vue:43`

When the user types then quickly clears the input, `clearTimeout` cancels the debounce but `loading.value` remains `true`. Same issue in `CoAuthorManager.vue:75`.

**Fix:** Add `loading.value = false` in the early-return path for empty input.

### L-03: `formatRelativeTime` uses `toLocaleDateString()` without locale

**File:** `frontend/src/composables/usePostDetail.ts:521`

Falls back to browser-default locale rather than the user's chosen app language for dates older than 7 days.

### L-04: Router guard toast messages are hardcoded English

**File:** `frontend/src/router/index.ts:331,337,343`

Permission-denied toast messages are not using `t()` i18n function.

### L-05: `CoAuthorManager` search results not filtered against existing co-authors

**File:** `frontend/src/components/post/CoAuthorManager.vue:80-97`

Already-invited users appear in search results. Clicking them produces a 409 error from the backend.

### L-06: `BulkDeleteNotificationsRequest.notification_ids` accepts strings, not UUIDs

**File:** `backend/app/schemas/notification.py:28`

`list[str]` instead of `list[uuid.UUID]` means invalid UUIDs cause a 500 (unhandled ValueError) instead of a clean 422 validation error.

### L-07: `CreateAccountRequest.captcha_code` has no `max_length`

**File:** `backend/app/schemas/user.py:79`

Other captcha fields have `max_length=10`, but this one doesn't. Allows arbitrarily long captcha strings (mitigated by 10MB body limit).

### L-08: No DM recipient existence validation

**File:** `backend/app/services/dm.py:95-158`

`send_message()` never validates that the recipient UUID corresponds to an actual, non-deleted user. Could create conversation rows with non-existent participants.

### L-09: Daily post limit key may persist indefinitely on Redis EXPIRE failure

**File:** `backend/app/services/post.py:19-30`

The `EXPIRE` is only set when `count == 1`. If the EXPIRE call fails, the key persists indefinitely. Also, a fixed 86400s TTL doesn't align with day boundaries.

### L-10: CSV formula injection mitigation incomplete

**File:** `backend/app/tasks/form_export.py:21-28`

`_sanitize_csv_value` only checks the first character for `=`, `+`, `-`, `@`, `\t`, `\r`. Missing check for `|` pipe character.

### L-11: `invite_code` expiry uses `time.time()` instead of timezone-aware comparison

**File:** `backend/app/services/invite_code.py:20`

If `expires_at` is timezone-naive, `.timestamp()` interprets it as local time, which could be incorrect on non-UTC servers.

### L-12: Citation API defaults to `pageSize=100`

**File:** `frontend/src/api/citations.ts:7,18`

Both `getCitedBy` and `getCiting` default to `pageSize=100` (backend max). Wasteful for posts with few citations.

### L-13: `sync_post_citations` double query for post existence

**File:** `backend/app/services/citation.py:92-103`

For each citation, separate queries check post existence and fetch the author. Could be combined into a single `SELECT user_id FROM posts WHERE id = $1 AND is_deleted = false`.

### L-14: `backup-db.sh` does not set restrictive `umask`

**File:** `scripts/backup-db.sh`

Unlike `backup.sh` which sets `umask 077`, database dumps may be world-readable on shared servers.

### L-15: No Docker network segmentation between application tiers

**File:** `docker-compose.yml:258`

All services share a single `ai3l-network` bridge. A compromised nginx container can directly reach PostgreSQL and Redis.

### L-16: No `log_min_duration_statement` for PostgreSQL slow query logging

**File:** `docker-compose.prod.yml:114-127`

Performance problems go undetected without slow query logging.

### L-17: DM file size limit inconsistency

**File:** `frontend/src/components/dm/MessageInput.vue:17`

Frontend limits to 10MB while backend may allow 50MB. Users may be unable to upload files the backend would accept.

### L-18: `dm_friends_only` exposed in `PublicUserResponse`

**File:** `backend/app/schemas/user.py:53`

Any user can see another user's DM privacy preference by viewing their profile.

### L-19: `max_respondents` can be lowered below current response count

**File:** `backend/app/schemas/form.py:89`

A form creator can set `max_respondents=1` when 50 responses already exist. Existing data is preserved but the form becomes inactive.

---

## Not Confirmed (Agent False Positives)

| Claim | Verification | Result |
|-------|-------------|--------|
| `.env` secrets committed to git | `git ls-files .env` and `git log -- .env` both empty | **False positive** — `.env` is not tracked |
| Comment self-reply check dead code | `uuid4()` collision impossible | Non-issue (harmless defense-in-depth) |
| `find_many` fallback count query broken | Uses self-contained `NOT EXISTS` subquery | **Not broken** (only `search` is broken) |
| DM text cleanup reprocesses messages | Messages are `DELETE`d, not just NULLed | Working correctly |
| `recommend_friends` empty table window | PostgreSQL MVCC prevents visibility | Working correctly |

---

## Positive Observations

The codebase demonstrates strong security practices in many areas:

- **SQL injection**: All queries use parameterized statements; sort/filter values validated via allowlist maps
- **XSS**: All `v-html` usages pass through DOMPurify; backend uses nh3 HTML sanitizer
- **Authentication**: HttpOnly cookies + CSRF double-submit bound to session JTI; Argon2id hashing; captcha on login/register
- **Authorization**: Consistent `require_role()` dependencies; ownership checks in service layer
- **WebSocket**: One-time ticket auth with atomic get-and-delete; per-user connection limits; message rate limiting
- **File uploads**: Magic byte validation + extension allowlist; storage quota enforcement; PDF sanitization via pikepdf
- **Rate limiting**: Atomic Lua script-based rate limiting on all sensitive endpoints
- **State management**: Timer cleanup comprehensive across all components; state cleared on logout; fetchId guards against stale responses
- **Router guards**: All protected routes covered; open redirect properly prevented
- **DM system**: Block checks within transaction; advisory locks for char cap; HTML sanitization; file validation

---

## Priority Action Items

1. **H-01**: Fix `post_repo.search` fallback count query (functional crash bug)
2. **H-02**: Add file cleanup to `bulk_soft_delete`
3. **H-03**: Fix `anonymize_user` partial failure reporting
4. **M-01**: Update `preferred_language` pattern for all 17 locales
5. **M-02**: Make `post_process_citations` idempotent
6. **M-04**: Fix `get_client_ip()` to prefer `X-Real-IP` for Cloudflare compatibility
7. **M-11**: Transform reactions to return counts instead of user ID lists
8. **M-12**: Convert album/social converters to async presigned URL generation
