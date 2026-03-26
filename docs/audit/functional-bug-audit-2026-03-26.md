# Functional Bug Audit Report — 2026-03-26

**Scope:** Full codebase — backend (endpoints, services, repositories, core, tasks, schemas), frontend (views, stores, composables, components, utilities, router), infrastructure (Docker, nginx, migrations, CI)

**Methodology:** 5 parallel analysis agents examined every source file; key findings cross-verified by reading actual code.

**Total findings: 70** (5 Critical, 10 High, 30 Medium, 25 Low)

> Includes first pass (F-01 to F-59) + second pass (F-60 to F-70, appended at bottom).

---

## Summary Table

| ID | Severity | Area | Short Description |
|----|----------|------|-------------------|
| F-01 | CRITICAL | Backend | Form `insert()` missing JSON deserialization on RETURNING |
| F-02 | CRITICAL | Frontend | DM store message order broken on pagination (page 2+) |
| F-03 | CRITICAL | Infra | nginx entrypoint reads non-existent `.template` in dev |
| F-04 | CRITICAL | Backend | `SYS_422` error code used with HTTP 400 status (30 occurrences) |
| F-05 | CRITICAL | Frontend | `useFormBuilder` autoSaveTimer leak on component reuse |
| F-06 | HIGH | Backend | Form `insert()` vs `update()` inconsistent questions type |
| F-07 | HIGH | Backend | Advisory lock hash collision risk in `insert_response()` |
| F-08 | HIGH | Frontend | DM unread count can go negative on rapid conversation switching |
| F-09 | HIGH | Frontend | `useFetchPaginated` page rollback on error doesn't re-fetch |
| F-10 | HIGH | Frontend | `usePostDetail` overlayDebounce + scan timers race on postId change |
| F-11 | HIGH | Frontend | `useDropdownKeyNav` focuses hidden/invisible elements |
| F-12 | HIGH | Frontend | DM conversation list pagination reset to page 1 on message send |
| F-13 | HIGH | Frontend | `useLocale` sets locale before API call — reverts on refresh if API fails |
| F-14 | HIGH | Infra | Production nginx shares dev config file with `YOUR_DOMAIN` placeholders |
| F-15 | HIGH | Infra | `alembic check` in prod has no retry on transient DB failure |
| F-16 | MEDIUM | Backend | Idempotency middleware truncates UUID to 16 chars — collision risk |
| F-17 | MEDIUM | Backend | DM cleanup task: MinIO deletion not retried after DB clear succeeds |
| F-18 | MEDIUM | Backend | DM text cleanup holds advisory locks for entire batch |
| F-19 | MEDIUM | Backend | Event bus failure persistence is fire-and-forget — no caller feedback |
| F-20 | MEDIUM | Backend | Form `find_by_id()` response_count pop has no downstream impact but is fragile |
| F-21 | MEDIUM | Backend | DM repo error message doesn't distinguish "not found" vs "not participant" |
| F-22 | MEDIUM | Backend | Form stats returns 0% for all options when no responses (no `has_responses` flag) |
| F-23 | MEDIUM | Backend | Comment edit rate limit checked before existence check — wastes quota |
| F-24 | MEDIUM | Frontend | DM `handleLoadMore` doesn't check if page exceeds total |
| F-25 | MEDIUM | Frontend | DM `markConversationRead` failure silently ignored — UI shows 0 unread |
| F-26 | MEDIUM | Frontend | `useFormBuilder` collapsedQuestions Set persists across form switches |
| F-27 | MEDIUM | Frontend | `useFetchPaginated` concurrent page changes — previousPage rollback wrong |
| F-28 | MEDIUM | Frontend | `useFormSubmit` file upload validates extension only, not MIME type |
| F-29 | MEDIUM | Frontend | `useFormResponseViewer` stats cast `as unknown as QuestionStats[]` — no validation |
| F-30 | MEDIUM | Frontend | `usePostDetail` commentSaving flag shared between root comment and reply |
| F-31 | MEDIUM | Frontend | `usePagination` `setPage()` accepts negative or zero values |
| F-32 | MEDIUM | Frontend | `AuditLogsView` date range validation only disables button — Enter key bypasses |
| F-33 | MEDIUM | Frontend | PostDetailView edit/delete buttons don't guard against concurrent operations |
| F-34 | MEDIUM | Frontend | DMView edit message by findIndex — stale if WS events re-order |
| F-35 | MEDIUM | Infra | `security-headers.conf` (generated file) committed to git with empty CSP vars |
| F-36 | MEDIUM | Infra | Production compose missing `S3_PUBLIC_URL` env var for FastAPI |
| F-37 | MEDIUM | Infra | `alembic.ini` missing `sqlalchemy.url` — direct CLI invocation fails |
| F-38 | MEDIUM | Infra | Dev nginx missing `write` rate limit zone — differs from prod |
| F-39 | MEDIUM | Frontend | WebSocket PONG response has no rate limiting |
| F-40 | MEDIUM | Frontend | `HomeView` fetchMyApplication swallows non-401/404 errors |
| F-41 | LOW | Backend | Guest counter initialization TOCTOU race |
| F-42 | LOW | Backend | `asyncpg.execute()` string comparison `"UPDATE 0"` is fragile |
| F-43 | LOW | Backend | Form response permission check TOCTOU gap (repo trusts service) |
| F-44 | LOW | Backend | `get_dm_friends_only()` returns False for non-existent users |
| F-45 | LOW | Backend | `update_my_profile()` passes None for explicit field clearing |
| F-46 | LOW | Frontend | `formatDate` silent locale fallback to 'en' |
| F-47 | LOW | Frontend | `extractMentions` regex no mention length validation |
| F-48 | LOW | Frontend | `assertShape` no extra key warnings |
| F-49 | LOW | Frontend | DM toast sender name truncation without ellipsis |
| F-50 | LOW | Frontend | `FormsDirectoryView` search query not trimmed |
| F-51 | LOW | Frontend | DMView `getPreferences()` has no timeout |
| F-52 | LOW | Frontend | `LoginView` error computed forces reactivity hack |
| F-53 | LOW | Frontend | `ProfileView` direct ref property mutation |
| F-54 | LOW | Frontend | `useFormBuilder` hardcoded touch drag threshold |
| F-55 | LOW | Infra | Dev nginx 5s DNS TTL causes stale routing after restart |
| F-56 | LOW | Infra | Unused Datadog agent profile in dev compose |
| F-57 | LOW | Backend | Missing explicit `sub` None check in co-author endpoint |
| F-58 | LOW | Backend | Form responses auth timing oracle (two separate queries) |
| F-59 | LOW | Frontend | `useFormResponseDraft` skipTypes `?.value` masks undefined |
| F-60 | MEDIUM | Backend | Guest invite code consumed before `guest_login()` succeeds |
| F-61 | MEDIUM | Backend | Forms from deleted SIGs still visible via `find_by_sig()` |
| F-62 | MEDIUM | Frontend | `toLocaleDateString()` called without locale in 8+ components |
| F-63 | MEDIUM | Frontend | DM store `messagesTotal` increments even on dedup (own echo) |
| F-64 | MEDIUM | Backend | Celery DM text cleanup has no idempotency — double-run loses char decrements |
| F-65 | LOW | Backend | DM admin endpoint returns 200 with empty list for non-existent conversations |
| F-66 | LOW | Backend | DM orphan cleanup S3 paginator has no timeout — can hang indefinitely |
| F-67 | LOW | Backend | WS `FORCE_LOGOUT` delivery not guaranteed before connection close |
| F-68 | LOW | Frontend | DM presigned URLs not refreshed after VirusTotal scan completes |
| F-69 | LOW | Frontend | Lightbox `canDelete` binding doesn't bounds-check `lightboxIndex` |
| F-70 | LOW | Frontend | Form deadline not validated client-side — submission fails only on backend |

