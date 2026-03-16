# System / Functional Bug Audit Report

> Date: 2026-03-16 | Scope: Full-stack (FastAPI + Vue 3) | Total: 18 bugs

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **High** | 4 | B01, B02, B03, B04 |
| **Medium** | 8 | B05–B12 |
| **Low** | 6 | B13–B18 |

---

## High Severity

### B01: Single-session design silently invalidates other devices

- **Location**: `backend/app/services/auth.py:31-42`
- **Description**: Session key is `session:{role}:{user_id}`. Each `create_session` call overwrites the previous JTI. When a user logs in on device B, device A's session is silently invalidated — no WebSocket notification, no informative message. The user on device A only discovers it when the next heartbeat fails.
- **Impact**: User confusion; no multi-device support; generic "session expired" instead of "logged in from another device".
- **Reproduction**: Log in on browser A, then log in on browser B. Browser A's next API call returns 401.
- **Suggested fix**: Either (a) support concurrent sessions (`session:{user_id}:{jti}`), or (b) send a `FORCE_LOGOUT` WebSocket message with reason before overwriting the session key.

### B02: Album photo/file uploads have no file size limit — DoS vector

- **Location**: `backend/app/api/v1/endpoints/albums.py:217-218, 243-244`
- **Description**: Both `upload_photo_endpoint` and `upload_file_endpoint` do `await file.read()` with no size limit. Editor uploads enforce `MAX_EDITOR_FILE_SIZE` (20MB), avatars enforce `MAX_AVATAR_SIZE` (2MB), but album uploads are unbounded.
- **Impact**: An authenticated user can upload a multi-GB file, causing OOM crash and filling object storage without quota.
- **Reproduction**: `POST /api/v1/albums/{id}/photos` with a 2GB file.
- **Suggested fix**: Add `MAX_ALBUM_PHOTO_SIZE` / `MAX_ALBUM_FILE_SIZE` constants; read with limit + 1 and reject if exceeded (same pattern as `files.py:44-48`).

### B03: Files with "pending" scan status are served to users

- **Location**: `backend/app/api/v1/endpoints/files.py:263-277`
- **Description**: `serve_file` blocks `malicious`, `unknown`, and `error` statuses, but `pending` files (not yet scanned by VirusTotal) are served freely. The scan is fire-and-forget and can take seconds to minutes.
- **Impact**: Malicious files are downloadable by other users during the scan window, defeating the purpose of virus scanning.
- **Reproduction**: Upload a malicious file, immediately request it via `/api/v1/files/content/{key}`.
- **Suggested fix**: Block `pending` status files or serve with a warning. Frontend already polls scan status — show "scan in progress" message.

### B04: `register_new_user` does not re-verify invite code expiry in transaction

- **Location**: `backend/app/services/auth.py:280-323`
- **Description**: Invite code expiry is checked at the endpoint level, but the actual transaction's UPDATE only verifies `consumed_at IS NULL` — not `expires_at > NOW()`. Between verification and the transaction, Argon2 hashing takes ~100ms–1s, creating a TOCTOU window.
- **Impact**: Users could register with an invite code that expired during the hashing delay.
- **Suggested fix**: Change the UPDATE WHERE clause to include `AND expires_at > NOW()`.

---

## Medium Severity

### B05: ILIKE special character injection in `/users/search`

- **Location**: `backend/app/api/v1/endpoints/users.py:197-230`
- **Description**: Search query uses `f"%{q}%"` without escaping ILIKE special characters (`%`, `_`). Other repos properly use `_escape_ilike()` but this inline query does not.
- **Impact**: `q=%` returns all non-deleted, non-banned users; `q=_` matches single-char usernames.
- **Suggested fix**: Apply `_escape_ilike(q)` and move the query to `user_repo.py`.

### B06: Comment count desynchronizes when deleting comments with replies

- **Location**: `frontend/src/composables/usePostDetail.ts:449`
- **Description**: Frontend decrements `comment_count` by 1 on delete, but backend decrements by `total_deleted` (parent + all children). Deleting a comment with 5 replies causes a count discrepancy of 5.
- **Impact**: Displayed comment count is wrong until page refresh.
- **Suggested fix**: Re-fetch the post after comment deletion, or have the delete API return the updated count.

### B07: Cursor pagination uses text-cast UUID for tie-breaking

