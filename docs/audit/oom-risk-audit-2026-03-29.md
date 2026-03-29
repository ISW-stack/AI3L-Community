# OOM Risk Audit — 2026-03-29

## Summary

Full OOM (Out of Memory) risk analysis across backend, frontend, and infrastructure layers.

- **5 Critical** / **5 High** / **6 Medium** findings
- Infrastructure layer is well-hardened (Docker memory limits, Redis maxmemory, Celery max-memory-per-child, nginx buffering)
- Main risks are in backend code: unbounded queries, in-memory file accumulation, startup data loading

---

## CRITICAL

### C-1: Blacklist — startup loads ALL block relationships into memory

- **File:** `backend/app/core/blacklist.py`
- **Issue:** On app startup, `SELECT blocker_id, blocked_id FROM blocks` fetches the entire table into Python memory. Per-request `SMEMBERS` also loads the full set for each user.
- **Impact:** 1M+ block relationships → hundreds of MB at startup; per-request full set load adds pressure on every filtered endpoint (comments, posts, notifications, DMs).
- **Fix:** Replace with on-demand `SISMEMBER` checks or batch-load only the requesting user's blocks. Remove full-table startup load.

### C-2: Album repo — `find_all_photos_for_album()` has no LIMIT

- **File:** `backend/app/repositories/album_repo.py` (line ~153)
- **Issue:** `fetch()` returns all photos for an album without LIMIT. Used for cascade cleanup.
- **Impact:** Album with 10K+ photos loads entire list into memory.
- **Fix:** Add batched deletion (e.g., `LIMIT 500` in a loop with `DELETE ... RETURNING id`).

### C-3: Citation repo — `find_existing_citations()` has no LIMIT

- **File:** `backend/app/repositories/citation_repo.py` (line ~69)
- **Issue:** Fetches ALL citations for a post without LIMIT during updates.
- **Impact:** Post with 1K+ citations loads full list.
- **Fix:** Add LIMIT or use batched comparison.

### C-4: Album upload — file chunks accumulated in memory

- **File:** `backend/app/api/v1/endpoints/albums.py` (line ~161)
- **Issue:**
  ```python
  chunks: list[bytes] = []
  while chunk := await file.read(8192):
      chunks.append(chunk)
  file_data = b"".join(chunks)
  ```
  Defeats chunked reading by accumulating entire file (up to 50MB) in RAM before processing.
- **Impact:** Each concurrent upload holds its full file size in memory. 3 concurrent × 50MB = 150MB.
- **Fix:** Stream chunks directly to S3 via `put_object()` with content-length, or use multipart upload.

### C-5: Storage download — full file loaded into memory

- **File:** `backend/app/core/storage.py` (line ~135)
- **Issue:** `data = resp["Body"].read()` loads entire file into memory with no size validation before read.
- **Impact:** Large files served through this path consume equivalent RAM.
- **Fix:** Use `StreamingResponse` with chunked reads, or validate size before reading.

---

## HIGH

### H-1: Recommendations task — loads all user IDs at once

- **File:** `backend/app/tasks/recommendations.py` (line ~63)
- **Issue:** `SELECT id FROM users WHERE is_deleted = false` fetched into a single Python list.
- **Impact:** 100K+ users → 100K-element UUID list (~1.6MB minimum, more with Python object overhead).
- **Fix:** Use cursor-based iteration or `LIMIT/OFFSET` batching for the initial user fetch.

### H-2: DM cleanup — unbounded dict accumulation

- **File:** `backend/app/tasks/dm_cleanup.py` (line ~122)
- **Issue:**
  ```python
  conv_msgs: dict[object, list] = {}
  for msg in expired:
      conv_msgs.setdefault(cid, []).append(msg["id"])
  ```
  All expired messages collected into a dict before processing.
- **Impact:** 100K+ expired messages → unbounded dict growth.
- **Fix:** Process deletions in smaller per-conversation batches instead of accumulating all first.

### H-3: Avatar cache — TOCTOU race condition

- **File:** `backend/app/api/v1/endpoints/about.py` (line ~45)
- **Issue:** Global `_avatar_cache: OrderedDict` with 10MB cap, but check-then-download-then-recheck pattern allows concurrent requests to exceed the limit.
- **Impact:** Under high concurrency, cache can temporarily exceed 10MB.
- **Fix:** Use a lock around the check-and-insert, or use `asyncio.Lock`.

### H-4: Posts pagination — page parameter allows up to 10,000

- **File:** `backend/app/api/v1/endpoints/posts.py` (line ~76)
- **Issue:** `page: int = Query(1, ge=1, le=10000)` with `page_size` up to 100. Large offset forces PostgreSQL to scan all preceding rows.
- **Impact:** `page=10000&page_size=100` → PG must skip 999,900 rows before returning 100.
- **Fix:** Reduce max page to 1000, or migrate to keyset/cursor pagination.

### H-5: Site export — ZIP ≤ 100MB loaded entirely into memory

- **File:** `backend/app/tasks/site_export.py` (line ~543)
- **Issue:** For ZIP files ≤ 100MB, the entire file is loaded into memory at once for S3 upload.
- **Impact:** Single 100MB memory spike per export.
- **Fix:** Always use multipart upload regardless of size, or lower the threshold.