---

## CRITICAL (5)

### F-01: Form `insert()` missing JSON deserialization on RETURNING

- **File:** `backend/app/repositories/form_repo.py:99-120` (also `insert_in_conn` at 236-271)
- **Category:** Data Integrity / Type Inconsistency
- **Description:** Both `insert()` and `insert_in_conn()` serialize `questions` to JSON via `json.dumps(questions)` before INSERT with `$9::jsonb`. After `RETURNING *`, the result is returned as-is without checking whether `questions` is a string or dict. asyncpg's JSONB decoding behavior after explicit `::jsonb` cast on a string parameter is unpredictable — it may return a raw string instead of a parsed dict.

  Meanwhile, `update()` (line 206-207) explicitly checks `isinstance(result.get("questions"), str)` and deserializes. This inconsistency means:
  - Form **creation** may return stringified questions
  - Form **update** always returns deserialized questions
  - Downstream converters must defensively handle both types

- **Expected:** All form repo functions return `questions` as `dict` (deserialized)
- **Actual:** `insert()` and `insert_in_conn()` may return `questions` as `str`
- **Impact:** API responses for form creation may contain malformed `questions` field; converter `safe_json_parse()` compensates but this is fragile

---

### F-02: DM store message order broken on pagination with WebSocket interleaving

- **File:** `frontend/src/stores/dm.ts:72-85`
- **Category:** Logic Error / Race Condition
- **Description:** `fetchMessages()` receives messages in `ORDER BY created_at DESC` from the backend and reverses them to chronological order at line 74. On page 2+ (loading older messages), the reversed chunk is prepended via `unshift` at line 82. The dedup filter at line 80 (`existingIds`) only prevents duplicate IDs — it does NOT verify chronological ordering after prepend. If a WebSocket-delivered message arrived between page 1 and page 2 fetch, the prepended chunk may interleave with existing messages, breaking chronological order.

- **Expected:** Messages maintain strict chronological order after pagination + WebSocket interleaving
- **Actual:** WS-delivered messages can create ordering gaps when older pages are prepended
- **Impact:** Messages may appear out of order in the chat thread after loading older pages

---

### F-03: nginx entrypoint reads non-existent `.template` in dev

- **File:** `nginx/docker-entrypoint.sh:8-10`
- **Category:** Docker Configuration Error
- **Description:** The entrypoint unconditionally runs:
  ```bash
  envsubst '$STORAGE_CSP_ORIGIN' \
      < /etc/nginx/snippets/security-headers.conf.template \
      > /etc/nginx/snippets/security-headers.conf
  ```
  In the dev Docker Compose, `nginx/snippets/` is mounted directly. If `security-headers.conf.template` does not exist in the mounted directory but `security-headers.conf` does, this command fails with "No such file or directory", preventing the nginx container from starting.

