# Deep Systemic/Functional Bug Audit — 2026-03-25

**Scope:** ~540 source files across backend (181 .py), frontend (365 .ts/.vue), infrastructure, and tests
**Method:** 7 parallel deep-dive agents examining all layers
**Result: 54 unique bugs** (3 HIGH, 25 MEDIUM, 26 LOW) after deduplication

---

## HIGH Severity (3)

### H-01: Event bus redacted kwargs make retried events produce garbage data

- **File:** `backend/app/core/event_bus.py:87,100-110`
- **Impact:** Data corruption in retried event handlers
- **Description:** When an event handler permanently fails, `_persist_failed_event()` redacts values for keys like `content`, `message`, `body` with `"[REDACTED]"` before storing to Redis. When `retry_failed_events` (in `event_retry.py`) later replays these entries, handlers receive the literal string `"[REDACTED]"` as the actual value. For example, a notification handler that failed due to a transient Redis error would be retried with `message="[REDACTED]"`, and the user would see a notification saying "[REDACTED]" instead of the real message. This affects any event handler that uses `content`, `message`, or `body` kwargs.
- **Fix:** Either (a) skip redaction for retryable failures, (b) store the unredacted payload in a separate short-lived Redis key and reference it from the failure entry, or (c) redact only for permanent logging and keep the raw payload for retry.

---

### H-02: Bulk role change force-logouts ALL requested users, not just changed ones

- **File:** `backend/app/api/v1/endpoints/users.py:325-327`
- **Impact:** Unnecessary session revocation and WebSocket disruption for unchanged users
- **Description:** After `bulk_change_role_svc()` returns the count of actually-updated users, the code iterates over ALL `req.user_ids` to emit `user.role_changed` events and call `revoke_user_sessions()`. Users who already had the target role get unnecessarily force-logged-out. A SUPER_ADMIN bulk-changing 50 users to MEMBER where 45 already are MEMBER causes 45 unnecessary force-logouts, each logging a `ROLE_CHANGED` WebSocket event, triggering client-side re-authentication flows, and disrupting active sessions.
- **Fix:** `bulk_change_role_svc()` should return the list of actually-changed user IDs. Only emit events and revoke sessions for those IDs.

---

### H-03: Duplicate `deploy` key in docker-compose.prod.yml silently loses `replicas: 1`

- **File:** `docker-compose.prod.yml:259-272`
- **Impact:** Multiple Celery Beat instances can dispatch duplicate periodic tasks
- **Description:** The `celery-beat` service has two `deploy:` blocks at the same YAML level:
  ```yaml
  deploy:           # line 259
    replicas: 1
  # ...
  deploy:           # line 268
    resources:
      limits:
        cpus: "0.25"
        memory: 128M
  ```
  In YAML, duplicate keys at the same level are resolved by last-key-wins. The first block (`replicas: 1`) is silently overwritten by the second (`resources.limits`). Without the replica constraint, if the deployment is scaled (`docker compose up --scale celery-beat=2`), multiple Beat instances would each dispatch the full schedule, causing every periodic task (cleanup, recommendations, etc.) to run N times concurrently.
- **Fix:** Merge both `deploy` blocks into one:
  ```yaml
  deploy:
    replicas: 1
    resources:
      limits:
        cpus: "0.25"
        memory: 128M
  ```

---

## MEDIUM Severity (25)

### Backend — Data Logic

#### M-01: `_normalize_percentages` corrupts `multiple_choice` statistics

- **File:** `backend/app/services/form.py:291-304`
- **Impact:** Incorrect statistics displayed for multi-select form questions
- **Description:** The `_normalize_percentages` function forces option percentages to sum to exactly 100.0%. This is applied uniformly to `single_choice`, `multiple_choice`, and `dropdown` question types (line 291). For `multiple_choice` questions where respondents can select multiple options, the natural sum can legitimately exceed 100% (e.g., if 10 respondents each select both Option A and Option B, each option is 100%, totaling 200%). Forcing normalization to 100% adjusts both to 50%, which is demonstrably wrong.
- **Fix:** Exclude `multiple_choice` from the normalization logic. Only normalize `single_choice` and `dropdown`.

---

