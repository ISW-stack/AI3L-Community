# Supplementary Backend Audit Report

> Date: 2026-03-16 | Scope: Areas not covered in initial audit | Total: 18 new issues

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **High** | 1 | N-B02 |
| **Medium** | 10 | N-B01, N-B03, N-B06, N-B08, N-B09, N-B10, N-B12, N-B13, N-B14, N-B17, N-B18 |
| **Low** | 4 | N-B04, N-B05, N-B07, N-B16 |
| **Very Low** | 2 | N-B11, N-B15 |

---

## High Severity

### N-B02: Event retry task loses events on worker crash

- **Location**: `backend/app/tasks/event_retry.py:38-39`
- **Description**: `LRANGE 0 -1` reads all failed events, then immediately `DELETE`s the entire Redis list before processing. If the worker crashes between DELETE and processing completion, all events are permanently lost. `max_retries=0` means Celery won't retry.
- **Impact**: Up to 5 minutes of accumulated failed events (audit logs, notifications) silently lost on crash.
- **Suggested fix**: Use `RPOPLPUSH` pattern or process with `LPOP` in a loop.

---

## Medium Severity

### N-B01: WebSocket `json.loads` without targeted error handling

- **Location**: `backend/app/api/v1/endpoints/ws.py:118`
- **Description**: Invalid JSON from client hits generic `except Exception`. Rate-limit budget is wasted since counter increments before parse. Client gets unclean disconnect.
- **Suggested fix**: Catch `json.JSONDecodeError` specifically; drop malformed messages or close with code 4003.

### N-B03: Recommendation task CROSS JOIN creates O(N²) rows

- **Location**: `backend/app/tasks/recommendations.py:126-227`
- **Description**: `CROSS JOIN active_users` produces N*(N-1) rows. 1000 users → ~1M pairs; 5000 → ~25M. Entire result fetched into Python memory.
- **Impact**: Excessive DB CPU, memory, connection time; may exceed `task_soft_time_limit`.
- **Suggested fix**: Add LIMIT, batch per-user, or skip if N exceeds threshold.

### N-B06: Thumbnail task sets `Image.MAX_IMAGE_PIXELS` globally per-invocation

- **Location**: `backend/app/tasks/thumbnail.py:74`
- **Description**: Sets process-wide Pillow global inside task function, not at module level. Inconsistent protection depending on task execution order.
- **Suggested fix**: Set at module level or in Celery worker init.

### N-B08: `warmup_block_cache` does not set TTL on Redis keys

- **Location**: `backend/app/core/blacklist.py:48-63`
- **Description**: Startup warmup uses `SADD` without `EXPIRE`. Compare with `get_blocked_user_ids` which sets 1h TTL. Warmup entries never expire; stale after unblock.
- **Impact**: Unblocked users still appear blocked until restart.
- **Suggested fix**: Add `pipe.expire(key, 3600)` in warmup loop.

### N-B09: `follow_user` TOCTOU race between block check and follow insert

- **Location**: `backend/app/services/social.py:156-168`
- **Description**: Block check + is_following check + insert happen without transaction or locking. Concurrent requests can bypass block restriction or create duplicate follows.
- **Suggested fix**: Wrap in `conn.transaction()`, add `FOR UPDATE` or advisory lock.

### N-B10: `update_profile` silently ignores `None` values — users cannot clear fields

- **Location**: `backend/app/repositories/user_repo.py:50-82`
- **Description**: `if value is not None: skip` means `None` (user wants to clear) is treated same as "not provided". Bio, affiliation, ORCID cannot be cleared once set.
- **Impact**: GDPR-relevant — users cannot remove personal information.
- **Suggested fix**: Use sentinel or empty string to distinguish "not provided" from "clear".

### N-B12: `cleanup_orphan_files` does not scan comment content for file references

- **Location**: `backend/app/tasks/cleanup.py:49-97`
- **Description**: Only scans `posts.content` and `forms.description` for editor file keys. Comments with embedded images are not scanned → those files flagged as orphans and deleted.
- **Impact**: Embedded images in comments break after 7 days.
- **Suggested fix**: Add third batch scanning `comments.content`.

### N-B13: Thumbnail download has no size limit

- **Location**: `backend/app/tasks/thumbnail.py:68-69`
- **Description**: `data = response.read()` is unbounded. A crafted image with small compressed size but huge pixel count passes editor upload limit but consumes arbitrary memory during download.
- **Suggested fix**: Use `response.read(MAX_SIZE)` with bound check.

### N-B14: Celery tasks create fresh event loops via `asyncio.run()`, corrupting connection pool

- **Location**: `backend/app/tasks/cleanup.py:31`, `form_autoclose.py:19`, `form_export.py:152`
- **Description**: Each task invocation creates/destroys an event loop. DB pool is module-global, so connections created under previous loop may reference closed loop → `RuntimeError: Event loop is closed`.
- **Impact**: Intermittent task failures in long-running workers.
- **Suggested fix**: Use single persistent event loop per worker, or reinitialize pool each invocation.

### N-B17: CSV export vulnerable to formula injection via option labels

- **Location**: `backend/app/tasks/form_export.py:106-124`
- **Description**: Multi-choice answers join option labels before sanitization. Form creator-controlled labels starting with `=`, `+`, `-`, `@` become formula injection in CSV.
- **Suggested fix**: Apply `_sanitize_csv_value` to each label before joining.

### N-B18: Idempotency middleware caches error responses (5xx, 429)

- **Location**: `backend/app/middleware/idempotency.py:80-96`
- **Description**: ALL JSON responses cached regardless of status code. Transient 500/429 errors become sticky for 5 minutes; client retries with same idempotency key get cached error.
- **Suggested fix**: Only cache 2xx and 4xx; exclude 5xx and 429.

---

## Low Severity

### N-B04: `view_sync` reconciliation runs without transactions

- **Location**: `backend/app/tasks/view_sync.py:152-166`
- **Description**: Four reconciliation functions run sequentially without wrapping transactions. UPDATE + zero-out are separate statements → crash between them leaves inconsistent counters.

### N-B05: SIG notification handler uses stale `total` in pagination

- **Location**: `backend/app/event_handlers.py:264-299`
- **Description**: `total` from first batch becomes stale if members change concurrently. Loop may terminate early.

### N-B07: `form_export` accesses record after connection release

- **Location**: `backend/app/tasks/form_export.py:47-59, 137`
- **Description**: `form["title"]` accessed after `async with pool.acquire()` exits. asyncpg Records retain values, but form could be deleted between the two pool acquisitions.

### N-B16: `block_user` count check outside transaction

- **Location**: `backend/app/services/social.py:233-248`
- **Description**: Block count checked before `conn.transaction()`. Two concurrent blocks can both pass, exceeding limit by 1.

---

## Very Low / Informational

### N-B11: Alembic migration `t1u2v3w4x5y6` destructive with no-op downgrade

- **Location**: `backend/alembic/versions/t1u2v3w4x5y6_clear_form_descriptions.py`
- **Description**: Clears all form descriptions; downgrade is `pass`. Silent no-op on rollback.

### N-B15: Pillow and other dependencies broadly pinned

- **Location**: `backend/requirements.txt:20`
- **Description**: `pillow>=10.0.0` allows known-vulnerable versions. Consider pinning to minimum safe versions.