- **Expected:** Entrypoint should check if template exists, or dev compose should provide the template file
- **Actual:** Dev nginx container may fail to start if template file is missing
- **Impact:** Dev environment broken — nginx cannot serve frontend or proxy API

---

### F-04: `SYS_422` error code used with HTTP 400 status (30 occurrences)

- **File:** 7 files across `backend/app/` — `users.py` (12), `posts.py` (5), `sigs.py` (3), `comments.py` (3), `social.py` (5), `dm.py` (1), `co_author.py` (1)
- **Category:** Wrong HTTP Status Code / API Contract Violation
- **Description:** 30 instances of `AppError(ErrorCode.SYS_422, 400, ...)` where the error code semantically means "422 Unprocessable Entity" but the actual HTTP status returned is 400 (Bad Request). Another 19 instances correctly use `SYS_422, 422`. This inconsistency means:
  - Clients parsing `error.code === "SYS_422"` expect 422 status but get 400
  - The same error code maps to two different HTTP statuses depending on the endpoint
  - Frontend error handling cannot reliably distinguish 400 (bad request) from 422 (validation error)

- **Expected:** `SYS_422` should always pair with HTTP 422, or use a different error code for 400
- **Actual:** 30 occurrences return 400, 19 return 422
- **Impact:** Inconsistent API contract; client-side error handling unreliable

---

### F-05: `useFormBuilder` autoSaveTimer leak on component reuse

- **File:** `frontend/src/composables/useFormBuilder.ts:351-358`
- **Category:** Timer / Memory Leak
- **Description:** `startAutoSave()` guards against duplicate starts with `if (autoSaveTimer !== null) return`. However, if the composable is used in a component that gets reused by Vue's router (same component, different route params), `onMounted` calls `startAutoSave()` again. The guard prevents a new timer only if the old variable reference is intact. If the composable is re-initialized (new instance), `autoSaveTimer` starts as `null`, so a new interval is created without clearing the old one from the previous instance. The old interval continues running with a stale closure.

- **Expected:** Old interval should be cleared when composable is re-initialized or component is reused
- **Actual:** Multiple intervals can accumulate, each triggering `saveDraftNow()` with potentially stale state
- **Impact:** Memory leak; stale draft saves; performance degradation over time

---

## HIGH (10)

### F-06: Form `insert()` vs `update()` inconsistent questions type

- **File:** `backend/app/repositories/form_repo.py:99-120, 171-212`
- **Category:** Data Consistency
- **Description:** `insert()` returns questions field as-is from `RETURNING *` (may be string or dict). `update()` explicitly deserializes at line 206-207. `find_by_id()` returns as-is from SELECT. Three different serialization states for the same field.
- **Impact:** Converters and API responses behave differently for create vs update vs read

### F-07: Advisory lock hash collision risk in `insert_response()`

- **File:** `backend/app/repositories/form_repo.py:373`
- **Category:** Race Condition
- **Description:** `pg_advisory_xact_lock(hashtext($1::text))` where `$1` is form_id UUID. `hashtext()` returns a 32-bit integer — with enough concurrent forms, two different form_ids can hash to the same value, causing unintended cross-form serialization or, worse, both exceeding `max_respondents` if the lock doesn't truly isolate them.
- **Impact:** Rare but possible: two concurrent form submissions on different forms block each other, or `max_respondents` enforcement fails due to lock collision

### F-08: DM unread count state inconsistency on rapid switching

- **File:** `frontend/src/views/DMView.vue:128-141`
- **Category:** State Consistency / Race Condition
- **Description:** `selectConversation()` calls `markConversationRead()` API, then decrements `dmStore.unreadCount`. If the user switches conversations rapidly, overlapping API calls can cause the unread count to become stale. The `catch` at line 138 ignores `markConversationRead` failures, but the UI has already committed to showing 0 unread for that conversation.

  More precisely: `markConversationRead()` is awaited at line 131, and lines 132-137 only execute on success. But if the user navigates away before the await resolves, the stale callback still runs and modifies the now-irrelevant conversation's state.
- **Impact:** Navbar unread badge may not reflect true server state; requires page refresh to sync

### F-09: `useFetchPaginated` page rollback on error doesn't re-fetch

- **File:** `frontend/src/composables/useFetchPaginated.ts:46-49`
- **Category:** State Recovery
- **Description:** On fetch failure, `setPage(previousPage)` restores the page number, but doesn't trigger a re-fetch. The user sees an error message with old data, but the page indicator shows the restored page. The `items` array still contains data from the previously successful fetch.
- **Impact:** UI shows inconsistent page number vs displayed data after a failed page navigation

### F-10: `usePostDetail` scan timer race on postId change

- **File:** `frontend/src/composables/usePostDetail.ts:685-717`
- **Category:** Timer Lifecycle
- **Description:** When `postId` changes (component reuse), the watcher clears scan timers and overlay debounce timer. However, `fetchPost().then(() => scanPostImages())` at line 714 is fire-and-forget — if the postId changes again before this promise resolves, new scan timers may be created for the old post's images.
- **Impact:** Scan polling for stale post images wastes API calls; minor resource leak

### F-11: `useDropdownKeyNav` focuses hidden/invisible elements