---

## MEDIUM

### M-1: WebSocket reconnect callbacks — unbounded array growth

- **File:** `frontend/src/composables/useWebSocket.ts` (line ~66)
- **Issue:** `_reconnectCallbacks` array grows with each call to `onReconnect()`. If components remount without cleanup, callbacks accumulate.
- **Fix:** Remove callbacks in `onUnmounted`, or use a `Set` with explicit deregistration.

### M-2: Image scan polling — no max retry limit

- **File:** `frontend/src/composables/usePostDetail.ts` (line ~642)
- **Issue:** `pollImageScanStatus()` retries every 5 seconds indefinitely while status is `pending`.
- **Fix:** Add `MAX_POLL_ATTEMPTS` (e.g., 20 retries = ~100s), then stop polling.

### M-3: localStorage drafts — no expiration or cleanup

- **Files:** `frontend/src/composables/useDraft.ts`, `useFormDraft.ts`, `useFormResponseDraft.ts`
- **Issue:** Drafts saved to localStorage without expiration timestamps. Multiple drafts accumulate indefinitely.
- **Fix:** Add timestamp-based cleanup (e.g., remove drafts > 48h old) and check quota before saving.

### M-4: Deep watchers on large form data

- **File:** `frontend/src/composables/useDraft.ts` (line ~159), `useFormResponseDraft.ts` (line ~85)
- **Issue:** `{ deep: true }` watch on entire draft/answers object. Forms with 500+ questions cause expensive reactivity tracking on every change.
- **Fix:** Use shallow watch with manual dirty detection, or watch specific metadata fields only.

### M-5: DM conversation list — LATERAL JOIN without cap

- **File:** `backend/app/repositories/dm_repo.py` (line ~102)
- **Issue:** Complex LATERAL JOIN with subqueries for last message and unread count across ALL conversations.
- **Impact:** User with 1000+ conversations → exponential query complexity.
- **Fix:** Add `LIMIT` to conversation listing and use keyset pagination.

### M-6: Dev Docker Compose — no log rotation

- **File:** `docker-compose.yml`
- **Issue:** Development compose has no `logging` configuration. Default `json-file` driver accumulates logs without rotation.
- **Fix:** Add `logging: { driver: json-file, options: { max-size: "50m", max-file: "3" } }` to long-running services.

---

## SAFE — Confirmed Mitigations Already in Place

| Area | Status | Details |
|------|--------|---------|
| Docker memory limits | ✅ | All services have explicit `memory` limits (nginx 256M, fastapi 3G, PG 2G, Redis 512M, Celery 768M) |
| Redis maxmemory | ✅ | Dev: 256MB `allkeys-lru`; Prod: 512MB `volatile-lru` |
| Celery worker memory | ✅ | `max-memory-per-child=256MB`, `prefetch_multiplier=1`, `task_reject_on_worker_lost=True` |
| nginx proxy buffering | ✅ | 256KB total buffer; `proxy_request_buffering off` on upload endpoints |
| PG work_mem | ✅ | 4MB × 50 connections = conservative 200MB max |
| WebSocket limits | ✅ | 64KB message size, 5 connections/user, 60 msg/min rate limit |
| Frontend DM store | ✅ | `MAX_MESSAGES = 200` with `_trimMessages()` |
| Frontend post list | ✅ | `MAX_ACCUMULATED_POSTS = 200` with `.slice()` |
| Upload concurrency | ✅ | `asyncio.Semaphore(3)` limits concurrent uploads |
| Thumbnail decompression | ✅ | `Image.MAX_IMAGE_PIXELS = 10_000_000` (10MP cap) |
| Request body size | ✅ | Per-endpoint limits (50MB albums, 10MB default) with middleware enforcement |
| Frontend notifications | ✅ | Capped at 10 items in store |
| Site export batching | ✅ | 1000-row DB batches, 64KB S3 chunks, 10GB hard cap |
| PG statement_timeout | ✅ | Dev: 30s, Prod: 60s |
| Production logging | ✅ | `json-file` with 50MB × 5 rotation per service |
| Production tmpfs | ✅ | `/tmp:100M` read-only filesystem |

---

## Recommended Fix Priority

### P0 — Immediate

1. **C-1** blacklist: on-demand `SISMEMBER` instead of full `SMEMBERS` per request
2. **C-4** album upload: stream to S3 instead of `chunks.append()`
3. **C-5** storage download: `StreamingResponse` with chunked reads

### P1 — High Priority

4. **C-2 / C-3** album/citation repo: add LIMIT + batched processing
5. **H-1** recommendations: cursor-based user iteration
6. **H-2** dm_cleanup: batch deletions per conversation
7. **H-4** posts: reduce max page to 1000 or use keyset pagination

### P2 — Medium Priority

8. **M-1** WebSocket reconnect callbacks: add `onUnmounted` cleanup
9. **M-2** scan polling: add `MAX_POLL_ATTEMPTS`
10. **M-3** drafts: add expiration cleanup
11. **M-5** DM conversations: add LIMIT to listing query
12. **M-6** dev compose: add log rotation config