#### M-02: `dm_repo.send_message_atomic` — `None` recipient silently bypasses block check

- **File:** `backend/app/repositories/dm_repo.py:479-497`
- **Impact:** Security bypass — blocked users can send DMs
- **Description:** The `recipient_id` is fetched via `fetchval` at line 479. If the conversation row has been deleted between the `find_or_create_conversation` call (in the service) and this atomic function, `recipient_id` will be `None`. The subsequent block check passes `None` as `$2` to the `blocks` query. In PostgreSQL, `NULL = anything` evaluates to `NULL` (not `TRUE`), so the `EXISTS` check returns `FALSE`, and the block check is silently bypassed.
- **Fix:** Add `if recipient_id is None: raise AppError(...)` immediately after the `fetchval` call.

---

#### M-03: `album.remove_member` has TOCTOU race — no transaction

- **File:** `backend/app/services/album.py:523-553`
- **Impact:** Race condition in album permission enforcement
- **Description:** The `remove_member` function reads the album and checks permissions at lines 538-549 but does NOT wrap these checks in a transaction with the `delete_member` call at line 551. Between the permission check and the actual delete, the caller's album role could be changed (e.g., demoted from ADMIN to MEMBER). Every other permission-sensitive album operation (`approve_member`, `delete_album`, `set_cover_from_photo`) properly wraps check+action in a transaction.
- **Fix:** Wrap the permission check and delete in `async with conn.transaction():`.

---

#### M-04: `_cleanup_post_files` — storage counter not refunded if decrement fails

- **File:** `backend/app/services/post.py:277-317`
- **Impact:** User's `storage_used_bytes` permanently inflated after partial cleanup failure
- **Description:** File operations and DB updates are not atomic. If `delete_file` succeeds for all files but `decrement_storage_used` fails (line 315), no retry or compensation is attempted. The user's storage counter stays permanently over-counted, reducing their usable quota.
- **Fix:** Wrap the storage decrement in a try/except with retry logic, or log a compensation entry that can be reconciled later.

---

#### M-05: `album.upload_cover` deletes MinIO file inside DB transaction

- **File:** `backend/app/services/album.py:348-351`
- **Impact:** Orphaned DB reference if transaction rolls back after irreversible MinIO delete
- **Description:** Inside a DB transaction (lines 325-366), the code calls `delete_file(old_cover_key)` at line 349, which is a MinIO (S3) operation. If the transaction later fails and rolls back, the old cover file has already been permanently deleted from MinIO, but the DB changes are rolled back. The album still references the now-deleted cover file.
- **Fix:** Move the MinIO deletion to after the transaction commits, storing the old key for deferred cleanup.

---

#### M-06: `sync_post_citations` N+1 queries inside transaction

- **File:** `backend/app/services/citation.py:90-104`
- **Impact:** Extended transaction hold under concurrent post edits
- **Description:** Inside a transaction (line 70), for each cited post ID in `to_add`, the code performs an individual `SELECT user_id FROM posts WHERE id = $1` (line 92) and an individual `INSERT INTO post_citations` (line 102). With N citations, this is N×2 queries in a single transaction. A post with 50 new citations would execute 100+ queries while holding the connection.
- **Fix:** Batch the SELECT and INSERT operations (e.g., `SELECT user_id FROM posts WHERE id = ANY($1::uuid[])`).

---

### Backend — Endpoints

#### M-07: Synchronous boto3 calls block asyncio event loop

- **Files:**
  - `backend/app/api/v1/endpoints/export.py:196,259`
  - `backend/app/api/v1/endpoints/about.py:357,362`
- **Impact:** Event loop starvation under concurrent load
- **Description:** `get_export_history` calls `client.head_object()` synchronously per history entry (up to 20). `delete_export` calls `client.delete_object()` synchronously. `about.py` uses sync `upload_file()` and `delete_file()`. All other file operations in the codebase use async storage wrappers, making these inconsistencies easy to miss. Export history with 20 entries = 20 sequential blocking S3 round-trips (50-200ms each).
- **Fix:** Use `asyncio.get_event_loop().run_in_executor()` or the existing `async_upload_file` / `async_delete_file` wrappers.

---

#### M-08: Admin invite code revoke/delete TOCTOU