- **File:** `frontend/src/composables/useDropdownKeyNav.ts:49-65`
- **Category:** Keyboard Navigation
- **Description:** ArrowUp/ArrowDown cycle through all elements with `tabindex="-1"` in the menu container, without checking visibility (`display: none`, `visibility: hidden`). Conditionally hidden menu items (e.g., admin-only actions) receive focus, breaking keyboard navigation.
- **Impact:** Focus trap on invisible menu items; keyboard users cannot navigate past hidden options

### F-12: DM conversation list pagination reset on message send

- **File:** `frontend/src/views/DMView.vue:186-190`
- **Category:** State Consistency
- **Description:** When creating a new conversation via `handleSend()`, the code calls `dmStore.fetchConversations(1, convPagination.pageSize)` to refresh the list. This resets pagination to page 1, losing the user's scroll position and current page in the conversation list.
- **Impact:** User loses their place in a long conversation list after sending a message to a new contact

### F-13: `useLocale` sets locale before API call — reverts on refresh

- **File:** `frontend/src/composables/useLocale.ts:34-48`
- **Category:** Optimistic Update Without Rollback
- **Description:** `setLocale()` applies the locale change to UI and `localStorage` at lines 36-42 **before** the API call at line 44. If the API call fails (caught silently at line 45), the browser shows the new locale but the database still has the old value. On next login, `syncFromProfile()` will revert the locale to the DB value.
- **Impact:** User sees locale change, but it reverts after re-login — confusing UX

### F-14: Production nginx shares dev config with `YOUR_DOMAIN` placeholders

- **File:** `docker-compose.prod.yml:44`, `nginx/conf.d/default.conf`
- **Category:** Infrastructure Configuration
- **Description:** Production compose mounts `./nginx/conf.d:/etc/nginx/conf.d` which contains `YOUR_DOMAIN` placeholders and `#HTTPS` comment-prefix patterns. The entrypoint `sed` commands process these at runtime. If `SERVER_DOMAIN` is not set or `sed` fails, HTTPS blocks remain commented out and domain names unresolved.
- **Impact:** Production deployment may serve with wrong domain or without HTTPS if env vars are misconfigured

### F-15: `alembic check` in production has no retry on transient DB failure

- **File:** `docker-compose.prod.yml:72`
- **Category:** Migration Reliability
- **Description:** Production migrate service runs `alembic upgrade head && alembic check`. If DB has a transient connection issue after `upgrade head` succeeds but before `check` completes, the entire migrate service fails. All dependent services (fastapi, celery) won't start.
- **Impact:** Production deployments can fail from transient DB connectivity issues during migration check

---

## MEDIUM (25)

### F-16: Idempotency middleware truncates UUID to 16 chars

- **File:** `backend/app/middleware/idempotency.py:47`
- **Category:** Key Collision Risk
- **Description:** `payload["sub"][:16]` truncates UUIDv4 (format `xxxxxxxx-xxxx-...`) to the first 16 chars. Two users whose UUIDs share the same first 16 characters would share idempotency keys, causing one user's cached response to be served to the other.
- **Impact:** Extremely rare but theoretically possible cross-user response leakage

### F-17: DM cleanup task — MinIO deletion not retried after partial failure

- **File:** `backend/app/tasks/dm_cleanup.py:31-87`
- **Category:** Data Consistency
- **Description:** If MinIO file deletion succeeds but the subsequent DB clear fails, the next cleanup run won't retry the MinIO deletion because the attachment_key is already removed from the DB. This leaves orphan files in MinIO.
- **Impact:** Slow storage leak for failed DM file cleanup operations

### F-18: DM text cleanup holds advisory locks for entire batch

- **File:** `backend/app/tasks/dm_cleanup.py:125-131`
- **Category:** Lock Contention
- **Description:** Advisory locks are acquired per conversation within a single transaction. For many conversations, locks are held until the entire batch completes, blocking concurrent DM sends.
- **Impact:** DM sends may block for 1-10 seconds during hourly cleanup runs

### F-19: Event bus failure persistence is fire-and-forget

- **File:** `backend/app/core/event_bus.py:87`
- **Category:** Error Handling
- **Description:** When a handler fails, `_persist_failed_event()` is called but its failure is silently logged. Callers can't distinguish between "failed and recorded for retry" vs "failed and lost".
- **Impact:** During Redis outages, event handler failures are lost with no audit trail

### F-20: Form `find_by_id()` response_count pop is fragile

- **File:** `backend/app/repositories/form_repo.py:142-144`
- **Category:** API Design
- **Description:** `result.pop("response_count")` correctly removes the key and returns it as a tuple element. However, any code that calls `find_by_id()` twice on the same dict reference would fail on the second pop. Not a current bug, but fragile pattern.
- **Impact:** Low — defensive concern only

### F-21: DM repo error doesn't distinguish "not found" vs "not participant"

- **File:** `backend/app/repositories/dm_repo.py:481-493`
- **Category:** Error Clarity
- **Description:** When `send_message_atomic()` can't find the recipient (CASE returns NULL), the error message "Conversation not found or invalid participant" is generic.
- **Impact:** Harder to debug DM send failures

### F-22: Form stats returns 0% when no responses (missing flag)

- **File:** `backend/app/services/form.py:294`
- **Category:** Missing Edge Case
- **Description:** Stats computation returns `0.0%` for all options when `total_responses == 0`. No `has_responses` flag helps the frontend distinguish "no data yet" from "all zeroes".
- **Impact:** Frontend may show misleading charts instead of "no responses yet" message