- **Location**: `backend/app/repositories/post_repo.py:297-308`
- **Description**: Cursor uses `p.id::text` for lexicographic comparison, which differs from native UUID binary ordering. When multiple posts share the same sort value, posts may be skipped or duplicated.
- **Impact**: Pagination inconsistencies under high concurrency with shared sort values.
- **Suggested fix**: Remove `::text` casts; pass cursor IDs as `uuid.UUID` objects.

### B08: `update_post` can save empty content after sanitization

- **Location**: `backend/app/api/v1/endpoints/posts.py:237-241`
- **Description**: If `sanitize_html()` strips all HTML (e.g., `<script>alert(1)</script>` → `""`), the empty string passes through and overwrites existing content.
- **Impact**: Posts can be emptied via malformed HTML updates.
- **Suggested fix**: After sanitization, reject empty strings with a 422 error.

### B09: `search_posts` silently ignores unsupported `sort` values

- **Location**: `backend/app/repositories/post_repo.py:30-34, 426`
- **Description**: `_SEARCH_SORT_MAP` lacks `popular` (available in `_SORT_MAP`). Passing `sort=popular` silently falls back to `newest`.
- **Impact**: Users get unexpected sort order with no error indication.
- **Suggested fix**: Add `popular` to `_SEARCH_SORT_MAP`, or validate the sort parameter.

### B10: WebSocket `connect()` races with itself on rapid tab switching

- **Location**: `frontend/src/composables/useWebSocket.ts:47-94, 122-129`
- **Description**: Rapid visible→hidden→visible transitions cause concurrent `connect()` calls. The `await getWsUrl()` creates a window where both calls create WebSocket instances.
- **Impact**: Duplicate WebSocket connections → duplicate notification toasts.
- **Suggested fix**: Add a `connecting` boolean guard; check before await, clear in finally.

### B11: `cleanup_orphan_files` materializes all S3 files into memory

- **Location**: `backend/app/tasks/cleanup.py:198`
- **Description**: `list(_iter_editor_files())` loads the entire S3 listing. Deployments with many files risk Celery worker OOM.
- **Impact**: Celery worker crash on deployments with >100K editor files.
- **Suggested fix**: Process files in batches, comparing incrementally.

### B12: `get_form_stats` loads all responses into memory

- **Location**: `backend/app/services/form.py:145-262`
- **Description**: `find_all_responses(form_id)` fetches every response row into Python for aggregation. Statistics are computed in Python loops.
- **Impact**: Memory spike and slow responses for popular forms (10,000+ responses).
- **Suggested fix**: Use SQL aggregation (COUNT/GROUP BY with JSONB extraction).

---

## Low Severity

### B13: Login does not honor `redirect` query parameter

- **Location**: `frontend/src/router/index.ts:279`, `LoginView.vue`
- **Description**: Router guard saves intended destination as `?redirect=`, but after login the user always lands on home page.
- **Suggested fix**: Read `route.query.redirect` after login and navigate there.

### B14: Post history `total` capped at 50 without indication

- **Location**: `backend/app/api/v1/endpoints/posts.py:326`, `backend/app/repositories/post_repo.py:215`
- **Description**: History has `LIMIT 50`, but API returns `total=len(history)` — misleading when >50 records exist.
- **Suggested fix**: Query true count separately, or document the limit.

### B15: Audit log date range has no format validation

- **Location**: `backend/app/api/v1/endpoints/users.py:487-488`
- **Description**: `date_from` / `date_to` are raw strings passed to service layer. Malformed values cause 500 instead of 400.
- **Suggested fix**: Use `date` type in Query parameters.

### B16: Comment creation does not notify post author

- **Location**: `backend/app/services/comment.py:91-100`
- **Description**: Event emits `mention_targets` and `reply_target` but no post-owner target. Top-level comments without @mention generate no notification for the post author.
- **Suggested fix**: Include post owner ID as notification target (excluding commenter).

### B17: `useFetchPaginated` shows stale items during page transitions

- **Location**: `frontend/src/composables/useFetchPaginated.ts:36-53`
- **Description**: On page change, previous data remains while loading. On failure, old data stays at new page number.
- **Suggested fix**: Clear items before fetch, or restore page number on failure.

### B18: Public stats cache is per-process

- **Location**: `backend/app/api/v1/endpoints/public.py:9-32`
- **Description**: `_stats_cache` is module-level. With N workers, DB gets N queries per TTL cycle instead of 1.
- **Suggested fix**: Use Redis cache, or accept the overhead.