- **File:** `backend/app/api/v1/endpoints/admin.py:53-61,95-102`
- **Impact:** ADMIN can delete another admin's invite code via race condition
- **Description:** For ADMIN users (not SUPER_ADMIN), the ownership check does `find_by_id()` then separately `revoke()` or `delete()`. The `if code_info and ...` guard silently passes when `code_info is None`. The delete path uses `DELETE FROM invite_codes WHERE id = $1` with no ownership filter. If `find_by_id` returns None transiently, an ADMIN can delete another user's invite code.
- **Fix:** Add `AND created_by = $2` to the DELETE query, or wrap check+delete in a transaction with `SELECT FOR UPDATE`.

---

#### M-09: Comment reaction endpoint ignores `post_id` URL parameter

- **File:** `backend/app/api/v1/endpoints/comments.py:124-156`
- **Impact:** Broken REST resource hierarchy; allows URL manipulation
- **Description:** `post_id` from the URL path `/posts/{post_id}/comments/{comment_id}/reactions` is accepted as a parameter but never used or validated. A user can react to comment BBB by calling `/posts/WRONG_UUID/comments/BBB/reactions` and it succeeds. Breaks the REST resource hierarchy contract.
- **Fix:** Validate that the comment's `post_id` matches the URL's `post_id` before proceeding.

---

#### M-10: GUEST access to SIG forms endpoints

- **File:** `backend/app/api/v1/endpoints/forms.py:91,215`
- **Impact:** Information disclosure — GUESTs can view and submit SIG forms
- **Description:** `get_sig_forms` and `get_form` use `Depends(get_current_user)` which permits GUESTs. Meanwhile `get_sig_posts` in `sigs.py` uses `require_role("MEMBER", "ADMIN", "SUPER_ADMIN")`. A GUEST who knows a `sig_id` can browse all forms in that SIG, read the full form structure, and submit responses. The `allow_non_members` check only guards against non-SIG-members, not against GUESTs.
- **Fix:** Change to `require_role("MEMBER", "ADMIN", "SUPER_ADMIN")` for consistency with posts.

---

#### M-11: Export history loads ALL entries without pagination

- **File:** `backend/app/api/v1/endpoints/export.py:180`
- **Impact:** Performance degradation with long history
- **Description:** `zrevrange("export:site:history", 0, -1)` fetches every entry, and for each successful one, makes a synchronous `head_object` call. No pagination parameters are available. Combined with sync S3 calls (M-07), this blocks the event loop for seconds with a long history.
- **Fix:** Add `limit`/`offset` query parameters, or enforce `EXPORT_HISTORY_MAX` more aggressively.

---

#### M-12: Export delete does O(n) linear scan of all history entries

- **File:** `backend/app/api/v1/endpoints/export.py:235-247`
- **Impact:** Deletion becomes slower as history grows
- **Description:** To find the entry matching `task_id`, the code fetches ALL entries from the sorted set and iterates through them, JSON-parsing each one. There is no index or secondary lookup.
- **Fix:** Use a Redis hash keyed by `task_id` alongside the sorted set for O(1) lookup.

---

### Backend — Tasks & Core

#### M-13: `cleanup_dm_orphan_files` task has no Celery Beat schedule

- **File:** `backend/app/celery_app.py`
- **Impact:** Orphaned DM files in MinIO accumulate indefinitely
- **Description:** The task `cleanup_dm_orphan_files` is defined in `tasks/dm_cleanup.py` with task name `"cleanup_dm_orphan_files"`, but has no corresponding entry in `celery.conf.beat_schedule`. The task is registered and discoverable but will never be triggered automatically. The `cleanup_dm_expired_files` task only handles files past their expiry date, not genuinely orphaned files (no referencing DB row).
- **Fix:** Add a Beat schedule entry (e.g., daily) for `cleanup_dm_orphan_files`.

---

#### M-14: `SoftTimeLimitExceeded` not handled in export task — lock and temp file leak