### F-23: Comment edit rate limit checked before existence

- **File:** `backend/app/api/v1/endpoints/comments.py:91`
- **Category:** Logic Order
- **Description:** Rate limit is checked before verifying the comment exists. Editing a non-existent comment wastes rate limit quota.
- **Impact:** User's rate limit quota wasted on 404 attempts

### F-24: DM `handleLoadMore` doesn't check page bounds

- **File:** `frontend/src/views/DMView.vue:154-162`
- **Category:** Missing Bounds Check
- **Description:** `handleLoadMore()` increments `currentMsgPage` and fetches without checking if the page exceeds total messages. `hasMoreMessages` guard may not update synchronously.
- **Impact:** Unnecessary API calls beyond available data

### F-25: DM `markConversationRead` failure drops unread state

- **File:** `frontend/src/views/DMView.vue:128-141`
- **Category:** Silent Error
- **Description:** The `markConversationRead()` API is awaited before updating local state, so local state is only modified on success. However, the `catch` block does not revert or notify the user, so a network error means the conversation appears "read" locally until the next time conversations are fetched (which may not happen until page navigation).
- **Impact:** Inconsistent read state between client and server on transient network errors

### F-26: `useFormBuilder` collapsedQuestions persists across forms

- **File:** `frontend/src/composables/useFormBuilder.ts:40`
- **Category:** State Cleanup
- **Description:** The `collapsedQuestions` Set is never reset when editing a different form. If question UUIDs match across forms, collapse state leaks.
- **Impact:** Questions appear unexpectedly collapsed when switching forms

### F-27: `useFetchPaginated` concurrent page changes — wrong rollback

- **File:** `frontend/src/composables/useFetchPaginated.ts:36-55`
- **Category:** Race Condition
- **Description:** If `setPage(2)` then `setPage(3)` quickly, the first fetch's `previousPage` is 1, second's is 2. If both fail, page state may flicker. `fetchId` guard prevents stale data updates but doesn't prevent page indicator inconsistency.
- **Impact:** Brief UI inconsistency during rapid page changes with errors

### F-28: `useFormSubmit` validates extension only, not MIME

- **File:** `frontend/src/composables/useFormSubmit.ts:327-336`
- **Category:** Validation Gap
- **Description:** File validation checks extension but not `file.type`. Renamed files pass client-side. Server catches via magic bytes, but client feedback is missing.
- **Impact:** Users don't get immediate feedback for misnamed files

### F-29: `useFormResponseViewer` unsafe type cast

- **File:** `frontend/src/composables/useFormResponseViewer.ts:131-135`
- **Category:** Type Safety
- **Description:** `as unknown as QuestionStats[]` bypasses TypeScript. Malformed API responses surface as runtime errors in templates.
- **Impact:** Harder to debug malformed responses

### F-30: Shared `commentSaving` flag for root + reply

- **File:** `frontend/src/composables/usePostDetail.ts:419-437`
- **Category:** State Overlap
- **Description:** Both `submitComment()` and `submitInlineReply()` use `commentSaving`. Concurrent submission causes premature flag reset.
- **Impact:** Double-submit possible; loading spinner inconsistent

### F-31: `usePagination` accepts negative/zero page

- **File:** `frontend/src/composables/usePagination.ts:18-20`
- **Category:** Input Validation
- **Description:** No guard against `setPage(0)` or `setPage(-1)`.
- **Impact:** API request with `page=0` returns unexpected results

### F-32: `AuditLogsView` date validation bypassed by Enter

- **File:** `frontend/src/views/admin/AuditLogsView.vue:45-46, 159`
- **Category:** Form Validation
- **Description:** Invalid date range disables the "Apply" button but Enter key in date inputs still submits.
- **Impact:** Users can submit invalid date ranges via keyboard

### F-33: PostDetailView edit/delete lacks operation guard

- **File:** `frontend/src/views/forum/PostDetailView.vue:188, 252-254`
- **Category:** Double-Submit
- **Description:** Edit save and delete buttons don't disable during async operations. Multiple clicks trigger concurrent API calls.
- **Impact:** Duplicate requests; potential data inconsistency

### F-34: DMView edit by findIndex — stale on WS reorder

- **File:** `frontend/src/views/DMView.vue:168-174`
- **Category:** Stale Reference
- **Description:** After editing a DM, `findIndex` by ID is correct, but `dmStore.messages[idx] = edited` is direct mutation. If WS event reorders between `findIndex` and assignment, index is stale.
- **Impact:** Very rare — practically safe in single-threaded JS, but not guaranteed if reactivity triggers intermediate updates

### F-35: Generated `security-headers.conf` committed to git

- **File:** `nginx/snippets/security-headers.conf:15`
- **Category:** Configuration Management
- **Description:** The envsubst-generated file is committed with empty CSP variable expansion. Should be `.gitignore`d.
- **Impact:** Confusing diffs; read-only mount breaks entrypoint

### F-36: Production compose missing `S3_PUBLIC_URL`

- **File:** `docker-compose.prod.yml`
- **Category:** Missing Env Var
- **Description:** `.env.production.example` defines `S3_PUBLIC_URL` but it's not in the FastAPI service environment in production compose.
- **Impact:** Presigned URLs use raw S3 endpoint — CORS failures in production

### F-37: `alembic.ini` missing `sqlalchemy.url`

- **File:** `backend/alembic.ini:1-37`
- **Category:** Developer Experience
- **Description:** No default URL — direct CLI outside Docker fails.
- **Impact:** Local alembic commands require containerized environment

### F-38: Dev nginx missing `write` rate limit

- **File:** `nginx/conf.d.dev/default.conf:46`
- **Category:** Dev/Prod Parity
- **Description:** Dev lacks `limit_req zone=write burst=5 nodelay;` present in prod.
- **Impact:** Rate-limit bugs not caught in development

### F-39: WebSocket PONG not rate-limited

- **File:** `frontend/src/composables/useWebSocket.ts:119-122`
- **Category:** Resource Exhaustion
- **Description:** Every PING receives immediate PONG. Malicious server could flood PINGs.
- **Impact:** Low — requires compromised server

### F-40: `HomeView` swallows non-401/404 errors

- **File:** `frontend/src/views/HomeView.vue:112-119`
- **Category:** Error Handling
- **Description:** `fetchMyApplication` silently ignores 401/404 but also swallows all other error codes.
- **Impact:** Unexpected API errors are invisible to user

---

## LOW (19)

### F-41: Guest counter initialization TOCTOU race

- **File:** `backend/app/services/auth.py:172-180`
- **Description:** Between first `get()` returning None and `set()` in `sync_guest_counter()`, another process could initialize. Mitigated by Lua script for increments.
- **Impact:** Counter may be off by 1 on first startup

### F-42: `asyncpg.execute()` string comparison fragile

- **File:** `backend/app/api/v1/endpoints/admin.py:64, 124`
- **Description:** Compares `result == "UPDATE 0"` — works but relies on asyncpg return format.
- **Impact:** Could break on asyncpg major version update

### F-43: Form response permission TOCTOU gap

- **File:** `backend/app/repositories/form_repo.py:360`
- **Description:** Repository trusts service layer for guest permission. If service bypassed, guests submit to restricted forms.
- **Impact:** Defense-in-depth concern; service layer is the actual guard

### F-44: `get_dm_friends_only()` returns False for non-existent users

- **File:** `backend/app/repositories/dm_repo.py:727`
- **Description:** Missing user and "no preference" both return False.
- **Impact:** Minimal — caller validates user existence elsewhere

### F-45: `update_my_profile()` passes None for field clearing

- **File:** `backend/app/api/v1/endpoints/users.py:82-86`
- **Description:** Uses `model_fields_set` correctly, but service layer should validate which fields are clearable.
- **Impact:** Depends on service validation

### F-46: `formatDate` silent locale fallback

- **File:** `frontend/src/utils/date.ts:8`
- **Description:** Unsupported locale silently falls back to 'en' without dev warning.

### F-47: `extractMentions` no mention length limit

- **File:** `frontend/src/utils/html.ts:65`
- **Description:** Regex matches mentions of any length. Very long mentions waste backend lookups.

### F-48: `assertShape` no extra key warnings

- **File:** `frontend/src/utils/apiValidation.ts:6-19`
- **Description:** Only warns on missing keys, not unexpected extra keys from API.

### F-49: DM toast sender name truncation without ellipsis

- **File:** `frontend/src/composables/useWebSocket.ts:147`
- **Description:** `.slice(0, 50)` without `...` indicator.

### F-50: `FormsDirectoryView` search not trimmed

- **File:** `frontend/src/views/forms/FormsDirectoryView.vue`
- **Description:** Search input sent without `.trim()`.

### F-51: DMView `getPreferences()` no timeout

- **File:** `frontend/src/views/DMView.vue:64-70`
- **Description:** Awaited API with no timeout can block component mount.

### F-52: `LoginView` error reactivity hack

- **File:** `frontend/src/views/LoginView.vue:30-34`
- **Description:** Uses `void currentLocale.value` to force computed re-evaluation.

### F-53: `ProfileView` direct ref mutation

- **File:** `frontend/src/views/ProfileView.vue:271-273`
- **Description:** Directly sets `dangerZoneRef.value.showDeleteConfirm = false`.

### F-54: `useFormBuilder` hardcoded touch drag threshold

- **File:** `frontend/src/composables/useFormBuilder.ts:301`
- **Description:** 50px threshold may be too sensitive on tablets.

### F-55: Dev nginx 5s DNS TTL stale routing

- **File:** `nginx/conf.d.dev/default.conf:8`
- **Description:** `valid=5s` causes 502 errors after FastAPI restart.

### F-56: Unused Datadog agent in dev compose

- **File:** `docker-compose.yml:267-287`
- **Description:** Disabled by profile but adds clutter.

### F-57: Missing explicit `sub` None check

- **File:** `backend/app/api/v1/endpoints/users.py:271-283`
- **Description:** Relies on dependency injection guarantee. Not a bug in practice.

### F-58: Form responses auth timing oracle

- **File:** `backend/app/api/v1/endpoints/forms.py:332-347`
- **Description:** Two separate queries for form fetch + membership check. Timing difference theoretically reveals form existence.

### F-59: `useFormResponseDraft` skipTypes masks undefined

- **File:** `frontend/src/composables/useFormResponseDraft.ts:76-85`
- **Description:** `skipTypes?.value` silently skips filtering if ref is undefined.

---

## SECOND PASS — Additional Findings (F-60 to F-70)