- **File:** `backend/app/tasks/site_export.py:590-603`
- **Impact:** Lock held and temp file leaks for up to 1 hour after soft timeout
- **Description:** The export task has `soft_time_limit=3600` and `time_limit=7200`. When the soft time limit fires, Celery raises `SoftTimeLimitExceeded` in the worker's main thread, interrupting `future.result()`. However, the actual coroutine `_async_export()` continues running on the background event loop thread. The `finally` block (lines 573-585) that releases the Redis lock and cleans up the temp file will NOT execute until the coroutine naturally completes or the hard time limit kills the process.
- **Fix:** Catch `SoftTimeLimitExceeded` in the sync wrapper and signal the async coroutine to cancel (e.g., via an `asyncio.Event`), then explicitly clean up.

---

#### M-15: Thumbnail task has `max_retries=2` but never calls `self.retry()`

- **File:** `backend/app/tasks/thumbnail.py:44,114-116`
- **Impact:** Transient failures permanently fail thumbnail generation
- **Description:** `generate_thumbnail_task` is configured with `bind=True, max_retries=2` but the exception handler simply re-raises without calling `self.retry(exc=exc)`. In Celery, `max_retries` only caps `self.retry()` calls; it does NOT enable automatic retry. Photos uploaded during transient failures (MinIO timeout, DB unavailability) permanently lack thumbnails with no mechanism to regenerate.
- **Fix:** Replace `raise` with `self.retry(exc=exc, countdown=30)` in the exception handler.

---

### Frontend — Views

#### M-16: QACreateView draft key is static, not reactive

- **File:** `frontend/src/views/qa/QACreateView.vue:41`
- **Impact:** Draft key resolves to `anon` on page refresh; different users share drafts
- **Description:** The draft key is a static template string `` `ai3l_question_draft_${auth.user?.id ?? 'anon'}` `` evaluated at setup time. If the user navigates directly to `/qa/ask` (page refresh), `auth.user` may not yet be populated, so the key resolves to `ai3l_question_draft_anon` even for logged-in users. Compare with `PostCreateView.vue` which correctly uses a computed getter `key: () => draftKey.value` that re-evaluates reactively.
- **Fix:** Use a computed ref for the draft key, matching the `PostCreateView` pattern.

---

#### M-17: UserProfileView `coAuthoredPosts` not reset on route param change

- **File:** `frontend/src/views/UserProfileView.vue:133-137`
- **Impact:** Stale co-authored posts shown when navigating between user profiles
- **Description:** The `watch(userId, ...)` resets `page` and re-fetches `user` and `posts`, but does not reset `coAuthoredPosts`, `coAuthoredLoading`, or `activeSection`. When navigating from one user profile to another while the "Co-Authored" tab is active, the old user's co-authored posts remain visible. The `switchSection` function only fetches if `coAuthoredPosts.value.length === 0`, but after navigation it's still populated with previous user's data.
- **Fix:** Reset `coAuthoredPosts.value = []` and `activeSection.value = 'authored'` in the `watch(userId, ...)` callback.

---

#### M-18: SigPostsView does not re-fetch when `sigId` changes

- **File:** `frontend/src/views/sigs/SigPostsView.vue:61`
- **Impact:** Stale posts displayed when navigating between SIGs
- **Description:** `SigPostsView` only fetches posts via `onMounted(fetchPosts)`. There is no `watch` on `sigId` to re-fetch when the route parameter changes. Vue Router reuses component instances for the same route component, so navigating from `/sigs/A` to `/sigs/B` doesn't re-fire `onMounted`. The parent `SigLayout` re-fetches the SIG data, but child posts stay stale. The sibling `SigFormsView` correctly has `watch(sigId, ...)` for this reason.
- **Fix:** Add `watch(sigId, () => { resetPage(); fetchPosts() })`.

---

#### M-19: ApplicationsView and ReportsView — no double-submit protection

- **Files:**
  - `frontend/src/views/admin/ApplicationsView.vue:46-57`
  - `frontend/src/views/admin/ReportsView.vue:41-48`
- **Impact:** Duplicate API requests on rapid double-click
- **Description:** Neither the `review` function (ApplicationsView) nor the `reviewReport` function (ReportsView) sets any loading state before the API call. The approve/reject/resolve/dismiss buttons have no `:disabled` or `:loading` binding. Multiple rapid clicks send duplicate API requests.
- **Fix:** Add a `processing` ref, set it before the API call, bind `:disabled="processing"` to buttons, and clear it in `finally`.