*Found by 5 additional focused agents examining auth flows, data lifecycle, SQL correctness, DM system, and frontend interactions. All claims cross-verified against actual code — false positives (e.g., 5 incorrect OFFSET/LIMIT swap claims, misattributed race conditions) were rejected.*

### MEDIUM (5)

### F-60: Guest invite code consumed before `guest_login()` succeeds

- **File:** `backend/app/api/v1/endpoints/auth.py:163-181`
- **Category:** Resource Waste / Logic Order
- **Description:** `consume_invite_code()` is called at line 163 (atomically marks the code as used). Then `increment_guest_ip_counter()` at line 170 and `guest_login()` at line 177 may both fail — if guest capacity is full, the response at line 181 is an error, but the invite code is already consumed and cannot be recovered. The IP counter is decremented at line 180, but the invite code is not restored.
- **Expected:** Consume invite code only after confirming guest session creation succeeds
- **Actual:** Code is permanently consumed even when guest capacity is full
- **Impact:** Users with valid invite codes are told "capacity full" and their code is wasted

### F-61: Forms from deleted SIGs still visible via `find_by_sig()`

- **File:** `backend/app/repositories/form_repo.py:274-307`, endpoint at `forms.py:86-100`
- **Category:** Data Consistency
- **Description:** `find_by_sig()` filters `f.is_deleted = false` but does NOT join to `sigs` table to verify `s.is_deleted = false`. The endpoint `get_sig_forms()` at forms.py:86 also doesn't check SIG deletion status. A direct API call to `GET /sigs/{sig_id}/forms` where the SIG is soft-deleted will still return its forms.
- **Expected:** Forms from deleted SIGs should be excluded
- **Actual:** Forms remain accessible via API after SIG deletion
- **Impact:** Data leaks from deleted SIGs; forms still submittable if SIG is deleted

### F-62: `toLocaleDateString()` called without locale in 8+ components

- **Files:** `FormsDirectoryView.vue:75`, `AlbumLayout.vue:338`, `AlbumCommentsView.vue:52`, `FormShareCard.vue:20`, `PostCard.vue:143`, `QuickCommentPanel.vue:83`, `SigsDirectoryView.vue:85`, `SigFormsView.vue:301`, `utils/datetime.ts:11`
- **Category:** Internationalization
- **Description:** These files call `new Date(...).toLocaleDateString()` without passing a locale parameter, while the project has `formatDate()` in `src/utils/date.ts` that properly accepts locale. The browser's default locale is used instead of the user's selected language from `preferred_language`.
- **Expected:** Use `formatDate(date, locale)` or pass `locale.value` to `toLocaleDateString()`
- **Actual:** Dates format according to browser locale, not the app's i18n setting
- **Impact:** Date formatting inconsistent with user's selected language

### F-63: DM store `messagesTotal` increments even on dedup

- **File:** `frontend/src/stores/dm.ts:162-169`
- **Category:** State Consistency
- **Description:** In `addFromWebSocket()`, when own message is echoed back (line 162), the code calls `_appendMessage(message)` at line 165 which deduplicates (skips if message ID already exists in array). But `messagesTotal.value += 1` at line 167 runs unconditionally regardless of whether the message was actually added.

  Multi-tab scenario: Tab A sends a message (adds it optimistically), Tab A receives the WS echo → `_appendMessage` skips (dedup), but `messagesTotal` still increments → total drifts +1 from actual count.
- **Expected:** Only increment `messagesTotal` if the message was actually new
- **Actual:** Increments unconditionally, causing total to exceed actual message count
- **Impact:** Pagination metadata becomes inaccurate; "load more" may appear when there are no more messages

### F-64: Celery DM text cleanup has no idempotency — double-run loses char decrements

- **File:** `backend/app/tasks/dm_cleanup.py:90-151`
- **Category:** Task Reliability
- **Description:** `cleanup_dm_expired_text` is scheduled via Celery Beat with no idempotency mechanism. If the task is enqueued twice (worker restart, Beat overlap), the second run finds messages already deleted by the first run and skips them. However, if the first run deleted messages but failed partway through the `total_chars` decrement loop, the second run cannot retry those decrements because the messages (and their content lengths) are already gone.
- **Expected:** Failed char decrements should be retriable
- **Actual:** Data for retry is lost when messages are deleted
- **Impact:** Conversation `total_chars` counter may be permanently inflated after a partial cleanup failure

### LOW (6)

### F-65: DM admin endpoint returns 200 for non-existent conversations

- **File:** `backend/app/api/v1/endpoints/dm.py:75-118`
- **Description:** `GET /dm/admin/conversations/{id}/messages` returns `{"messages": [], "total": 0}` for any conversation ID, including non-existent ones. Should return 404 for invalid IDs.
- **Impact:** Audit logging can't distinguish "empty conversation" from "invalid ID"

### F-66: DM orphan cleanup S3 paginator has no timeout

- **File:** `backend/app/tasks/dm_cleanup.py:184-195`
- **Description:** `loop.run_in_executor(None, _list_all_dm_keys)` calls boto3 paginator without timeout. If MinIO is unresponsive, the task hangs indefinitely.
- **Impact:** Celery worker thread blocked; may exhaust worker pool

### F-67: WS `FORCE_LOGOUT` delivery not guaranteed