---

### Frontend — Stores/Composables

#### M-20: `useFormResponseViewer` computes statistics from only the current page

- **File:** `frontend/src/composables/useFormResponseViewer.ts:118-124`
- **Impact:** Misleading aggregated statistics for forms with 200+ responses
- **Description:** When `fetchResponses` is called, line 118 replaces `responses.value` with only the current page's data. Then line 123 computes `formStats` from just those responses. When there are more than `pageSize` (200) responses and the user navigates to page 2, the stats are recalculated from only page 2's data, giving completely wrong aggregated statistics (averages, distributions, counts).
- **Fix:** Either (a) fetch stats from a dedicated backend endpoint (`GET /forms/{id}/stats`), or (b) accumulate all pages' responses before computing stats.

---

#### M-21: `useFormResponseViewer` has no stale-response guard

- **File:** `frontend/src/composables/useFormResponseViewer.ts:104-130`
- **Impact:** Stale data can overwrite current data on rapid page changes
- **Description:** The `fetchResponses` function has no `fetchId` counter or stale-response guard. Other composables (`useFetchPaginated`, `usePostList`, DM store) all use a `fetchId` pattern to discard responses from superseded requests. Rapidly changing pages or switching between forms can cause a slow response from a previous request to overwrite correct data.
- **Fix:** Add a `fetchId` counter; discard responses where `fetchId` doesn't match current.

---

#### M-22: DataExportView download URL not validated before opening

- **File:** `frontend/src/views/admin/DataExportView.vue:143-144`
- **Impact:** Defense-in-depth gap — could open malicious URLs
- **Description:** The `handleDownload` function calls `window.open(url, '_blank')` with the raw URL from the API response, without validating the URL origin. The `useFormExport` composable has an `isAllowedDownloadUrl()` function that validates URLs belong to the same origin or the configured MinIO origin before opening them. This pattern was not applied to the site export feature.
- **Fix:** Import and use `isAllowedDownloadUrl()` or equivalent validation before `window.open()`.

---

### Infrastructure

#### M-23: Nginx write-heavy regex location missing proxy timeout directives

- **File:** `nginx/conf.d/default.conf:79-85`
- **Impact:** Long POST/PUT/DELETE operations get 504 Gateway Timeout at 60s
- **Description:** The write-heavy location block (`~ ^/api/v1/(posts|comments|forms|albums|social|qa|recommendations|dm)`) is missing `proxy_connect_timeout`, `proxy_send_timeout`, `proxy_read_timeout`, and `client_body_timeout` directives. Because nginx regex locations take priority over prefix locations, these requests bypass the general `/api/` block (which has 300s timeouts) and use nginx defaults (60s). The same issue exists in the HTTPS block at line 194.
- **Fix:** Add timeout directives matching the general API block:
  ```nginx
  proxy_connect_timeout 90s;
  proxy_send_timeout 300s;
  proxy_read_timeout 300s;
  client_body_timeout 300s;
  ```

---

#### M-24: Dev docker-compose mounts production nginx config

- **File:** `docker-compose.yml:22-26`
- **Impact:** Vite HMR not available in development; dev nginx features unused
- **Description:** The development `docker-compose.yml` mounts `./nginx/conf.d:/etc/nginx/conf.d` (production config) instead of `./nginx/conf.d.dev`. The dev config (`conf.d.dev/default.conf`) with its `resolver 127.0.0.11 valid=5s`, dynamic DNS `set $var` pattern, and Vite HMR proxy (`set $vite http://frontend:3210`) is never used. Frontend changes require a full rebuild to be visible.
- **Fix:** Mount `./nginx/conf.d.dev:/etc/nginx/conf.d` in the development compose file.

---

### Schema/Validation

#### M-25: `SiteExportRequest` allows both options to be `false`

- **File:** `backend/app/schemas/export.py:6-8`
- **Impact:** No-op export acquires lock, uses rate limit, creates history entry
- **Description:** There is no `model_validator` to reject requests where both `include_database` and `include_files` are `false`. The frontend guards against this (`canStart` computed), but the backend does not. A direct API call with `{"include_database": false, "include_files": false}` would create an empty ZIP, acquire the distributed lock for up to 3 hours, and consume the rate limit slot (1 per 30 minutes).
- **Fix:** Add a `model_validator`:
  ```python
  @model_validator(mode="after")
  def at_least_one_option(self) -> "SiteExportRequest":
      if not self.include_database and not self.include_files:
          raise ValueError("At least one export option must be selected.")
      return self
  ```

---

## LOW Severity (26)

### L-01: `invite_code.py` unconditional `.replace(tzinfo=UTC)` on already-aware datetime

- **File:** `backend/app/services/invite_code.py:20`
- **Description:** The code does `row["expires_at"].replace(tzinfo=timezone.utc)` without checking if `tzinfo` is already set. asyncpg returns timezone-aware datetimes for TIMESTAMPTZ columns. `.replace()` replaces (not converts) the timezone. Currently harmless since asyncpg returns UTC, but brittle if behavior changes. The correct pattern (used in `dm.py:473-474`) is `if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=timezone.utc)`.

---

### L-02: `remove_co_author` and `leave_co_authorship` missing transaction wrapping

- **File:** `backend/app/services/co_author.py:282-328`
- **Description:** Both functions verify permissions/ownership and then call the mutation in two separate queries without an explicit transaction. Other co-author operations (`invite_co_author`, `respond_to_invitation`) consistently use transactions. TOCTOU window exists but is unlikely in practice.

---

### L-03: Vote removal on deleted comment returns 0, masking the issue

- **File:** `backend/app/repositories/vote_repo.py:11-29`
- **Description:** When `vote=0` (remove vote), the CTE deletes the vote row, but the outer `UPDATE comments SET vote_score = ...` runs on a potentially non-existent comment. Returns `0` instead of raising an error, masking that the comment doesn't exist. The caller would have already checked this, so impact is minimal.

---

### L-04: `soft_delete_with_permission` loads ALL form responses without pagination

- **File:** `backend/app/repositories/form_repo.py:576-593`
- **Description:** When a form with `file_upload` questions is soft-deleted, `SELECT user_id, answers FROM form_responses WHERE form_id = $1` is executed without LIMIT. For popular forms with thousands of responses, this loads all response data (including large JSONB `answers`) into memory at once, inside a transaction. The `answers` column could be large per row.

---

### L-05: `about.py` override endpoint double-parses request body

- **File:** `backend/app/api/v1/endpoints/about.py:215`
- **Description:** The endpoint uses both `body: OrgChartOverrideUpdateRequest` (Pydantic parsing) and `raw_body = await request.json()` (manual parsing) to determine provided fields. Should use `body.model_fields_set` like `forms.py:280` and `users.py:83` do.

---

### L-06: Missing rate limiting on `unfriend` and `unfollow` endpoints

- **File:** `backend/app/api/v1/endpoints/social.py:136-193`
- **Description:** `unfriend_endpoint` and `unfollow_user_endpoint` have no rate limiting, unlike `follow_user_endpoint`, `block_user_endpoint`, `accept_friend_request_endpoint`, and `reject_friend_request_endpoint` which all apply rate limits. A malicious script could rapidly unfriend/unfollow all connections.

---

### L-07: GUEST can read comments but cannot list posts

- **File:** `backend/app/api/v1/endpoints/comments.py:31-52`
- **Description:** `get_comments` uses `get_current_user` (allows GUEST), but `get_posts_list` in `posts.py` uses `require_role("MEMBER", ...)`. A GUEST who knows a `post_id` can read all comments on it, even though they cannot access the post listing. Information disclosure through inconsistent permission levels.

---

### L-08: `DATABASE_SSL` env var parsed inconsistently

- **File:** `backend/app/core/database.py:14`
- **Description:** `database.py` reads `DATABASE_SSL` directly from `os.environ.get()` and only matches the exact string `"true"` (case-insensitive). `config.py` defines `DATABASE_SSL: bool = False` which Pydantic would parse `"1"`, `"yes"`, `"on"`, etc. as truthy. `database.py` does not use `settings.DATABASE_SSL`. Setting `DATABASE_SSL=1` would cause `settings.DATABASE_SSL` to be `True` but the actual connection to use no SSL.

---

### L-09: `form_export` task has `max_retries=2` but never calls `self.retry()`