- **File:** `backend/app/api/v1/endpoints/ws.py:126-134`
- **Description:** On JTI mismatch, `FORCE_LOGOUT` is sent before WebSocket close. If the client's recv buffer is full, the message may not arrive. Client only sees a raw close code (4003).
- **Impact:** Client doesn't know why connection was closed; may attempt reconnect loop

### F-68: DM presigned URLs not refreshed after scan completes

- **File:** `frontend/src/stores/dm.ts:140-187`
- **Description:** When a `NEW_DM` with a pending-scan attachment arrives via WS, the message has no `attachment_url`. After the VirusTotal scan completes, there's no mechanism to refresh the presigned URL in the rendered message.
- **Impact:** User must manually refresh or re-open conversation to see attachment

### F-69: Lightbox `canDelete` binding doesn't bounds-check index

- **File:** `frontend/src/views/albums/AlbumPhotosView.vue:206`
- **Description:** Template uses `photos[lightboxIndex] ? canDeleteThisPhoto(...)  : false`. If `photos` array shrinks after deletion while lightbox is open, the truthy check handles `undefined` gracefully, but the access pattern is fragile.
- **Impact:** Edge case — lightbox could briefly show stale data after batch delete

### F-70: Form deadline not validated client-side

- **File:** `frontend/src/views/forms/FormView.vue:222-224`
- **Description:** Form submission view checks `form.is_active` from server but doesn't client-side validate if deadline has passed based on local clock. Users can fill out a form only to be rejected on submit.
- **Impact:** Poor UX — wasted form-filling effort

---

## Recommended Fix Priority

### P0 — Fix Immediately (blocks correctness or deployment)

1. **F-01 + F-06**: Add `isinstance(result.get("questions"), str)` check + `json.loads()` to `insert()` and `insert_in_conn()`
2. **F-03**: Add `[ -f template ]` guard in `docker-entrypoint.sh`, or ensure `.template` file exists in dev mount
3. **F-04**: Audit all 30 occurrences of `SYS_422, 400` — change to `SYS_400, 400` or `SYS_422, 422` consistently

### P1 — Fix Soon (user-facing bugs)

4. **F-02**: Add `sort()` by `created_at` after prepending older messages in DM store
5. **F-05**: Clear old interval in `startAutoSave()` before creating new one: `if (autoSaveTimer !== null) clearInterval(autoSaveTimer)`
6. **F-08**: Only decrement unread count after successful API response; revert on failure
7. **F-09**: After page rollback on error, either re-fetch previous page or display stale-data indicator
8. **F-11**: Filter dropdown items to only visible/focusable elements before key nav
9. **F-13**: Only persist locale to `localStorage` after API success, or rollback on failure
10. **F-14**: Separate prod nginx config from dev, or add startup validation for `SERVER_DOMAIN`
11. **F-15**: Add retry logic or `|| true` for `alembic check` in production compose

### P2 — Fix When Convenient

12. **F-07, F-16**: Use full UUID for lock keys and idempotency namespaces
13. **F-12, F-24, F-31**: Add pagination bounds checks
14. **F-22**: Add `has_responses` flag to form stats response
15. **F-23**: Reorder comment edit: existence check before rate limit
16. **F-26**: Clear `collapsedQuestions` on form switch
17. **F-28**: Add client-side MIME type check for file uploads
18. **F-30, F-33**: Per-operation loading flags; disable buttons during async
19. **F-17, F-18, F-19, F-64**: DM cleanup task improvements (idempotency, retry, lock scope)
20. **F-35, F-36, F-37, F-38**: Infrastructure config cleanup
21. **F-60**: Move `consume_invite_code()` after `guest_login()` succeeds
22. **F-61**: Add `JOIN sigs s ON s.id = f.sig_id` + `s.is_deleted = false` to `find_by_sig()`
23. **F-62**: Replace `toLocaleDateString()` with `formatDate(date, locale)` in 8+ components
24. **F-63**: Guard `messagesTotal += 1` with `_appendMessage` return value

### P3 — Backlog

25. All LOW items (F-41 through F-59, F-65 through F-70)

---

## Second-Pass Rejected Claims (False Positives)

The following claims from second-pass agents were **verified as incorrect**:

| Claim | Why Rejected |
|-------|-------------|
| `application_repo.py` OFFSET/LIMIT param swap | Verified: `params.extend([offset, limit])` matches `OFFSET ${idx} LIMIT ${idx+1}` — correct |
| `audit_repo.py` LIMIT/OFFSET param swap | Verified: `params.extend([page_size, offset])` matches `LIMIT ${idx} OFFSET ${idx+1}` — correct |
| `report_repo.py` LIMIT/OFFSET param swap | Verified: `params.extend([limit, offset])` matches `LIMIT ${idx} OFFSET ${idx+1}` — correct |
| `user_repo.py` param index off-by-one | Verified: parameter ordering is correct |
| `comment_repo.py` count query missing filter | Verified: fallback count query DOES include `exclude_user_ids` at line 118-120 |
| Auth invite code TOCTOU race | `consume_invite_code()` is atomic — second concurrent request gets `False` and errors at line 164 |
| DM `edit_message` char delta pre-lock race | Advisory lock at line 558 serializes all conversation operations; delta calculated from FOR-UPDATE-locked row |
| DM `recall_message` lock released before cleanup | By design — `total_chars` updated inside transaction; storage cleanup is non-critical |
| `sig_repo.soft_delete` FK constraint order | All operations within single `conn.transaction()` — order doesn't cause FK violations |