- **File:** `backend/app/tasks/form_export.py:155-159`
- **Description:** Same pattern as M-15. `export_form_csv` has `bind=True, max_retries=2, default_retry_delay=60` but never calls `self.retry()`. Transient failures permanently fail the export. Lower severity than thumbnails since users can manually re-trigger.

---

### L-10: Sync boto3 in async function blocks event loop in export task

- **File:** `backend/app/tasks/site_export.py:289-316`
- **Description:** Inside `_export_files_to_zip()`, synchronous boto3 calls (`paginator.paginate()`, `client.get_object()`, `body.read()`) are made directly within an async function. Progress updates (`_set_progress()`) can only execute between S3 reads. For large files, progress stalls until download completes. Lower severity because the export holds a distributed lock (no concurrent operations on same loop).

---

### L-11: DB connection held for entire table export duration

- **File:** `backend/app/tasks/site_export.py:201-244`
- **Description:** For each table, a connection is acquired and held for the entire duration of streaming all rows via server-side cursor. For large tables (`audit_logs`, `dm_messages`), this could be minutes. Pool max_size=20; at most 1 connection held at a time (sequential), but the transaction prevents reuse.

---

### L-12: Redis failure in progress reporting aborts entire export

- **File:** `backend/app/tasks/site_export.py:75-90`
- **Description:** `_set_progress()` and `_set_progress_field()` call `get_redis()` without error handling. If Redis becomes unavailable during a long export (hours), these raise exceptions that propagate up and abort the entire export. Progress reporting is non-critical; it should not abort the actual data export work.

---

### L-13: S3 response body not closed on exception during file export

- **File:** `backend/app/tasks/site_export.py:302-323`
- **Description:** When `client.get_object()` succeeds but a subsequent operation (`dest.write(chunk)`) throws, the `body` (`StreamingBody`) is never closed. The `except` block catches the error but doesn't call `body.close()`. The underlying HTTP connection may not be released until GC. If many files fail, the connection pool could be exhausted.

---

### L-14: Raw exception stored in Redis progress hash (write-side unsanitized)

- **File:** `backend/app/tasks/site_export.py:551`
- **Description:** On failure, `str(exc)[:500]` is stored in the Redis progress hash. The progress endpoint sanitizes on read (line 150-152), but only against `_INTERNAL_PATTERNS` regex. If any other code path reads the progress hash directly, it sees unsanitized errors. Defense-in-depth: sanitize at write side.

---

### L-15: Error sanitization regex misses MinIO/S3 URLs

- **File:** `backend/app/api/v1/endpoints/export.py:23-27`
- **Description:** `_INTERNAL_PATTERNS` catches `postgresql://` and `redis://` but not `minio://`, `http://minio:9000`, or `s3://` URLs. An error like `"Cannot connect to minio:9000"` would pass unsanitized, potentially revealing internal MinIO hostname and port.

---

### L-16: AlbumCommentsView double fetch on mount

- **File:** `frontend/src/views/albums/AlbumCommentsView.vue:133-141`
- **Description:** `onMounted(fetchComments)` and the watch on `album.value?.id` both fire on mount. If `album.value` is already populated, both trigger `fetchComments` simultaneously, creating duplicate API calls.

---

### L-17: AlbumPhotosView double fetch via immediate watch + page watch

- **File:** `frontend/src/views/albums/AlbumPhotosView.vue:149-157`
- **Description:** The watch on `album.value?.id` with `{ immediate: true }` calls `resetPage()` then `fetchPhotos()`. `resetPage()` changes `page` to 1, which triggers `watch(page, fetchPhotos)`, causing a second `fetchPhotos()` call on initial load.

---

### L-18: DMView `recallTargetId` not reset on conversation switch

- **File:** `frontend/src/views/DMView.vue:110-116`
- **Description:** `selectConversation` resets `editingMessageId` and `editingContent` but not `recallTargetId`. If the recall confirmation modal is open, switching conversations leaves it referencing a message from the previous conversation. Confirming recall would target the wrong conversation's message.

---

### L-19: `v-html` used on plain-text `affiliation` field

- **File:** `frontend/src/views/about/MembersView.vue:151`
- **Description:** `member.affiliation` is rendered with `v-html="sanitizeHtml(member.affiliation)"`. Affiliation is a plain text field (institution name), not HTML. HTML special characters (e.g., `"R&D <Lab>"`) render as markup instead of literal text. Not an XSS issue (sanitizeHtml protects), but causes incorrect display.

---

### L-20: FormsDirectoryView has no fetchId guard

- **File:** `frontend/src/views/forms/FormsDirectoryView.vue:44-56`
- **Description:** `fetchForms()` has no `fetchId` counter against stale responses. Debounced search and `watch(page, fetchForms)` can race. Unlike `NotificationsView` and other views, this view has no race condition protection.

---

### L-21: SigMembersView date formatting without locale

- **File:** `frontend/src/views/sigs/SigMembersView.vue:232,286`
- **Description:** Uses `new Date(m.created_at).toLocaleDateString()` without passing the i18n locale, falling back to browser locale. Inconsistent with the app's selected language when browser locale differs.

---

### L-22: `FormResponse` type mismatch — `display_name` required but missing from backend

- **Files:** `frontend/src/api/forms.ts:82`, `frontend/src/types/form.ts:49-57`
- **Impact:** TypeScript believes `display_name` is always present; at runtime it's `undefined` for `getMyResponse`
- **Description:** The `getMyResponse` API function returns `FormResponse | null`, where `FormResponse` has `display_name: string` as required. The backend's `FormUserResponseSchema` does NOT include `display_name`. Any code accessing `previousResponse.value.display_name` gets `undefined`.

---

### L-23: `syncQueryParams` runs after failed fetch

- **File:** `frontend/src/composables/usePostList.ts:172`
- **Description:** `syncQueryParams()` is placed after the `try-catch-finally` block. When a fetch fails, the URL query params still get updated to reflect the new filter state, even though displayed data doesn't match. Refreshing the page would re-apply the failed filter.

---

### L-24: Watcher in `onMounted` relies on implicit cleanup

- **File:** `frontend/src/composables/useFormBuilder.ts:569`
- **Description:** A `watch()` created inside `onMounted()` relies on Vue's implicit effect scope cleanup. The `onUnmounted` handler only cleans up the keydown listener and auto-save timer, not this watcher. Fragile if composable is ever used outside a component context.

---

### L-25: DM store `resetState` doesn't invalidate in-flight fetchId counters

- **File:** `frontend/src/stores/dm.ts:222-233`
- **Description:** `resetState` resets all reactive state but does NOT increment `_convFetchId` or `_msgFetchId`. If called during logout while a DM fetch is in-flight, the pending response could arrive after reset and repopulate the store with the previous user's data.

---

### L-26: DataExportView local `formatDate` ignores user locale

- **File:** `frontend/src/views/admin/DataExportView.vue:66-69`
- **Description:** Defines its own `formatDate` using `toLocaleString()` without passing a locale parameter. The project has a shared `formatDateTime()` utility in `src/utils/date.ts` that passes the user's locale. Export history dates display in browser default locale rather than user's selected language.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| **HIGH** | 3 | Event bus retry corruption, bulk role change blast radius, YAML config loss |
| **MEDIUM** | 25 | TOCTOU races (4), event loop blocking (3), stale frontend state (3), missing validation (3), data logic errors (2), missing schedules (1), missing timeouts (1), no-op export (1), download URL validation (1), test gaps (1) |
| **LOW** | 26 | Missing guards, inconsistent patterns, double-fetches, cleanup gaps, type mismatches, locale issues |
| **Total** | **54** | |

### Recommended Fix Priority

1. **H-01** — Event bus retry corruption (data integrity)
2. **H-03** — Docker YAML replicas (infra correctness)
3. **H-02** — Bulk role change blast radius (UX disruption)
4. **M-02** — DM block bypass (security)
5. **M-01** — Form stats corruption (data integrity)
6. **M-13** — Orphan file cleanup never runs (storage leak)
7. **M-15** — Thumbnails never retry (permanent data loss)
8. **M-18** — SIG posts stale navigation (user-facing bug)
9. **M-05** — MinIO delete in transaction (data integrity)
10. **M-07** — Sync S3 blocking event loop (performance)
