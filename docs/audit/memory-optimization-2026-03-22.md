# Memory Optimization Audit Report

**Date:** 2026-03-22
**Scope:** Full-stack analysis — Docker infrastructure, backend (Python/FastAPI), frontend (Vue 3/TypeScript), data layer (PostgreSQL/Redis)
**Objective:** Identify areas where alternative technical approaches can reduce system memory consumption while maintaining all current functionality

---

## Table of Contents

1. [System Memory Overview](#1-system-memory-overview)
2. [Finding MO-01: Docker Container Memory Over-Allocation](#mo-01)
3. [Finding MO-02: nginx Rate Limit Zone Over-Sizing](#mo-02)
4. [Finding MO-03: asyncpg Connection Pool Over-Provisioning](#mo-03)
5. [Finding MO-04: Redis Client Connection Pool Over-Provisioning](#mo-04)
6. [Finding MO-05: Reaction JSONB Full-Load-Modify-Write Pattern](#mo-05)
7. [Finding MO-06: Form Response Batching Returns Materialized List](#mo-06)
8. [Finding MO-07: DM Cleanup Tasks Unbounded Query](#mo-07)
9. [Finding MO-08: Post List Queries Load Full Content Column](#mo-08)
10. [Finding MO-09: Frontend DM Messages Unbounded Accumulation](#mo-09)
11. [Finding MO-10: Frontend Infinite Scroll Post Accumulation](#mo-10)
12. [Finding MO-11: FormHistory Undo/Redo Full-Snapshot Strategy](#mo-11)
13. [Finding MO-12: Vue Deep Watchers on Complex Objects](#mo-12)
14. [Finding MO-13: Avatar Presigned URL Regeneration Per Request](#mo-13)
15. [Finding MO-14: No Virtual Scrolling for Long Lists](#mo-14)
16. [Summary and Prioritization](#summary)

### Supplementary Findings (Second-Pass Deep Audit)

17. [Finding MO-15: ZIP Validation In-Memory Reconstruction](#mo-15)
18. [Finding MO-16: Thumbnail Generation PIL Decompression Peak](#mo-16)
19. [Finding MO-17: Concurrent File Upload Full-Buffer Memory Pressure](#mo-17)
20. [Finding MO-18: User Anonymization Unbounded DM Attachment Query](#mo-18)
21. [Finding MO-19: Idempotency Middleware Response Body Buffering](#mo-19)
22. [Finding MO-20: Form CSV Export Full StringIO Materialization](#mo-20)
23. [Finding MO-21: PDF Sanitization Triple Buffer](#mo-21)
24. [Finding MO-22: DM Store Data Persistence Across Route Navigation](#mo-22)
25. [Finding MO-23: Dead Code — find_all_responses() Unbounded Query](#mo-23)
26. [Updated Summary and Prioritization](#updated-summary)

---

## 1. System Memory Overview

### Current Docker Memory Allocation

| Service | Memory Limit | CPU Limit | Internal Memory Config |
|---------|-------------|-----------|------------------------|
| **fastapi** | 3G | 2.0 | asyncpg pool min=10/max=30; Redis pool max=50 |
| **postgres** | 2G | 2.0 | shared_buffers=256MB; work_mem=4MB; max_connections=100 |
| **celery** | 1536M | 1.0 | concurrency=2; max-memory-per-child=256000 (256MB) |
| **minio** | 1536M | 1.0 | (no internal config) |
| **redis** | 1G | 0.5 | maxmemory=256mb; allkeys-lru; appendonly=no |
| **nginx** | 256M | 0.5 | 4 rate-limit zones × 50m = 200MB shared memory |
| **celery-beat** | 256M | 0.25 | (scheduler only) |
| **datadog-agent** | 1G | 1.0 | (monitoring profile, optional) |

**Total (excluding Datadog):** ~9.5 GB

### Existing Memory Safeguards (Already in Place)

The system already implements several good memory management practices:

- Celery `worker_max_memory_per_child=256MB` with automatic process recycling
- Celery `worker_prefetch_multiplier=1` prevents task queue memory buildup
- Redis `allkeys-lru` eviction policy with 256MB hard cap
- Avatar LRU cache bounded at 50 entries / 10MB total / 1-hour TTL
- Post history queries capped at 50 entries (`POST_HISTORY_LIMIT`)
- All list endpoints paginated (default 20 items, max 100)
- File uploads validated with size limits (20MB editor, 50MB album/DM)
- File downloads streamed in 64KB chunks via async generator
- S3 orphan cleanup uses generator-based streaming (`_iter_editor_files()`)
- Cleanup tasks process records in 500-row batches
- Event bus failed events trimmed to 1,000 in Redis with 24-hour TTL
- WebSocket connections limited to 5 per user with cleanup on disconnect
- Notification store capped at 10 items in frontend
- i18n locale files lazy-loaded (except English fallback)
- All route components lazy-loaded via dynamic `() => import(...)` imports
- Blob URLs properly revoked on component unmount (PhotoUploadModal, useFormSubmit)

---

<a id="mo-01"></a>

## MO-01: Docker Container Memory Over-Allocation

**Severity:** LOW (no code change needed)
**Estimated Savings:** ~2–3 GB
**Complexity:** Trivial (config-only)
**Risk:** None

### Current State

**File:** `docker-compose.yml`

| Service | Current Limit | Actual Peak Usage (est.) | Gap |
|---------|--------------|-------------------------|-----|
| Redis | 1G | ~300MB (256MB internal cap + process overhead) | ~700MB wasted |
| Celery | 1536M | ~600MB (2 workers × 256MB + main process ~100MB) | ~900MB wasted |
| MinIO | 1536M | ~200–400MB (dev workload) | ~1.1GB wasted |
| Celery-Beat | 256M | ~50–80MB (scheduler-only process) | ~180MB wasted |

### Problem

Container memory limits are set conservatively high relative to the internal memory configurations that actually bound each service. Redis is limited to 256MB internally via `--maxmemory`, but its container allows 1G. Celery workers are individually capped at 256MB with `--max-memory-per-child`, and only 2 workers run concurrently (`--concurrency=2`), yet the container permits 1536M.

### Recommended Approach

Adjust `docker-compose.yml` deploy resource limits:

```yaml
redis:
  deploy:
    resources:
      limits:
        memory: 512M    # was: 1G — internal maxmemory is 256MB

celery:
  deploy:
    resources:
      limits:
        memory: 768M    # was: 1536M — 2 workers × 256MB + main ~100MB

minio:
  deploy:
    resources:
      limits:
        memory: 768M    # was: 1536M — adequate for dev/small-scale

celery-beat:
  deploy:
    resources:
      limits:
        memory: 128M    # was: 256M — scheduler only, ~50-80MB actual
```

### Impact

Total allocation drops from ~9.5GB to ~6.9GB. No functional change. All internal memory bounds remain unchanged.

---

<a id="mo-02"></a>

## MO-02: nginx Rate Limit Zone Over-Sizing

**Severity:** LOW (no code change needed)
**Estimated Savings:** ~160 MB shared memory
**Complexity:** Trivial (config-only)
**Risk:** None

### Current State

**File:** `nginx/nginx.conf:55-67`

```nginx
limit_conn_zone $binary_remote_addr zone=ws_conn:50m;          # line 55
limit_req_zone $binary_remote_addr zone=global:50m rate=20r/s;  # line 58
limit_req_zone $binary_remote_addr zone=auth:50m rate=5r/m;     # line 60
limit_req_zone $write_limit_key zone=write:50m rate=5r/m;       # line 67
```

4 zones × 50MB = **200MB** of shared memory allocated.

### Problem

Each `$binary_remote_addr` entry occupies ~64–128 bytes. A 50MB zone can track ~400,000–800,000 unique IP addresses. For an academic exchange platform, this is vastly over-provisioned. 10MB per zone still tracks ~80,000–160,000 unique IPs — more than sufficient.

### Recommended Approach

```nginx
limit_conn_zone $binary_remote_addr zone=ws_conn:10m;
limit_req_zone $binary_remote_addr zone=global:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
limit_req_zone $write_limit_key zone=write:10m rate=5r/m;
```

### Impact

Shared memory usage drops from 200MB to 40MB. Rate limiting functionality unchanged. If the platform scales to hundreds of thousands of concurrent IPs, zones can be increased incrementally.

---

<a id="mo-03"></a>

## MO-03: asyncpg Connection Pool Over-Provisioning

**Severity:** MEDIUM
**Estimated Savings:** ~80–120 MB
**Complexity:** Low (one-line config change)
**Risk:** Low — requires load testing to verify no contention under peak traffic

### Current State

**File:** `backend/app/core/database.py:11-15`

```python
_pool = await asyncpg.create_pool(
    dsn=dsn,
    min_size=10,   # line 13 — always keeps 10 idle connections
    max_size=30,   # line 14
    command_timeout=60,  # line 15
)
```

Each idle asyncpg connection consumes approximately 10–15MB of memory (statement cache, connection state, kernel buffers). With `min_size=10`, the system always holds 10 warm connections regardless of load.

### Problem

At `min_size=10`, the baseline memory footprint is ~100–150MB just for idle connections. For development and low-to-medium traffic deployments, most of these connections sit unused. The pool will dynamically scale up to `max_size` under load regardless of `min_size`.

Additionally, PostgreSQL's `max_connections=100` (docker-compose.yml line 94) is high relative to the pool's max of 30. Each PostgreSQL backend process holds ~5–10MB on the server side.

### Recommended Approach

```python
_pool = await asyncpg.create_pool(
    dsn=dsn,
    min_size=2,    # keep only 2 warm connections at idle
    max_size=20,   # scale up to 20 under load (was 30)
    command_timeout=60,
)
```

Paired with PostgreSQL:
```yaml
# docker-compose.yml
- "-c"
- "max_connections=${PG_MAX_CONNECTIONS:-50}"  # was: 100
```

### Impact

Idle memory drops from ~100–150MB to ~20–30MB (8 fewer idle connections × 10–15MB). Peak capacity is still 20 concurrent queries, which exceeds typical academic platform traffic. The `max_size=20` still leaves headroom for connection usage by Celery workers and the migration service.

---

<a id="mo-04"></a>

## MO-04: Redis Client Connection Pool Over-Provisioning

**Severity:** LOW
**Estimated Savings:** ~20–30 MB
**Complexity:** Trivial (one-line config change)
**Risk:** None

### Current State

**File:** `backend/app/core/redis.py:16`

```python
_redis = Redis.from_url(
    url,
    decode_responses=True,
    socket_keepalive=True,
    socket_timeout=10,
    socket_connect_timeout=5,
    retry_on_timeout=True,
    max_connections=50,  # line 16
)
```

### Problem

The FastAPI process maintains a pool of up to 50 connections to Redis. Typical Redis operations (session lookup, rate limit check, pub/sub, cache reads) are sub-millisecond. Even under peak load, 50 concurrent Redis connections from a single FastAPI process is unlikely. Each idle connection holds a socket buffer (~0.5–1MB).

### Recommended Approach

```python
max_connections=20,  # was: 50
```

### Impact

Reduces maximum socket buffer memory from ~50MB to ~20MB. Redis operations are non-blocking and fast, so 20 connections provides ample concurrency for a single FastAPI process.

---

<a id="mo-05"></a>

## MO-05: Reaction JSONB Full-Load-Modify-Write Pattern

**Severity:** HIGH (under high engagement)
**Estimated Savings:** O(n) → O(1) per reaction toggle
**Complexity:** Medium (SQL rewrite + testing)
**Risk:** Medium — requires thorough testing of JSONB edge cases

### Current State

**File:** `backend/app/repositories/reaction_helpers.py:20-80`

```python
async def toggle_reaction_jsonb(conn, table, row_id, user_id, reaction_type):
    row = await conn.fetchrow(queries["select"], row_uuid)      # line 37-40: load entire JSONB
    raw = row["reactions"]
    if isinstance(raw, str):
        reactions = json.loads(raw)                               # line 47: parse in Python
    elif raw:
        reactions = dict(raw)
    else:
        reactions = {}

    user_list: list[str] = reactions[reaction_type]               # line 56: modify in Python
    if user_id in user_list:
        user_list.remove(user_id)                                 # line 58
    else:
        user_list.append(user_id)                                 # line 60

    await conn.execute(queries["update"], json.dumps(reactions), row_uuid)  # line 65-68: serialize back
```

### Problem

Every reaction toggle (like/unlike) follows this cycle:
1. `SELECT reactions` — loads **entire** JSONB column into Python
2. `json.loads()` — parses into Python dict
3. Modify the list in memory
4. `json.dumps()` — serialize back to string
5. `UPDATE ... SET reactions = $1::jsonb` — write entire JSONB back

For a post with 10,000 likes, each toggle loads and parses a JSONB object containing 10,000 user IDs (~360KB), modifies one entry, then serializes and writes the entire 360KB back. Memory usage per toggle is O(n) where n = total reactions on the post.

### Recommended Approach

Use PostgreSQL's native JSONB operators to perform the toggle entirely in SQL, avoiding Python-side loading:

```sql
-- Add a reaction (append user to array)
UPDATE posts
SET reactions = jsonb_set(
    COALESCE(reactions, '{}'::jsonb),
    ARRAY[$2::text],
    COALESCE(reactions->$2, '[]'::jsonb) || to_jsonb($3::text),
    true
),
like_count = CASE WHEN $2 = 'like'
    THEN jsonb_array_length(COALESCE(reactions->$2, '[]'::jsonb)) + 1
    ELSE like_count END,
updated_at = NOW()
WHERE id = $1;

-- Remove a reaction (filter user from array)
UPDATE posts
SET reactions = jsonb_set(
    reactions,
    ARRAY[$2::text],
    (SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
     FROM jsonb_array_elements(reactions->$2) AS elem
     WHERE elem #>> '{}' != $3)
),
like_count = CASE WHEN $2 = 'like'
    THEN GREATEST(0, jsonb_array_length(COALESCE(reactions->$2, '[]'::jsonb)) - 1)
    ELSE like_count END,
updated_at = NOW()
WHERE id = $1
RETURNING reactions;
```

This requires a check-then-act pattern:
1. First query: check if user exists in the array (`SELECT reactions->$2 @> to_jsonb($3::text)`)
2. Second query: add or remove accordingly (within transaction, row already locked by `FOR UPDATE`)

### Impact

- Memory per toggle: O(1) instead of O(n)
- Network transfer: O(1) instead of O(n) (no JSONB round-trip)
- A post with 100,000 reactions no longer loads 3.6MB per toggle
- `like_count` synchronization is handled atomically in the same UPDATE

### Caveats

- The `RETURNING reactions` clause still transfers the full JSONB if the caller needs it. If the caller only needs confirmation, use `RETURNING like_count` instead.
- Edge case: if `reactions->$2` is NULL (reaction type doesn't exist yet), the add query must handle `jsonb_set` with `create_missing=true`.
- `comments` table uses the same pattern but typically has fewer reactions, so the impact is lower.

---

<a id="mo-06"></a>

## MO-06: Form Response Batching Returns Materialized List

**Severity:** HIGH (for large forms)
**Estimated Savings:** Prevents potential OOM on forms with 10K+ responses
**Complexity:** Medium (refactor to async generator + streaming aggregation)
**Risk:** Low

### Current State

**File:** `backend/app/repositories/form_repo.py:468-515`

```python
async def iter_responses_batched(form_id: uuid.UUID, batch_size: int = 500) -> list[dict]:
    results: list[dict] = []       # line 475 — accumulator
    last_id: uuid.UUID | None = None

    async with pool.acquire() as conn:
        while True:
            rows = await conn.fetch("""
                SELECT id, form_id, user_id, answers, created_at
                FROM form_responses WHERE form_id = $1 AND id > $2
                ORDER BY id LIMIT $3
            """, form_id, last_id, batch_size)
            if not rows:
                break
            for r in rows:
                d = dict(r)
                if isinstance(d.get("answers"), str):
                    d["answers"] = json.loads(d["answers"])
                results.append(d)    # line 511 — appends every batch to same list
            last_id = rows[-1]["id"]
    return results                   # line 515 — returns ALL responses at once
```

This function is called by form stats computation:

**File:** `backend/app/services/form.py:165`

```python
responses = await form_repo.iter_responses_batched(form_id)
```

### Problem

Although `iter_responses_batched` fetches from the database in 500-row batches (good for DB memory), it accumulates **all results** into a single `results` list before returning. For a form with 50,000 responses at ~1–5KB each, the final list occupies 50–250MB in Python process memory.

Additionally, `find_all_responses()` (lines 435–453) exists as an unbounded fallback with no LIMIT clause. It is currently only referenced in test code, but its continued existence poses a risk if accidentally used in production.

### Recommended Approach

**Step 1:** Convert `iter_responses_batched` to an async generator:

```python
async def iter_responses_batched(
    form_id: uuid.UUID, batch_size: int = 500
) -> AsyncIterator[dict]:
    """Yield responses one at a time, fetching from DB in batches."""
    last_id: uuid.UUID | None = None
    pool = get_pool()
    async with pool.acquire() as conn:
        while True:
            if last_id is None:
                rows = await conn.fetch(...)
            else:
                rows = await conn.fetch(...)
            if not rows:
                break
            for r in rows:
                d = dict(r)
                if isinstance(d.get("answers"), str):
                    d["answers"] = json.loads(d["answers"])
                yield d                     # yield instead of append
            last_id = rows[-1]["id"]
            if len(rows) < batch_size:
                break
```

**Step 2:** Refactor `get_form_stats()` to use streaming aggregation:

```python
async def get_form_stats(form_id: uuid.UUID) -> dict:
    stats = initialize_empty_stats()
    async for response in form_repo.iter_responses_batched(form_id):
        update_stats_incrementally(stats, response)  # O(1) memory per response
    return stats
```

**Step 3:** Remove or deprecate `find_all_responses()` to prevent accidental unbounded loading.

### Impact

Peak memory during stats computation drops from O(total_responses) to O(batch_size). A form with 100,000 responses uses ~2.5MB (one batch of 500) instead of ~500MB.

---

<a id="mo-07"></a>

## MO-07: DM Cleanup Tasks Unbounded Query

**Severity:** MEDIUM
**Estimated Savings:** Prevents potential OOM during cleanup
**Complexity:** Low (add LIMIT + loop)
**Risk:** None

### Current State

**File:** `backend/app/repositories/dm_repo.py:564-578`

```python
async def find_expired_file_messages(cutoff: object) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, conversation_id, attachment_key, attachment_size, sender_id
            FROM dm_messages
            WHERE attachment_expires_at IS NOT NULL
              AND attachment_expires_at < $1
              AND attachment_key IS NOT NULL
        """, cutoff)                         # NO LIMIT
        return [dict(r) for r in rows]
```

**File:** `backend/app/repositories/dm_repo.py:621-635`

```python
async def find_expired_text_messages(cutoff: object) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, conversation_id, content
            FROM dm_messages
            WHERE created_at < $1
              AND NOT is_recalled
              AND attachment_key IS NULL
        """, cutoff)                         # NO LIMIT
        return [dict(r) for r in rows]
```

**File:** `backend/app/tasks/dm_cleanup.py:19-64, 74-116`

Both cleanup tasks call these unbounded queries and process all results in a loop.

### Problem

If the system runs for a period without executing cleanup (e.g., Celery was down for a week), or if the DM system has high volume, the first cleanup run could fetch tens of thousands of expired messages into memory at once:

- **File cleanup:** Each row is small (~100 bytes), but S3 deletion per row means the list stays in memory for the full loop duration.
- **Text cleanup:** Each row includes the `content` column, so rows can be 1–5KB each. 50,000 expired messages = 50–250MB.

### Recommended Approach

Add `LIMIT 1000` to both queries and process in a loop:

```python
async def find_expired_file_messages(cutoff: object, limit: int = 1000) -> list[dict]:
    # ... same query ...
    """... AND attachment_key IS NOT NULL ORDER BY created_at ASC LIMIT $2""",
    cutoff, limit)
```

In the Celery task:

```python
while True:
    expired = await dm_repo.find_expired_file_messages(cutoff, limit=1000)
    if not expired:
        break
    for msg in expired:
        # process deletion
    # loop continues until no more expired messages
```

### Impact

Peak memory during cleanup is bounded to ~1,000 rows regardless of how many expired messages exist. Total cleanup time is unchanged (same number of DB queries and S3 calls, just batched).

---

<a id="mo-08"></a>

## MO-08: Post List Queries Load Full Content Column

**Severity:** MEDIUM
**Estimated Savings:** ~50–500 KB per list API call
**Complexity:** Medium (schema split + query variant)
**Risk:** Low — requires verifying no frontend list view depends on full content

### Current State

**File:** `backend/app/repositories/post_repo.py:10-20`

```python
_POST_SELECT = """
    SELECT p.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           c.name AS category_name,
           s.name AS sig_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN sigs s ON p.sig_id = s.id
"""
```

**File:** `backend/app/schemas/post.py:58`

```python
class PostResponse(BaseModel):
    content: str            # line 58 — full HTML content included
```

`PostResponse` is used for both detail and list responses. The `PostListResponse` (line 80) wraps `list[PostResponse]`, so every post in a list includes its full HTML content.

### Problem

`SELECT p.*` loads all columns from the `posts` table, including `content` (full HTML body). A typical post body is 5–50KB of HTML. For a list of 20 posts, this transfers 100KB–1MB of content data that the list view may not display (typically only title, author, date, like count are shown in cards).

This affects:
- Python memory (parsing and holding 20 full content strings)
- Network bandwidth (API → nginx → browser)
- Browser memory (storing full HTML in Pinia store)

### Recommended Approach

**Step 1:** Create a list-specific SELECT that excludes or truncates content:

```python
_POST_LIST_SELECT = """
    SELECT p.id, p.title, p.user_id, p.category_id, p.sig_id,
           p.is_pinned, p.is_locked, p.post_type, p.like_count,
           p.comment_count, p.answer_count, p.view_count,
           p.reactions, p.keywords, p.created_at, p.updated_at,
           LEFT(p.content, 300) AS content_preview,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           c.name AS category_name,
           s.name AS sig_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN sigs s ON p.sig_id = s.id
"""
```

**Step 2:** Create a `PostListItem` schema with `content_preview: str` instead of `content: str`.

**Step 3:** Use `_POST_SELECT` (full) only in `find_by_id()` and `find_by_id_with_user()` (detail endpoints). Use `_POST_LIST_SELECT` in `find_many()`, `search()`, and `find_trending()`.

### Impact

List API response size drops by 80–90%. Backend memory per list request drops proportionally. Frontend store holds only 300-character previews instead of full HTML bodies.

### Caveats

- Verify that no frontend component renders full HTML from list data. PostCard components typically display a text excerpt, not full rendered HTML.
- Search highlighting may need full content — if so, search can continue using `_POST_SELECT` or perform highlighting server-side on the preview.

---

<a id="mo-09"></a>

## MO-09: Frontend DM Messages Unbounded Accumulation

**Severity:** HIGH
**Estimated Savings:** Prevents multi-MB memory growth in long sessions
**Complexity:** Medium (add windowing logic to store)
**Risk:** Low

### Current State

**File:** `frontend/src/stores/dm.ts`

```typescript
const messages = ref<DMMessage[]>([])                      // line 12 — no cap

// Pagination loads (line 62-69):
if (page === 1) {
  messages.value = chronological
} else {
  const existingIds = new Set(messages.value.map((m) => m.id))
  const newMessages = chronological.filter((m) => !existingIds.has(m.id))
  messages.value = [...newMessages, ...messages.value]     // line 68 — unbounded prepend
}

// WebSocket additions (lines 104, 122, 142):
messages.value.push(message)                               // unbounded append
```

### Problem

The `messages` array grows without bound in two scenarios:

1. **Pagination:** User scrolls up to load older messages. Each page adds 30 messages. After loading 20 pages, 600 messages are held in memory.
2. **WebSocket:** New messages are pushed via `addFromWebSocket()`. In an active conversation, messages accumulate indefinitely.

Each `DMMessage` object contains `content` (string), `attachment_url`, `attachment_name`, sender info, and timestamps. At ~0.5–2KB per message, 1,000 messages = 0.5–2MB. The `Set` and spread operations on line 66–68 also create temporary copies, doubling peak memory during pagination.

### Recommended Approach

Add a message window with configurable upper bound:

```typescript
const MAX_MESSAGES = 500

// After pagination prepend:
if (messages.value.length > MAX_MESSAGES) {
  messages.value = messages.value.slice(0, MAX_MESSAGES)
  // Optionally set a flag: hasNewerTrimmed = true
}

// After WebSocket push:
if (messages.value.length > MAX_MESSAGES) {
  messages.value = messages.value.slice(-MAX_MESSAGES)
  // Optionally set a flag: hasOlderTrimmed = true
}
```

For optimal UX, pair with virtual scrolling (see MO-14).

### Impact

Message array is bounded at ~500 messages (~250KB–1MB max). Older or newer messages outside the window are re-fetched on demand via pagination.

---

<a id="mo-10"></a>

## MO-10: Frontend Infinite Scroll Post Accumulation

**Severity:** MEDIUM
**Estimated Savings:** Prevents multi-MB memory growth during extended browsing
**Complexity:** Low (add max cap)
**Risk:** Low

### Current State

**File:** `frontend/src/composables/usePostList.ts:185, 247`

```typescript
posts.value = [...posts.value, ...data.posts]   // line 185 — loadMore()
posts.value = [...posts.value, ...data.posts]   // line 247 — searchMore()
```

### Problem

As the user scrolls through the forum, every loaded page's posts are appended to the array. With 20 posts per page and 50 pages scrolled, 1,000 posts accumulate. Each post includes full content (see MO-08), metadata, reactions JSONB, and keywords. At ~5–50KB per post (with content), 1,000 posts = 5–50MB.

The spread operator `[...posts.value, ...data.posts]` also creates a full copy on each append, causing a temporary peak of 2× the array size.

### Recommended Approach

**Option A:** Add a maximum accumulation cap:

```typescript
const MAX_ACCUMULATED_POSTS = 200

// After append:
if (posts.value.length > MAX_ACCUMULATED_POSTS) {
  posts.value = posts.value.slice(-MAX_ACCUMULATED_POSTS)
}
```

**Option B (stronger):** Combine with MO-08 (exclude content from list responses) to reduce per-post memory. With only metadata (~500 bytes per post), 1,000 posts would be ~500KB, which is acceptable.

### Impact

With Option A alone, post array is bounded at 200 posts. Combined with MO-08, even 500 posts would use only ~250KB. The `hasMore` flag and cursor pagination allow re-loading if the user scrolls back.

---

<a id="mo-11"></a>

## MO-11: FormHistory Undo/Redo Full-Snapshot Strategy

**Severity:** LOW
**Estimated Savings:** ~5–8 MB per form editing session
**Complexity:** High (differential history algorithm)
**Risk:** Medium — delta-based undo/redo is more error-prone

### Current State

**File:** `frontend/src/composables/useFormHistory.ts:15-43`

```typescript
const MAX_HISTORY = 50                                          // line 13

function deepCloneQuestions(questions: Question[]): Question[] {
  return JSON.parse(JSON.stringify(questions))                  // line 16 — redundant clone
}

function pushState(questions: Question[]): void {
  const snapshot = JSON.stringify(deepCloneQuestions(questions)) // line 31 — clone THEN stringify
  // ...
  undoStack.value.push(snapshot)                                // line 36
  if (undoStack.value.length > MAX_HISTORY) {
    undoStack.value.shift()                                     // line 38
  }
}
```

### Problem

1. **Double serialization:** `deepCloneQuestions()` calls `JSON.parse(JSON.stringify(questions))` to create a clone, then `pushState()` immediately calls `JSON.stringify()` on that clone. This means every push performs **two** `JSON.stringify()` calls and one `JSON.parse()` — the intermediate clone is unnecessary.

2. **Full snapshots:** Each undo state is a complete JSON string of all form questions. A form with 50 questions and options can be 50–200KB per snapshot. With `MAX_HISTORY = 50`, peak storage is 2.5–10MB in undo+redo stacks.

### Recommended Approach

**Quick fix (eliminate double serialization):**

```typescript
function pushState(questions: Question[]): void {
  const snapshot = JSON.stringify(questions)   // direct stringify — no intermediate clone needed
  // ...
}
```

This alone halves the CPU cost per push and eliminates the transient clone.

**Deeper fix (differential history):**

Replace full snapshots with JSON Patch (RFC 6902) deltas:

```typescript
import { compare as jsonPatchCompare, applyPatch } from 'fast-json-patch'

function pushState(questions: Question[]): void {
  const current = questions  // reference, not clone
  if (undoStack.value.length > 0) {
    const patch = jsonPatchCompare(lastState, current)
    if (patch.length === 0) return  // no change
    undoStack.value.push(patch)     // store only the delta (~100 bytes typical)
  }
  lastState = JSON.parse(JSON.stringify(current))  // snapshot for next comparison
}
```

Each delta is typically 50–500 bytes (a single field change), versus 50–200KB for a full snapshot. 50 deltas ≈ 2.5–25KB instead of 2.5–10MB.

**Moderate fix (reduce MAX_HISTORY):**

If differential history is too complex, simply reducing `MAX_HISTORY` from 50 to 20 cuts peak memory by 60% with minimal UX impact (20 undo levels is generous for form editing).

### Impact

- Quick fix: Halves CPU per push, eliminates transient memory allocation
- Differential: Reduces undo/redo memory from ~5–10MB to ~5–25KB
- MAX_HISTORY reduction: Proportional memory reduction

---

<a id="mo-12"></a>

## MO-12: Vue Deep Watchers on Complex Objects

**Severity:** LOW
**Estimated Savings:** CPU reduction (indirect memory savings under load)
**Complexity:** Medium (refactor to explicit change tracking)
**Risk:** Low

### Current State

Three composables use `{ deep: true }` watchers:

| File | Line | Watched Object | Purpose |
|------|------|---------------|---------|
| `src/composables/useDraft.ts` | 149 | `data` (draft content object) | Auto-save debouncing |
| `src/composables/useFormResponseDraft.ts` | 84 | `answers` (form answers object) | Auto-save debouncing |
| `src/composables/usePostDetail.ts` | 668 | `imageScanStatuses` (Record) | Malicious image overlay |

### Problem

Vue's `{ deep: true }` watcher performs recursive traversal of the entire reactive object tree on every potential change. For a form with 50+ questions, each containing options arrays, the watcher traverses hundreds of nested properties. This is CPU-intensive and creates garbage collection pressure from the traversal's temporary comparison objects.

### Recommended Approach

Replace deep watchers with explicit change notification:

```typescript
// Instead of:
watch(data, () => { saveDraft() }, { deep: true })

// Use:
function onFieldChange() {
  isDirty.value = true
  debouncedSaveDraft()
}

// Call onFieldChange() from each input's @input/@change handler
```

For `imageScanStatuses`, since it's a Record that changes infrequently (only during scan polling), the deep watcher overhead is minimal. This one can remain as-is.

### Impact

Eliminates recursive traversal on every keystroke during form editing. Reduces GC pressure from watcher internals. Most beneficial for large forms with many fields.

---

<a id="mo-13"></a>

## MO-13: Avatar Presigned URL Regeneration Per Request

**Severity:** LOW
**Estimated Savings:** CPU/thread-pool reduction (indirect memory savings)
**Complexity:** Low (add Redis cache)
**Risk:** None

### Current State

**File:** `backend/app/converters/user_converter.py:4-36`

```python
def resolve_avatar_url(avatar_url: str | None) -> str | None:
    if not avatar_url:
        return None
    return generate_presigned_url(avatar_url, expires_in=3600)   # fresh URL every call

async def async_resolve_avatar_url(avatar_url: str | None) -> str | None:
    if not avatar_url:
        return None
    return await run_in_threadpool(
        generate_presigned_url, avatar_url, expires_in=3600      # fresh URL every call
    )
```

Every user serialization calls `resolve_avatar_url()` or `async_resolve_avatar_url()`. A list endpoint returning 20 users generates 20 presigned URLs — each involving a boto3/S3 call (run in thread executor).

### Problem

Presigned URLs for the same storage key are functionally identical within their validity window. Regenerating them on every request wastes CPU cycles and thread-pool slots. Under concurrent requests listing users, this can saturate the thread executor.

### Recommended Approach

Cache presigned URLs in Redis with a TTL shorter than the URL's validity:

```python
async def async_resolve_avatar_url(avatar_url: str | None) -> str | None:
    if not avatar_url:
        return None
    redis = get_redis()
    cache_key = f"presigned:{avatar_url}"
    cached = await redis.get(cache_key)
    if cached:
        return cached
    url = await run_in_threadpool(generate_presigned_url, avatar_url, expires_in=3600)
    if url:
        await redis.setex(cache_key, 2700, url)  # cache for 45 min (75% of 1h validity)
    return url
```

### Impact

Repeat requests for the same avatar (common in list views, comments, notifications) hit Redis instead of boto3. Reduces thread-pool contention and CPU usage. Memory impact on Redis is negligible (~100 bytes per cached URL × number of active users).

---

<a id="mo-14"></a>

## MO-14: No Virtual Scrolling for Long Lists

**Severity:** MEDIUM
**Estimated Savings:** DOM node memory reduction for long lists
**Complexity:** Medium (integrate virtual scroll library)
**Risk:** Low

### Current State

The frontend renders all list items as real DOM nodes:

| Component | Data Source | Max Items |
|-----------|-----------|-----------|
| MessageThread (DM) | `dm.messages` | Unbounded (see MO-09) |
| HomeView / Forum | `usePostList.posts` | Unbounded (see MO-10) |
| ConversationList (DM) | `dm.conversations` | Up to 30 per page (paginated) |
| Notification dropdown | `notifications.items` | Capped at 10 |

### Problem

When `messages` or `posts` arrays grow large (500+ items), the browser renders all items as DOM nodes. Each rendered component (PostCard, message bubble) contains multiple child elements. A PostCard with avatar, title, metadata, reactions = ~20–30 DOM nodes. 500 PostCards = 10,000–15,000 DOM nodes, consuming 5–15MB of browser memory and causing layout/paint performance degradation.

### Recommended Approach

Integrate `@tanstack/vue-virtual` or `vue-virtual-scroller` for the two heaviest lists:

1. **MessageThread:** Wrap message list in a virtual scroller. Only render messages in the visible viewport + small overscan buffer (~5 items above/below).

2. **HomeView post list:** Wrap PostCard list in a virtual scroller. Each PostCard has a predictable height (or use dynamic height measurement).

```typescript
import { useVirtualizer } from '@tanstack/vue-virtual'

const virtualizer = useVirtualizer({
  count: messages.value.length,
  getScrollElement: () => scrollContainerRef.value,
  estimateSize: () => 80,  // estimated message height in px
  overscan: 5,
})
```

### Impact

With virtual scrolling, only ~20–30 items are rendered at any time regardless of total list size. DOM node count stays constant. Combined with MO-09 and MO-10 (data array caps), both data and DOM memory are bounded.

### Caveats

- Virtual scrolling requires a fixed-height scroll container. The current layout must be adjusted to provide explicit container heights.
- Dynamic-height items (variable-length messages, multi-line post titles) require the virtualizer's dynamic measurement mode, which adds slight complexity.
- ConversationList and Notification dropdown are small enough that virtual scrolling is unnecessary.

---

<a id="summary"></a>

## Summary and Prioritization

### By Estimated Impact

| Priority | Finding | Type | Est. Savings | Complexity | Risk |
|----------|---------|------|-------------|-----------|------|
| **P0** | MO-01: Docker container limits | Config | ~2–3 GB | Trivial | None |
| **P0** | MO-02: nginx zone sizes | Config | ~160 MB | Trivial | None |
| **P1** | MO-03: asyncpg pool min_size | Config | ~80–120 MB | Low | Low |
| **P1** | MO-07: DM cleanup LIMIT | Code | Prevents OOM | Low | None |
| **P1** | MO-06: Form responses generator | Code | Prevents OOM | Medium | Low |
| **P2** | MO-05: Reaction JSONB in-DB ops | Code | O(n)→O(1)/toggle | Medium | Medium |
| **P2** | MO-08: Post list exclude content | Code | ~50–500 KB/req | Medium | Low |
| **P2** | MO-09: DM messages cap | Code | ~1–5 MB/session | Medium | Low |
| **P2** | MO-10: Post accumulation cap | Code | ~5–50 MB/session | Low | Low |
| **P2** | MO-14: Virtual scrolling | Code | DOM memory bound | Medium | Low |
| **P3** | MO-04: Redis pool size | Config | ~20–30 MB | Trivial | None |
| **P3** | MO-11: FormHistory snapshots | Code | ~5–8 MB/session | High | Medium |
| **P3** | MO-12: Deep watchers | Code | CPU reduction | Medium | Low |
| **P3** | MO-13: Avatar URL cache | Code | CPU reduction | Low | None |

### By Category

**Pure configuration (no code changes):**
MO-01, MO-02, MO-03, MO-04 — Total savings: ~2.5–3.5 GB

**Backend code changes:**
MO-05, MO-06, MO-07, MO-08, MO-13 — Prevents OOM + reduces per-request memory

**Frontend code changes:**
MO-09, MO-10, MO-11, MO-12, MO-14 — Bounds client-side memory growth

### Recommended Implementation Order

1. **Phase 1 (Config only):** MO-01 + MO-02 + MO-03 + MO-04 — immediate savings, zero risk
2. **Phase 2 (Safety nets):** MO-07 + MO-06 — prevent potential OOM in cleanup and stats
3. **Phase 3 (Per-request optimization):** MO-08 + MO-09 + MO-10 — reduce steady-state memory
4. **Phase 4 (Scaling):** MO-05 + MO-14 — prepare for high-engagement scenarios
5. **Phase 5 (Polish):** MO-11 + MO-12 + MO-13 — diminishing returns, do if time permits

---

## Supplementary Findings (Second-Pass Deep Audit)

The following findings were identified during a second-pass deep audit targeting binary data processing, concurrent upload scenarios, cascade operations, middleware buffering, and frontend lifecycle patterns. These items were not covered in the initial 14 findings.

---

<a id="mo-15"></a>

## MO-15: ZIP Validation In-Memory Reconstruction (Memory Bomb Risk)

**Severity:** CRITICAL
**Peak Memory:** ~1.3 GB worst case (single request)
**Complexity:** High (streaming ZIP rewrite)
**Risk:** HIGH — can cause OOM kill of the FastAPI container under normal usage

### Current State

**File:** `backend/app/core/zip_validation.py`

**Constants (lines 18–24):**

```python
MAX_COMPRESSION_RATIO = 100          # line 18
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GB — line 21
MAX_ZIP_ENTRIES = 1000               # line 24
```

**Flow (lines 128–246):**

1. **Line 142:** `zipfile.is_zipfile(BytesIO(data))` — wraps raw bytes in BytesIO (no copy, but holds reference)
2. **Line 146:** `zf = zipfile.ZipFile(BytesIO(data), "r")` — another BytesIO wrapper + ZIP central directory parsed in memory
3. **Lines 165–216:** Iterates entries to validate (compression ratio, extensions, path traversal) — metadata only, low memory
4. **Lines 229–237:** If Mac junk found, **reconstructs the entire ZIP in memory:**

```python
buf = BytesIO()                                              # line 230
with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
    for info in entries:
        if info.filename in mac_junk_entries:
            continue
        out_zf.writestr(info, zf.read(info.filename))        # line 236 — reads each entry fully
clean_data = buf.getvalue()                                  # line 237 — materializes entire ZIP
```

**Caller (album ZIP upload):**

**File:** `backend/app/api/v1/endpoints/albums.py:313-320`

```python
chunks: list[bytes] = []
total = 0
while chunk := await file.read(8192):                        # line 315
    total += len(chunk)
    if total > ALBUM_MAX_ZIP_SIZE_BYTES:                      # line 317 — 100MB constant
        raise AppError(...)
    chunks.append(chunk)
file_data = b"".join(chunks)                                  # line 320 — full ZIP in memory
```

Note: the endpoint uses `ALBUM_MAX_ZIP_SIZE_BYTES` (100MB from constants.py), but `MAX_ALBUM_UPLOAD_BYTES` is 50MB. The effective limit depends on which constant is referenced — currently the endpoint uses the 100MB constant at line 317.

### Worst-Case Peak Memory Calculation

During the Mac junk stripping reconstruction phase, the following coexist in memory:

| Buffer | Size | Lives Until |
|--------|------|------------|
| `file_data` (original raw bytes from endpoint) | up to 100 MB | end of request |
| `BytesIO(data)` inside `zf` (ZIP reader) | reference to same bytes | `zf.__exit__` |
| `zf.read(info.filename)` per entry | up to 1 GB uncompressed total | each `writestr` call |
| `buf` (reconstructed ZIP BytesIO) | ~100 MB (recompressed) | `buf.getvalue()` |
| `clean_data = buf.getvalue()` | ~100 MB (bytes copy) | returned to caller |

**Peak during reconstruction:** `file_data` (100MB) + decompressed entry being copied (variable, up to entry size) + `buf` accumulating (up to 100MB) + `clean_data` (100MB)

**Realistic worst case:** ~300–400 MB for a 100MB ZIP with Mac junk

**Theoretical maximum** (if entry decompression hits the 1GB uncompressed limit): could spike to ~1.3 GB momentarily during `zf.read()` of a highly-compressed entry, though this is bounded by `MAX_COMPRESSION_RATIO = 100`.

### Why This Is Critical

- A single album ZIP upload request can consume 300–400 MB of the FastAPI container's 3 GB limit
- Multiple concurrent uploads (e.g., 5 users uploading albums simultaneously) could consume 1.5–2 GB
- The Celery worker also processes thumbnails from these images, adding further memory pressure
- The `MAX_UNCOMPRESSED_BYTES = 1 GB` limit allows decompressed content that exceeds the FastAPI container's memory limit

### Recommended Approach

**Option A (Simplest — reduce limits):**

```python
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB instead of 1 GB
```

Combined with lowering the endpoint limit to match `MAX_ALBUM_UPLOAD_BYTES` (50 MB), the realistic peak drops to ~150 MB per request.

**Option B (Streaming reconstruction via temp file):**

```python
import tempfile

if strip_mac_junk and mac_junk_entries:
    with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024) as tmp:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
            for info in entries:
                if info.filename in mac_junk_entries:
                    continue
                out_zf.writestr(info, zf.read(info.filename))
        tmp.seek(0)
        clean_data = tmp.read()
```

`SpooledTemporaryFile` keeps data in memory up to 10 MB, then spills to disk. This bounds peak memory to ~10 MB for the output buffer regardless of ZIP size.

**Option C (Skip reconstruction entirely):**

Instead of rebuilding the ZIP without Mac junk, simply skip Mac junk entries during extraction (in the album upload service). This eliminates the reconstruction phase entirely:

```python
# In album service, when processing ZIP entries:
for info in zf.infolist():
    if _is_mac_junk(info.filename):
        continue
    # process only non-junk entries
```

This is the lowest-memory approach but requires the caller to handle junk filtering.

---

<a id="mo-16"></a>

## MO-16: Thumbnail Generation PIL Decompression Peak

**Severity:** HIGH
**Peak Memory:** ~252 MB per thumbnail task
**Complexity:** Low (enforce max dimensions)
**Risk:** Medium — runs in Celery worker with 256 MB per-child limit; can trigger worker recycling

### Current State

**File:** `backend/app/tasks/thumbnail.py`

```python
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024                          # line 13 — 50 MB
Image.MAX_IMAGE_PIXELS = 50_000_000                            # line 54 — 50 megapixels

data = response.read(MAX_DOWNLOAD_SIZE + 1)                    # line 70 — full file in memory
img = Image.open(io.BytesIO(data))                             # line 83 — decompress to bitmap
img = ImageOps.exif_transpose(img)                             # line 84 — may create copy
img.thumbnail(ALBUM_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)  # line 85 — resize in-place
if img.mode in ("RGBA", "LA", "P"):
    img = img.convert("RGB")                                   # line 89 — new image buffer
buf = io.BytesIO()
img.save(buf, format="WEBP", quality=ALBUM_THUMBNAIL_QUALITY)  # line 93 — encode to output
```

### Peak Memory Calculation

| Buffer | Size | Notes |
|--------|------|-------|
| `data` (raw compressed file) | up to 50 MB | JPEG/PNG compressed |
| `img` after `Image.open()` | up to 200 MB | 50MP × 4 bytes (RGBA) = 200 MB bitmap |
| `img` after `exif_transpose()` | up to 200 MB | may create new image (PIL implementation detail) |
| `img` after `.thumbnail()` | ~480 KB | 400×400 × 3 bytes (RGB) |
| `buf` (WebP output) | ~50–200 KB | compressed thumbnail |

**Peak coexistence:** `data` (50 MB) + pre-resize bitmap (200 MB) + post-transpose copy (200 MB, briefly) = **up to 450 MB**

In practice, `exif_transpose()` creates a copy only if rotation is needed, and PIL may release the pre-resize buffer during `.thumbnail()`. Realistic peak: **~252 MB** (download buffer + one decompressed bitmap).

### Why This Matters

The Celery worker has `--max-memory-per-child=256000` (256 MB). A single thumbnail generation for a 50 MP image will:

1. Exceed the per-child memory limit
2. Trigger worker recycling (`SIGTERM` → restart)
3. The task may be retried (`max_retries=2`), hitting the same limit again
4. After 3 failures, the task is permanently failed

This is not a crash bug — Celery handles it gracefully — but it means large images silently fail to generate thumbnails.

### Recommended Approach

**Option A (Enforce max dimensions before full decompression):**

```python
# After Image.open(), check dimensions before loading pixel data
img = Image.open(io.BytesIO(data))
width, height = img.size
MAX_DIMENSION = 8000  # 8000×8000 = 64 MP max; fits in ~256 MB RGBA
if width > MAX_DIMENSION or height > MAX_DIMENSION:
    # Use PIL's draft mode to load at reduced resolution
    img.draft("RGB", (ALBUM_THUMBNAIL_SIZE[0] * 2, ALBUM_THUMBNAIL_SIZE[1] * 2))
    img.load()
```

PIL's `draft()` mode for JPEG files can load at 1/2, 1/4, or 1/8 resolution without decompressing the full image. For a 8000×6000 JPEG, loading at 1/4 resolution (2000×1500) uses only ~12 MB instead of 192 MB.

**Option B (Lower the pixel limit):**

```python
Image.MAX_IMAGE_PIXELS = 20_000_000  # 20 MP instead of 50 MP
```

A 20 MP RGBA image = 80 MB, which fits comfortably within the 256 MB worker limit along with the download buffer.

**Option C (Release download buffer before decompression):**

```python
data = response.read(MAX_DOWNLOAD_SIZE + 1)
# ...size check...
img = Image.open(io.BytesIO(data))
del data  # release 50 MB download buffer before PIL decompresses
img.load()  # force decompression now (after data is freed)
```

This reduces peak from ~252 MB to ~200 MB (bitmap only). Combined with Option B, peak drops to ~80 MB.

---

<a id="mo-17"></a>

## MO-17: Concurrent File Upload Full-Buffer Memory Pressure

**Severity:** HIGH (under concurrent load)
**Peak Memory:** Up to 500+ MB site-wide from concurrent uploads
**Complexity:** Medium (streaming upload pipeline)
**Risk:** Medium

### Current State

Three upload paths read the entire file into memory before processing:

| Upload Path | File | Line | Max Size | Read Method |
|-------------|------|------|----------|-------------|
| **Editor files** | `endpoints/files.py` | 45 | 20 MB | `await file.read(MAX + 1)` |
| **DM attachments** | `endpoints/dm.py` | 147 | 50 MB | `await file.read(MAX + 1)` |
| **Album ZIP** | `endpoints/albums.py` | 315–320 | 100 MB | Chunked read → `b"".join(chunks)` |
| **Album photo** | `services/album.py` | (caller) | 10 MB | Passed as `file_data: bytes` |
| **Album cover** | `services/album.py` | (caller) | 5 MB | Passed as `file_data: bytes` |

### Problem

Each concurrent upload holds its full file data in Python process memory until the MinIO upload completes and the response is sent. Under concurrent load:

| Scenario | Memory |
|----------|--------|
| 5 concurrent editor uploads × 20 MB | 100 MB |
| 3 concurrent DM attachments × 50 MB | 150 MB |
| 2 concurrent album ZIPs × 100 MB | 200 MB |
| All combined | **450 MB** |

This is on top of the FastAPI process baseline (~200–250 MB), bringing total to ~700 MB. With ZIP reconstruction (MO-15), a single album upload can push this to 1+ GB.

Rate limits mitigate but don't eliminate this:
- Editor: per-user rate limit (but multiple users upload simultaneously)
- DM: `RATE_LIMIT_DM_SEND` (30/60s per user)
- Albums: `RATE_LIMIT_ALBUM_UPLOAD` (per user)

### Recommended Approach

**Option A (Streaming to MinIO via multipart upload):**

For files over 10 MB, stream directly to MinIO using S3's multipart upload API instead of buffering in Python:

```python
# Pseudocode — stream upload
async def stream_upload_to_minio(file: UploadFile, key: str, max_size: int):
    upload_id = s3.create_multipart_upload(Bucket=bucket, Key=key)
    part_number = 1
    total = 0
    parts = []
    while chunk := await file.read(5 * 1024 * 1024):  # 5 MB parts
        total += len(chunk)
        if total > max_size:
            s3.abort_multipart_upload(...)
            raise AppError(...)
        resp = s3.upload_part(Body=chunk, PartNumber=part_number, UploadId=upload_id, ...)
        parts.append({"ETag": resp["ETag"], "PartNumber": part_number})
        part_number += 1
    s3.complete_multipart_upload(...)
```

This caps per-upload memory at 5 MB regardless of file size. However, it requires computing the file hash incrementally (for VirusTotal) and performing validation after upload rather than before.

**Option B (Simpler — enforce stricter concurrent upload limits):**

Add a global (not per-user) semaphore for large uploads:

```python
_upload_semaphore = asyncio.Semaphore(3)  # max 3 concurrent large uploads

async def upload_file_endpoint(...):
    async with _upload_semaphore:
        file_data = await file.read(MAX_SIZE + 1)
        # ...process...
```

This caps peak upload memory at 3 × max_file_size. Simple, no architectural change required.

**Option C (Temp file spill for large uploads):**

Use `SpooledTemporaryFile` to keep small files in memory and spill large ones to disk:

```python
import tempfile

spooled = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024)  # 5 MB threshold
while chunk := await file.read(8192):
    spooled.write(chunk)
spooled.seek(0)
# For validation: read from spooled (may be on disk for large files)
# For upload: pass spooled file object to boto3
```

### Impact

Option A eliminates upload buffering entirely. Option B is simplest and caps peak at ~300 MB (3 × 100 MB). Option C adds disk I/O but bounds memory at 5 MB per upload.

---

<a id="mo-18"></a>

## MO-18: User Anonymization Unbounded DM Attachment Query

**Severity:** MEDIUM
**Peak Memory:** Unbounded (proportional to user's total DM attachments)
**Complexity:** Low (add LIMIT + batch loop)
**Risk:** None

### Current State

**File:** `backend/app/services/user.py:429-435`

```python
# H-06: Collect DM attachment keys before deleting messages
dm_rows = await conn.fetch(
    "SELECT attachment_key FROM dm_messages "
    "WHERE sender_id = $1 AND attachment_key IS NOT NULL",
    user_id,
)                                                      # NO LIMIT
dm_attachment_keys = [r["attachment_key"] for r in dm_rows]
```

This query runs inside a transaction during `anonymize_user()` (GDPR account deletion). It loads **all** DM attachment keys for the user at once.

**Post-transaction file deletion (lines 462–479):**

```python
files_to_delete: list[str] = []
if avatar_key:
    files_to_delete.append(avatar_key)
files_to_delete.extend(dm_attachment_keys)                 # all keys in one list

for key in files_to_delete:
    await async_delete_file(key)                           # sequential S3 deletes
```

### Problem

If a user has sent 10,000 DM attachments over time, this query returns 10,000 rows into memory. Each row is small (~100 bytes for a storage key string), so 10K rows ≈ 1 MB — not catastrophic, but:

1. The list persists for the entire duration of the sequential S3 deletion loop (potentially minutes)
2. If attachment keys are long paths, memory could be higher
3. The pattern violates the project's general principle of bounded queries

### Recommended Approach

Batch the attachment collection and deletion:

```python
# Inside transaction: collect in batches
dm_attachment_keys: list[str] = []
batch_offset = 0
_BATCH = 1000
while True:
    dm_rows = await conn.fetch(
        "SELECT attachment_key FROM dm_messages "
        "WHERE sender_id = $1 AND attachment_key IS NOT NULL "
        "ORDER BY created_at LIMIT $2 OFFSET $3",
        user_id, _BATCH, batch_offset,
    )
    if not dm_rows:
        break
    dm_attachment_keys.extend(r["attachment_key"] for r in dm_rows)
    batch_offset += _BATCH
    if len(dm_rows) < _BATCH:
        break
```

Alternatively, move file deletion to a Celery task that processes keys in batches after the transaction commits, avoiding holding all keys in the request handler.

### Impact

Bounds in-transaction memory to 1,000 rows at a time. For the post-transaction deletion loop, the full list is still needed (to ensure all files are cleaned up after the DB transaction commits), but it can be paginated through Celery for very large datasets.

---

<a id="mo-19"></a>

## MO-19: Idempotency Middleware Response Body Buffering

**Severity:** MEDIUM
**Peak Memory:** Up to response body size per idempotent request
**Complexity:** Low (add size guard)
**Risk:** None

### Current State

**File:** `backend/app/middleware/idempotency.py:104-133`

```python
if "application/json" in content_type:
    body = b""
    async for chunk in response.body_iterator:               # line 106
        body += chunk if isinstance(chunk, bytes) else chunk.encode()  # line 107

    status = response.status_code
    cacheable = (200 <= status <= 299) or (400 <= status <= 499 and status != 429)
    if cacheable:
        cache_data = json.dumps({
            "body": body.decode("utf-8", errors="replace"),  # line 114
            "status_code": status,
        })
        await redis.set(redis_key, cache_data, ex=IDEMPOTENCY_TTL)  # line 119
```

### Problem

The middleware reads the **entire response body** into memory to cache it in Redis. For most API responses, this is small (1–10 KB). However:

1. **List endpoints** with large page sizes can return 50–100 KB responses
2. **Form CSV export trigger** returns a download URL (small), but the pattern would buffer any JSON response
3. **`body += chunk`** uses string concatenation, which creates intermediate copies (O(n²) for many chunks)

The `IDEMPOTENCY_TTL = 300` seconds means cached responses occupy Redis memory for 5 minutes. If many unique idempotency keys are used (e.g., frontend sends unique key per retry), Redis accumulates many response bodies.

### Recommended Approach

Add a response size limit before caching:

```python
MAX_IDEMPOTENCY_BODY_SIZE = 512 * 1024  # 512 KB

body_chunks: list[bytes] = []
body_size = 0
async for chunk in response.body_iterator:
    c = chunk if isinstance(chunk, bytes) else chunk.encode()
    body_size += len(c)
    body_chunks.append(c)

body = b"".join(body_chunks)  # single join instead of repeated concatenation

if body_size > MAX_IDEMPOTENCY_BODY_SIZE:
    # Response too large to cache — clear processing marker and return
    await redis.delete(redis_key)
    return Response(content=body, status_code=response.status_code, headers=dict(response.headers))

# Proceed with caching...
```

This also fixes the O(n²) concatenation pattern by using `b"".join()`.

### Impact

Bounds idempotency cache memory to 512 KB per response. Fixes string concatenation inefficiency for large responses. Prevents Redis memory growth from large cached responses.

---

<a id="mo-20"></a>

## MO-20: Form CSV Export Full StringIO Materialization

**Severity:** MEDIUM
**Peak Memory:** Proportional to total form responses (10K responses ≈ 20–50 MB)
**Complexity:** Medium (streaming upload)
**Risk:** Low

### Current State

**File:** `backend/app/tasks/form_export.py`

The task fetches responses in 1000-row batches (line 80–131) and writes each row to a `StringIO` CSV writer — good so far. But at line 134:

```python
csv_bytes = output.getvalue().encode("utf-8-sig")   # line 134 — entire CSV materialized
upload_file(csv_bytes, storage_key, "text/csv")       # line 136 — sync upload
```

### Problem

`output.getvalue()` returns the **entire accumulated CSV as a single string**, then `.encode()` creates a **bytes copy**. For a form with 50,000 responses and 20 questions:

- Each CSV row ≈ 500 bytes
- 50,000 rows × 500 bytes = ~25 MB string
- `.encode("utf-8-sig")` creates another ~25 MB bytes object
- **Peak: ~50 MB** (string + bytes coexisting before GC)

This runs in a Celery worker with `max-memory-per-child=256 MB`, so a very large export could approach the limit.

### Recommended Approach

**Option A (Write to temp file, stream upload):**

```python
import tempfile

with tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024, mode="w+b") as tmp:
    # Write BOM
    tmp.write(b"\xef\xbb\xbf")
    # Write CSV rows incrementally
    text_wrapper = io.TextIOWrapper(tmp, encoding="utf-8", newline="")
    writer = csv.writer(text_wrapper)
    writer.writerow(headers)
    # ... batch loop writes rows ...
    text_wrapper.flush()
    text_wrapper.detach()

    tmp.seek(0)
    file_size = tmp.seek(0, 2)
    tmp.seek(0)
    # Use S3 put_object with file-like object (streaming)
    s3.put_object(Bucket=bucket, Key=key, Body=tmp, ContentLength=file_size, ContentType="text/csv")
```

Files under 5 MB stay in memory (fast); larger exports spill to disk automatically.

**Option B (Simpler — just avoid double buffer):**

```python
# Instead of:
csv_bytes = output.getvalue().encode("utf-8-sig")

# Use:
output.seek(0)
csv_text = output.read()
output.close()  # release StringIO buffer
csv_bytes = ("\ufeff" + csv_text).encode("utf-8")  # BOM prepend + single encode
del csv_text  # release string
upload_file(csv_bytes, storage_key, "text/csv")
```

This still materializes the full CSV, but avoids holding both `StringIO` and `bytes` simultaneously.

### Impact

Option A bounds memory to 5 MB per export regardless of response count. Option B halves peak memory by avoiding concurrent buffers.

---

<a id="mo-21"></a>

## MO-21: PDF Sanitization Triple Buffer

**Severity:** LOW (bounded by 20 MB editor file limit)
**Peak Memory:** ~60–80 MB for a 20 MB PDF
**Complexity:** Low (release input buffer earlier)
**Risk:** None

### Current State

**File:** `backend/app/core/file_validation.py:59-85`

```python
def sanitize_pdf(data: bytes) -> bytes:
    import pikepdf

    pdf = pikepdf.open(BytesIO(data))         # line 67 — input buffer + pikepdf internal structures

    # Strip dangerous keys (lines 72-81)
    for key in _PDF_DANGEROUS_KEYS:
        if key in pdf.Root:
            del pdf.Root[key]
    for page in pdf.pages:
        # ...strip page-level keys...

    buf = BytesIO()
    pdf.save(buf)                              # line 84 — output buffer
    return buf.getvalue()                      # line 85 — bytes copy of output
```

### Problem

Three buffers coexist during PDF sanitization:

| Buffer | Size |
|--------|------|
| `data` (input bytes, passed by caller) | up to 20 MB |
| pikepdf internal structures | ~20–40 MB (depends on PDF object count) |
| `buf` (output BytesIO) | ~20 MB |
| `buf.getvalue()` return value | ~20 MB |

**Peak:** ~60–80 MB for a 20 MB PDF

### Why This Is Low Severity

The editor file upload limit is 20 MB (`MAX_EDITOR_FILE_SIZE`), so the absolute maximum is bounded. This only becomes a concern if:
- Multiple concurrent PDF uploads occur (5 × 80 MB = 400 MB)
- The file size limit is increased in the future

### Recommended Approach

Release the input buffer before generating output:

```python
def sanitize_pdf(data: bytes) -> bytes:
    import pikepdf

    pdf = pikepdf.open(BytesIO(data))

    # Strip dangerous keys...

    del data  # release input buffer — caller no longer needs it
    # Note: BytesIO(data) inside pikepdf may still hold a reference;
    # this only works if pikepdf has fully parsed the PDF.

    buf = BytesIO()
    pdf.save(buf)
    pdf.close()  # release pikepdf internal structures
    return buf.getvalue()
```

However, this requires the caller to not reference `data` after calling `sanitize_pdf()`. Currently, `validate_editor_file()` at line 141 reassigns `data = sanitize_pdf(data)`, so the old `data` reference is dropped — making this safe.

### Impact

Reduces peak from ~80 MB to ~40–60 MB. Marginal improvement given the 20 MB file limit.

---

<a id="mo-22"></a>

## MO-22: DM Store Data Persistence Across Route Navigation

**Severity:** MEDIUM
**Peak Memory:** Accumulates across multiple conversation views in a session
**Complexity:** Low (add cleanup on navigation)
**Risk:** None

### Current State

**File:** `frontend/src/stores/dm.ts`

```typescript
const messages = ref<DMMessage[]>([])              // line 12
const conversations = ref<Conversation[]>([])       // line 8
```

**File:** `frontend/src/views/DMView.vue:78-80`

```typescript
onUnmounted(() => {
  dmStore.setActiveConversation(null)               // line 79 — clears active ID only
})
```

### Problem

When the user navigates away from DMView (e.g., to Forum, then back to DM):

1. `conversations` array stays populated from the previous visit
2. `messages` array from the last-viewed conversation stays in memory
3. On return, `fetchConversations()` replaces the list (line 42: `conversations.value = res.conversations`), but `messages` may still hold old data if a different conversation is opened

When switching between conversations within DMView:

1. `fetchMessages()` with `page === 1` replaces messages (line 63)
2. But if the user loaded 5 pages of messages in Conversation A (150 messages), then switches to Conversation B, those 150 messages are replaced — **this is correct**
3. However, if the user switches back to A, they must re-fetch — no issue, but the previous 150 messages were held in memory until the switch

The real accumulation risk is **within a single conversation session** (MO-09), not across navigation. However, there's a secondary concern:

**No cleanup on logout detection:** If the auth token expires while on DMView, the store retains stale data until `clearSession()` is called from auth store.

### Recommended Approach

Clear messages when navigating away from DM:

```typescript
// In DMView.vue onUnmounted:
onUnmounted(() => {
  dmStore.setActiveConversation(null)
  dmStore.messages = []          // release message array
  dmStore.messagesTotal = 0
})
```

Or implement via a route guard:

```typescript
// In router/index.ts, DM route definition:
{
  path: '/messages',
  beforeLeave: (to, from) => {
    const dmStore = useDMStore()
    dmStore.messages = []
    dmStore.messagesTotal = 0
  }
}
```

### Impact

Ensures messages are GC'd when the user leaves DM. Conversations list is lightweight (30 items × ~200 bytes = 6 KB) and doesn't need clearing.

---

<a id="mo-23"></a>

## MO-23: Dead Code — `find_all_responses()` Unbounded Query

**Severity:** LOW (currently unused in production)
**Peak Memory:** Unbounded if accidentally called
**Complexity:** Trivial (delete function)
**Risk:** None

### Current State

**File:** `backend/app/repositories/form_repo.py:435-453`

```python
async def find_all_responses(form_id: uuid.UUID) -> list[dict]:
    """Fetch all responses for a form (for stats computation)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, form_id, user_id, answers, created_at
               FROM form_responses WHERE form_id = $1""",
            form_id,
        )
        # ...parse and return all rows at once...
```

### Problem

This function has **no LIMIT** and loads all form responses into memory at once. A test (`test_bug_fixes_b07_b09_b11_b12.py:529-543`) explicitly verifies that `get_form_stats()` does NOT call this function. However, the function still exists and could be accidentally used by a future developer.

**Grep confirms:** Only referenced in `form_repo.py` (definition) and one test file (negative assertion).

### Recommended Approach

Delete the function entirely, or mark it clearly:

```python
# Option A: Delete
# (remove lines 435-453)

# Option B: Add deprecation warning
async def find_all_responses(form_id: uuid.UUID) -> list[dict]:
    """DEPRECATED: Use iter_responses_batched() instead. This loads ALL rows into memory."""
    raise NotImplementedError("Use iter_responses_batched() to avoid OOM")
```

### Impact

Eliminates the risk of accidentally loading unbounded form responses. The existing test assertion becomes a compile-time guarantee instead of a runtime check.

---

## Updated Summary and Prioritization

### Complete Finding Table (Original + Supplementary)

| Priority | Finding | Type | Peak Memory Risk | Complexity | Risk |
|----------|---------|------|-----------------|-----------|------|
| **P0** | MO-01: Docker container limits | Config | ~2–3 GB savings | Trivial | None |
| **P0** | MO-02: nginx zone sizes | Config | ~160 MB savings | Trivial | None |
| **P0** | **MO-15: ZIP reconstruction memory bomb** | Code | **~300–400 MB/request** | Low–Medium | Medium |
| **P1** | MO-03: asyncpg pool min_size | Config | ~80–120 MB savings | Low | Low |
| **P1** | MO-07: DM cleanup LIMIT | Code | Prevents OOM | Low | None |
| **P1** | MO-06: Form responses generator | Code | Prevents OOM | Medium | Low |
| **P1** | **MO-16: Thumbnail PIL decompression** | Code | **~252 MB/task** | Low | Low |
| **P1** | **MO-17: Concurrent upload pressure** | Code | **~500 MB site-wide** | Medium | Low |
| **P2** | MO-05: Reaction JSONB in-DB ops | Code | O(n)→O(1)/toggle | Medium | Medium |
| **P2** | MO-08: Post list exclude content | Code | ~50–500 KB/req | Medium | Low |
| **P2** | MO-09: DM messages cap | Code | ~1–5 MB/session | Medium | Low |
| **P2** | MO-10: Post accumulation cap | Code | ~5–50 MB/session | Low | Low |
| **P2** | MO-14: Virtual scrolling | Code | DOM memory bound | Medium | Low |
| **P2** | **MO-18: Anonymization DM query** | Code | Unbounded | Low | None |
| **P2** | **MO-19: Idempotency body buffer** | Code | Response size | Low | None |
| **P2** | **MO-20: CSV export StringIO** | Code | ~50 MB for large exports | Medium | Low |
| **P3** | MO-04: Redis pool size | Config | ~20–30 MB savings | Trivial | None |
| **P3** | MO-11: FormHistory snapshots | Code | ~5–8 MB/session | High | Medium |
| **P3** | MO-12: Deep watchers | Code | CPU reduction | Medium | Low |
| **P3** | MO-13: Avatar URL cache | Code | CPU reduction | Low | None |
| **P3** | **MO-21: PDF sanitization buffers** | Code | ~60–80 MB/request | Low | None |
| **P3** | **MO-22: DM store navigation cleanup** | Code | ~0.5–2 MB/session | Low | None |
| **P3** | **MO-23: Dead code removal** | Code | Prevents future OOM | Trivial | None |

### Revised Implementation Phases

1. **Phase 1 (Config + Critical):** MO-01 + MO-02 + MO-03 + MO-04 + MO-15 (reduce ZIP uncompressed limit or use SpooledTemporaryFile)
2. **Phase 2 (Safety nets):** MO-07 + MO-06 + MO-16 (thumbnail dimension limit) + MO-18 + MO-23
3. **Phase 3 (Per-request optimization):** MO-08 + MO-09 + MO-10 + MO-17 (upload semaphore) + MO-19
4. **Phase 4 (Scaling):** MO-05 + MO-14 + MO-20
5. **Phase 5 (Polish):** MO-11 + MO-12 + MO-13 + MO-21 + MO-22

---

## Per-User Quota Evaluation

This section evaluates every per-user quota against the platform's actual usage profile (academic exchange for AI in Language Learning and Literacy) and the memory risks identified in MO-01 through MO-23. The goal is to determine which quotas are set higher than necessary and can be lowered to reduce memory pressure without impacting legitimate usage.

### Evaluation Framework

**Platform profile:** Academic community — users upload research PDFs (1–10 MB), presentation slides (5–20 MB), activity photos (0.5–5 MB), and exchange short academic messages. This is not a consumer social network or media hosting platform.

**Key reference points for quota sizing:**

| Platform | Feature | Limit |
|----------|---------|-------|
| LinkedIn | Profile summary | 2,600 chars |
| GitHub | Issue comment | ~65,535 chars (soft) |
| Stack Overflow | Answer body | 30,000 chars |
| Slack | Message | 40,000 chars |
| Slack | File upload | 1 GB (paid) / none (free) |
| Discord | File upload | 25 MB (free) / 500 MB (Nitro) |
| Google Drive | Shared file | 5 TB (Workspace) |
| WhatsApp | Document attachment | 100 MB |
| Telegram | File attachment | 2 GB (premium) / 100 MB (free) |

---

### Complete Per-User Quota Inventory

The following table lists every per-user quota currently enforced in the system, grouped by category.

#### Storage & File Quotas

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Per-user total storage | `MAX_USER_STORAGE_BYTES` | 1 GB | `config.py` | 78 |
| Editor file size | `MAX_EDITOR_FILE_SIZE` | 20 MB | `constants.py` | 29 |
| Album upload endpoint | `MAX_ALBUM_UPLOAD_BYTES` | 50 MB | `constants.py` | 30 |
| Album photo size | `ALBUM_MAX_PHOTO_SIZE_BYTES` | 10 MB | `constants.py` | 94 |
| Album cover size | `ALBUM_MAX_COVER_SIZE_BYTES` | 5 MB | `constants.py` | 95 |
| Album ZIP size | `ALBUM_MAX_ZIP_SIZE_BYTES` | 100 MB | `constants.py` | 96 |
| Album photos per album | `ALBUM_MAX_PHOTOS` | 50 | `constants.py` | 99 |
| DM attachment size | `DM_MAX_ATTACHMENT_SIZE` | 50 MB | `constants.py` | 151 |
| Avatar size | `MAX_AVATAR_SIZE` | 2 MB | `constants.py` | 28 |

#### Content Creation Quotas

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Posts per day | `MAX_POSTS_PER_DAY` | 50 | `constants.py` | 18 |
| Comments per post | `MAX_COMMENTS_PER_POST` | 200 | `constants.py` | 19 |
| Comment length | `MAX_COMMENT_LENGTH` | 10,000 chars | `constants.py` | 25 |
| Keywords per post | `MAX_KEYWORDS` | 15 | `constants.py` | 24 |
| Keyword length | `MAX_KEYWORD_LENGTH` | 50 chars | `constants.py` | 54 |
| Bio length | `MAX_BIO_LENGTH` | 50,000 chars | `constants.py` | 50 |
| Display name length | `MAX_DISPLAY_NAME_LENGTH` | 100 chars | `constants.py` | 51 |
| Affiliation length | `MAX_AFFILIATION_LENGTH` | 200 chars | `constants.py` | 52 |
| ORCID length | `MAX_ORCID_LENGTH` | 30 chars | `constants.py` | 53 |
| Co-authors per post | `MAX_CO_AUTHORS_PER_POST` | 10 | `constants.py` | 109 |

#### DM Quotas

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Message length | `DM_MAX_MESSAGE_LENGTH` | 5,000 chars | `constants.py` | 146 |
| Char cap per conversation | `DM_CHAR_CAP_PER_CONVERSATION` | 50,000 chars | `constants.py` | 147 |
| Edit/recall window | `DM_EDIT_RECALL_WINDOW_HOURS` | 12 hours | `constants.py` | 148 |
| File expiry | `DM_FILE_EXPIRY_DAYS` | 3 days | `constants.py` | 149 |
| Text expiry | `DM_TEXT_EXPIRY_DAYS` | 30 days | `constants.py` | 150 |

#### Form Quotas

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Active standalone forms per user | `MAX_ACTIVE_STANDALONE_FORMS_PER_USER` | 10 | `constants.py` | 89 |
| Active forms per SIG | `MAX_ACTIVE_FORMS_PER_SIG` | 20 | `constants.py` | 20 |
| Questions per form | (schema) | 100 | `schemas/form.py` | 69 |
| Options per question | (schema) | 50 | `schemas/form.py` | 29 |
| QA invites per question | `MAX_QA_INVITES_PER_QUESTION` | 5 | `constants.py` | 140 |

#### Session & Connection Quotas

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| WebSocket connections per user | `WS_MAX_CONNECTIONS_PER_USER` | 5 | `ws.py` | 18 |
| Global guest sessions | `MAX_GUESTS` | 30 | `constants.py` | 22 |
| Guest sessions per IP | `MAX_GUESTS_PER_IP` | 3 | `constants.py` | 23 |
| Guest session timeout | `GUEST_SESSION_TIMEOUT` | 45 min | `constants.py` | 66 |
| Active invite codes per user | `MAX_ACTIVE_INVITE_CODES_PER_USER` | 5 | `constants.py` | 21 |
| Blocked users per user | `MAX_BLOCKS_PER_USER` | 5 | `constants.py` | 113 |

#### Rate Limits (per user, per window)

| Feature | Constant | Max/Window | File | Line |
|---------|----------|-----------|------|------|
| Login | `RATE_LIMIT_LOGIN` | 10/60s | `constants.py` | 11 |
| Register | `RATE_LIMIT_REGISTER` | 5/60s | `constants.py` | 12 |
| Guest login | `RATE_LIMIT_GUEST` | 10/60s | `constants.py` | 13 |
| Comment | `RATE_LIMIT_COMMENT` | 30/60s | `constants.py` | 14 |
| Report | `RATE_LIMIT_REPORT` | 5/60s | `constants.py` | 15 |
| Captcha | `RATE_LIMIT_CAPTCHA` | 20/60s | `constants.py` | 73 |
| File upload | `RATE_LIMIT_FILE_UPLOAD` | 10/60s | `constants.py` | 74 |
| Form submit | `RATE_LIMIT_FORM_SUBMIT` | 5/60s | `constants.py` | 75 |
| Form export | `RATE_LIMIT_FORM_EXPORT` | 1/300s | `constants.py` | 76 |
| Form stats | `RATE_LIMIT_FORM_STATS` | 10/60s | `constants.py` | 77 |
| Invite generate | `RATE_LIMIT_INVITE_GEN` | 5/3600s | `constants.py` | 78 |
| Invite verify | `RATE_LIMIT_INVITE_VERIFY` | 10/60s | `constants.py` | 79 |
| Reaction | `RATE_LIMIT_REACTION` | 30/60s | `constants.py` | 80 |
| SIG join | `RATE_LIMIT_SIG_JOIN` | 10/60s | `constants.py` | 81 |
| SIG manage | `RATE_LIMIT_SIG_MANAGE` | 20/60s | `constants.py` | 82 |
| SIG CRUD | `RATE_LIMIT_SIG_CRUD` | 10/60s | `constants.py` | 83 |
| Category CRUD | `RATE_LIMIT_CATEGORY_CRUD` | 10/60s | `constants.py` | 84 |
| Preferences | `RATE_LIMIT_PREFERENCES` | 10/60s | `constants.py` | 85 |
| Search suggestions | `RATE_LIMIT_SEARCH_SUGGESTIONS` | 30/60s | `constants.py` | 86 |
| Standalone form | `RATE_LIMIT_STANDALONE_FORM` | 10/60s | `constants.py` | 90 |
| Album upload | `RATE_LIMIT_ALBUM_UPLOAD` | 10/60s | `constants.py` | 102 |
| Album comment | `RATE_LIMIT_ALBUM_COMMENT` | 30/60s | `constants.py` | 103 |
| Co-author invite | `RATE_LIMIT_CO_AUTHOR_INVITE` | 10/60s | `constants.py` | 110 |
| Social | `RATE_LIMIT_SOCIAL` | 30/60s | `constants.py` | 114 |
| Friend request | `RATE_LIMIT_FRIEND_REQUEST` | 10/60s | `constants.py` | 115 |
| Citation search | `RATE_LIMIT_CITATION_SEARCH` | 20/60s | `constants.py` | 123 |
| Vote | `RATE_LIMIT_VOTE` | 60/60s | `constants.py` | 142 |
| DM send | `RATE_LIMIT_DM_SEND` | 30/60s | `constants.py` | 152 |
| DM list | `RATE_LIMIT_DM_LIST` | 60/60s | `constants.py` | 153 |
| DM edit | `RATE_LIMIT_DM_EDIT` | 30/60s | `constants.py` | 154 |
| DM recall | `RATE_LIMIT_DM_RECALL` | 20/60s | `constants.py` | 155 |
| DM mark read | `RATE_LIMIT_DM_MARK_READ` | 60/60s | `constants.py` | 156 |

#### Pagination Limits

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Max page size | `MAX_PAGE_SIZE` | 100 | `constants.py` | 46 |
| Max page number | `MAX_PAGE_NUMBER` | 10,000 | `constants.py` | 47 |
| Default page size (general) | `DEFAULT_PAGE_SIZE` | 20 | `constants.py` | 40 |
| DM page size | `DEFAULT_PAGE_SIZE_DM` | 30 | `constants.py` | 157 |

#### Other Limits

| Quota | Constant | Current Value | File | Line |
|-------|----------|--------------|------|------|
| Post history display limit | `POST_HISTORY_LIMIT` | 50 | `constants.py` | 57 |
| Avatar cache entries | `AVATAR_CACHE_MAX_SIZE` | 50 | `constants.py` | 60 |
| Recommendation max per user | `RECOMMENDATION_MAX_PER_USER` | 10 | `constants.py` | 126 |
| Recommendation max users (skip CROSS JOIN) | `RECOMMENDATION_MAX_USERS` | 2,000 | `constants.py` | 129 |
| Recommendation batch size | `RECOMMENDATION_BATCH_SIZE` | 200 | `constants.py` | 130 |
| Follower notification max | `FOLLOWER_NOTIFICATION_MAX` | 500 | `constants.py` | 118 |

---

### Quotas Recommended for Reduction

<a id="q-01"></a>

#### Q-01: `MAX_BIO_LENGTH` — 50,000 → 5,000

**File:** `backend/app/core/constants.py:50`

| Aspect | Detail |
|--------|--------|
| **Current** | 50,000 characters (~25 pages of A4 text) |
| **Proposed** | 5,000 characters (~2.5 pages) |
| **Rationale** | No academic bio needs 25 pages. LinkedIn caps summaries at 2,600. A 5,000-char bio can include a full research statement, publication highlights, and contact info. |
| **Memory link** | User listing APIs return bio in full. 20 users × 50K chars = 1 MB per page vs 20 × 5K = 100 KB. Affects MO-08 (post list memory) indirectly via user profile queries. |
| **Risk** | None. No existing user is likely to have a bio approaching 50K. |
| **Migration** | No DB migration needed — this is a validation-only constant. Existing bios exceeding 5K would only be rejected on next edit. |

<a id="q-02"></a>

#### Q-02: `ALBUM_MAX_ZIP_SIZE_BYTES` — 100 MB → 50 MB

**File:** `backend/app/core/constants.py:96`

| Aspect | Detail |
|--------|--------|
| **Current** | 100 MB |
| **Proposed** | 50 MB (align with `MAX_ALBUM_UPLOAD_BYTES`) |
| **Rationale** | Two constants represent the same concept but differ in value, creating confusion. The endpoint at `albums.py:317` uses the 100 MB constant, but `MAX_ALBUM_UPLOAD_BYTES` (50 MB) was intended as the hard limit. 50 photos × 10 MB/photo = 500 MB uncompressed; a ZIP of typical JPEG photos compresses to 30–40% of raw size, so 50 MB ZIP holds 125–170 MB of images — more than enough for one album batch. |
| **Memory link** | **MO-15 (Critical).** ZIP reconstruction peak memory is proportional to input size: 100 MB ZIP → ~300–400 MB peak; 50 MB ZIP → ~150–200 MB peak. This single change halves the worst-case memory spike of the highest-severity finding. |
| **Risk** | None. Unifies two inconsistent constants. |
| **Implementation** | Change constant value OR replace endpoint reference with `MAX_ALBUM_UPLOAD_BYTES`. |

<a id="q-03"></a>

#### Q-03: `DM_MAX_ATTACHMENT_SIZE` — 50 MB → 10 MB

**File:** `backend/app/core/constants.py:151`

| Aspect | Detail |
|--------|--------|
| **Current** | 50 MB (aliased to `MAX_ALBUM_UPLOAD_BYTES`) |
| **Proposed** | 10 MB |
| **Rationale** | DM attachments serve a fundamentally different purpose than album uploads. Academic DM attachments are typically: PDFs (1–10 MB), screenshots (0.1–2 MB), Word/Excel documents (0.5–5 MB). No legitimate academic DM scenario requires a 50 MB file. Files are retained for only 3 days (`DM_FILE_EXPIRY_DAYS`), making large uploads particularly wasteful. For context: Discord free tier allows 25 MB, WhatsApp allows 100 MB, Telegram free allows 100 MB — but these are consumer messaging platforms handling media-heavy communication. An academic platform transmitting PDFs and documents needs far less. |
| **Memory link** | **MO-17 (High).** Each DM upload reads the full file into Python memory: `file_data = await file.read(DM_MAX_ATTACHMENT_SIZE + 1)` (dm.py:147). With current limit: 5 concurrent uploads × 50 MB = 250 MB. With proposed limit: 5 × 10 MB = 50 MB — an 80% reduction in concurrent upload memory pressure. |
| **Risk** | Very low. Users needing to share files >10 MB can use the editor file upload (which persists longer) or share via external links. |
| **Implementation** | Decouple from `MAX_ALBUM_UPLOAD_BYTES`; set as independent constant: `DM_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024`. |

<a id="q-04"></a>

#### Q-04: `MAX_EDITOR_FILE_SIZE` — 20 MB → 10 MB

**File:** `backend/app/core/constants.py:29`

| Aspect | Detail |
|--------|--------|
| **Current** | 20 MB |
| **Proposed** | 10 MB |
| **Rationale** | Allowed types are PNG, JPEG, PDF, DOCX. Academic PDFs with embedded figures typically range 1–10 MB. PDFs exceeding 10 MB usually contain uncompressed images that should be optimized before sharing. High-resolution photos for post illustration are typically 2–8 MB. DOCX files rarely exceed 5 MB. A 10 MB limit accommodates 99%+ of academic document sizes. |
| **Memory link** | **MO-21 (Low).** PDF sanitization creates ~3× buffer: 20 MB → 60–80 MB peak; 10 MB → 30–40 MB peak. **MO-17 (High).** Editor upload reads full file into memory: 10 concurrent × 20 MB = 200 MB; 10 × 10 MB = 100 MB. |
| **Risk** | Low. Rare edge case: a research poster PDF with many high-resolution images. Such files can be compressed or shared via external hosting. |
| **Implementation** | Single constant change. |

<a id="q-05"></a>

#### Q-05: `MAX_POSTS_PER_DAY` — 50 → 20

**File:** `backend/app/core/constants.py:18`

| Aspect | Detail |
|--------|--------|
| **Current** | 50 posts per day per user |
| **Proposed** | 20 posts per day per user |
| **Rationale** | Even the most prolific academic contributor would struggle to write 20 substantive posts in a single day. At 20 posts/day, that is roughly 1 post per waking hour — already an extreme pace. 50 posts/day is a spam-level threshold that provides no value as a legitimate use guard. For context: Reddit does not impose a hard daily post limit but community norms are 1–5 per subreddit; Stack Overflow rate-limits questions to 6/day for new users and 50/day for established users across the entire site. |
| **Memory link** | Indirect. More posts → larger `posts` table → more data in full-text search indexes, list queries (MO-08), and post accumulation in frontend (MO-10). |
| **Risk** | None. No legitimate user would be impacted. |
| **Implementation** | Single constant change. |

<a id="q-06"></a>

#### Q-06: `MAX_COMMENT_LENGTH` — 10,000 → 5,000

**File:** `backend/app/core/constants.py:25`

| Aspect | Detail |
|--------|--------|
| **Current** | 10,000 characters (~5 pages) |
| **Proposed** | 5,000 characters (~2.5 pages) |
| **Rationale** | Academic discussion comments are structured and concise. A 5,000-character comment can include a detailed argument with citations, code snippets, and formatted text. For context: GitHub PR review comments have no hard limit but are typically under 2,000 characters; Hacker News comments are capped at ~8,000. A 5,000-char limit is generous for a discussion comment (as opposed to a standalone article or answer). |
| **Memory link** | Comment content is loaded via `SELECT cm.*` in list queries. With pagination at 20 comments/page: 20 × 10K = 200 KB/page worst case → 20 × 5K = 100 KB/page. |
| **Risk** | Very low. Users writing extremely long responses can create a new post instead of a comment. |
| **Implementation** | Single constant change. Existing comments exceeding 5K are unaffected (validated only on create/edit). |

<a id="q-07"></a>

#### Q-07: `DM_CHAR_CAP_PER_CONVERSATION` — 50,000 → 20,000

**File:** `backend/app/core/constants.py:147`

| Aspect | Detail |
|--------|--------|
| **Current** | 50,000 characters per conversation pair (~25 pages) |
| **Proposed** | 20,000 characters per conversation pair (~10 pages) |
| **Rationale** | This cap controls how many total characters are retained in a conversation before the oldest messages are auto-deleted. Combined with `DM_TEXT_EXPIRY_DAYS = 30` (messages expire after 30 days regardless), the char cap serves as a secondary bound. 20,000 characters of conversation history (roughly 200 messages of 100 chars average) provides ample context for ongoing academic discussions. The 30-day text expiry already ensures old messages are cleaned up; a lower char cap simply accelerates cleanup for very active conversations. |
| **Memory link** | Lower cap → `dm_messages` table rows per conversation are bounded tighter → `find_expired_text_messages()` in MO-07 returns fewer rows → DM cleanup tasks use less memory. Also reduces the `messages` array size in the frontend DM store (MO-09). |
| **Risk** | Low. Very active conversations would see older messages deleted sooner. Users who need persistent records can use the forum (posts/comments) instead. |
| **Implementation** | Single constant change. Takes effect immediately — `send_message_atomic()` checks `total_chars` on each send and auto-deletes oldest when the cap is exceeded. |

<a id="q-08"></a>

#### Q-08: `RATE_LIMIT_FILE_UPLOAD` — (10, 60) → (5, 60)

**File:** `backend/app/core/constants.py:74`

| Aspect | Detail |
|--------|--------|
| **Current** | 10 uploads per 60 seconds per user |
| **Proposed** | 5 uploads per 60 seconds per user |
| **Rationale** | File uploads are memory-intensive operations (each one buffers the full file in Python memory). 10 uploads/minute from a single user means up to 10 files × 20 MB = 200 MB peak from one user alone. 5 uploads/minute (one every 12 seconds) is more than sufficient for inserting images into a post or uploading documents — users typically compose content between uploads. |
| **Memory link** | **MO-17 (High).** Directly reduces the maximum concurrent uploads from a single user: 10 → 5 in-flight files. Combined with Q-04 (10 MB editor limit), single-user peak drops from 200 MB to 50 MB. |
| **Risk** | None. 5 uploads per minute is generous. ZIP album upload (which uploads many photos at once) uses a separate endpoint and rate limit (`RATE_LIMIT_ALBUM_UPLOAD`). |
| **Implementation** | Single constant change. Configurable via `RATE_LIMIT_FILE_UPLOAD_MAX` env var. |

---

### Quotas Evaluated and Confirmed as Appropriate

The following quotas were reviewed and determined to be already well-sized for the platform's usage profile. No changes recommended.

#### Storage

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `MAX_USER_STORAGE_BYTES` | 1 GB | **Keep** | Academic users accumulate PDFs, images, and documents over months/years. 1 GB provides a comfortable runway. Lowering would force users to manage storage actively, which is a poor UX for an academic platform. MinIO storage is cheap. |
| `MAX_AVATAR_SIZE` | 2 MB | **Keep** | Standard for profile photos. Most avatars are well under 1 MB. |
| `ALBUM_MAX_PHOTO_SIZE_BYTES` | 10 MB | **Keep** | Activity photos may be taken with modern phone cameras (12–50 MP). 10 MB accommodates high-quality JPEG/HEIF images. |
| `ALBUM_MAX_COVER_SIZE_BYTES` | 5 MB | **Keep** | Proportional to photo size. |
| `ALBUM_MAX_PHOTOS` | 50 | **Keep** | One academic event = 20–50 photos. Reasonable per-album cap. |

#### Content

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `MAX_COMMENTS_PER_POST` | 200 | **Keep** | Popular discussion threads in academic communities can generate 50–200 comments. This is a per-post (not per-user) limit. |
| `MAX_KEYWORDS` | 15 | **Keep** | Academic papers commonly have 5–10 keywords. 15 allows cross-disciplinary tagging. |
| `MAX_KEYWORD_LENGTH` | 50 | **Keep** | Multi-word academic keywords (e.g., "Natural Language Processing") fit within 50 chars. |
| `MAX_DISPLAY_NAME_LENGTH` | 100 | **Keep** | Accommodates long names and academic titles. |
| `MAX_AFFILIATION_LENGTH` | 200 | **Keep** | Full institutional names can be long (e.g., "Department of Computer Science, National Taiwan University"). |
| `MAX_CO_AUTHORS_PER_POST` | 10 | **Keep** | Reflects reality of multi-author academic publications. |

#### DM

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `DM_MAX_MESSAGE_LENGTH` | 5,000 | **Keep** | A single message of 5K chars can include a detailed paragraph with quotes. Appropriate for academic discussion. |
| `DM_EDIT_RECALL_WINDOW_HOURS` | 12 | **Keep** | Generous but reasonable. Allows correction of messages sent late at night. |
| `DM_FILE_EXPIRY_DAYS` | 3 | **Keep** | Short retention is appropriate — DM attachments are meant for quick sharing, not archival. |
| `DM_TEXT_EXPIRY_DAYS` | 30 | **Keep** | One month of message history provides sufficient context for ongoing discussions. |

#### Forms

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `MAX_ACTIVE_STANDALONE_FORMS_PER_USER` | 10 | **Keep** | Researchers may run multiple surveys simultaneously. 10 active forms is appropriate. |
| `MAX_ACTIVE_FORMS_PER_SIG` | 20 | **Keep** | A SIG with multiple researchers may have several active surveys/feedback forms. |
| Questions per form | 100 | **Keep** | Long research questionnaires may have 50–100 questions. |
| Options per question | 50 | **Keep** | Likert scales, multi-choice with many options. |

#### Sessions & Connections

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `WS_MAX_CONNECTIONS_PER_USER` | 5 | **Keep** | Users may have the platform open in multiple browser tabs/devices. |
| `MAX_GUESTS` | 30 | **Keep** | Appropriate for public access to an academic platform. |
| `MAX_GUESTS_PER_IP` | 3 | **Keep** | Prevents abuse while allowing shared networks (university labs). |
| `GUEST_SESSION_TIMEOUT` | 45 min | **Keep** | Reasonable inactivity timeout for browsing sessions. |
| `MAX_ACTIVE_INVITE_CODES_PER_USER` | 5 | **Keep** | Sufficient for inviting colleagues. |
| `MAX_BLOCKS_PER_USER` | 5 | **Keep** | Adequate for an academic platform with low harassment. Could consider raising to 10, but not a memory concern. |

#### Rate Limits

| Rate Limit | Value | Verdict | Reasoning |
|------------|-------|---------|-----------|
| `RATE_LIMIT_LOGIN` | 10/60s | **Keep** | Brute-force protection. |
| `RATE_LIMIT_REGISTER` | 5/60s | **Keep** | Registration abuse protection. |
| `RATE_LIMIT_COMMENT` | 30/60s | **Keep** | Allows rapid discussion participation. |
| `RATE_LIMIT_REACTION` | 30/60s | **Keep** | Users may react to multiple posts in quick succession. |
| `RATE_LIMIT_DM_SEND` | 30/60s | **Keep** | Academic conversations can be rapid. |
| `RATE_LIMIT_FORM_EXPORT` | 1/300s | **Keep** | Export is a heavy operation (MO-20). |
| `RATE_LIMIT_ALBUM_UPLOAD` | 10/60s | **Keep** | Separate from editor file upload. ZIP upload is a single request containing many photos. |
| All other rate limits | Various | **Keep** | Appropriately sized for their respective operations. |

#### Pagination & Cache

| Quota | Value | Verdict | Reasoning |
|-------|-------|---------|-----------|
| `MAX_PAGE_SIZE` | 100 | **Keep** | Upper bound for client-requested page size. |
| `DEFAULT_PAGE_SIZE` | 20 | **Keep** | Reasonable default for all list views. |
| `POST_HISTORY_LIMIT` | 50 | **Keep** | Sufficient for tracking post edits. |
| `AVATAR_CACHE_MAX_SIZE` | 50 | **Keep** | Already well-tuned with TTL and byte limit. |
| `RECOMMENDATION_BATCH_SIZE` | 200 | **Keep** | Balances memory and throughput for daily Celery task. |

---

### Summary: Recommended Quota Changes

| ID | Quota | Current | Proposed | Memory Impact | Risk |
|----|-------|---------|----------|--------------|------|
| Q-01 | `MAX_BIO_LENGTH` | 50,000 | **5,000** | Reduces user list API response size by up to 90% | None |
| Q-02 | `ALBUM_MAX_ZIP_SIZE_BYTES` | 100 MB | **50 MB** | MO-15: ZIP reconstruction peak halved (400→200 MB) | None |
| Q-03 | `DM_MAX_ATTACHMENT_SIZE` | 50 MB | **10 MB** | MO-17: Concurrent upload memory reduced by 80% | Very low |
| Q-04 | `MAX_EDITOR_FILE_SIZE` | 20 MB | **10 MB** | MO-17/MO-21: Per-upload and PDF sanitization peak halved | Low |
| Q-05 | `MAX_POSTS_PER_DAY` | 50 | **20** | Indirect: reduces post accumulation in DB and frontend | None |
| Q-06 | `MAX_COMMENT_LENGTH` | 10,000 | **5,000** | Reduces comment list query memory by up to 50% | Very low |
| Q-07 | `DM_CHAR_CAP_PER_CONVERSATION` | 50,000 | **20,000** | Reduces dm_messages table size; MO-07/MO-09 impact | Low |
| Q-08 | `RATE_LIMIT_FILE_UPLOAD` | (10, 60) | **(5, 60)** | MO-17: Single-user concurrent upload pressure halved | None |

**All changes are single-line constant modifications.** No database migrations, no architectural changes, no frontend modifications required. Existing data exceeding new limits is unaffected — limits are enforced only on creation/edit.

### Combined Memory Impact with MO Findings

When Q-01 through Q-08 are applied together with Phase 1 of the MO recommendations:

| Scenario | Before | After |
|----------|--------|-------|
| ZIP album upload peak | ~300–400 MB | ~150–200 MB (Q-02) |
| 5 concurrent DM uploads | ~250 MB | ~50 MB (Q-03) |
| 10 concurrent editor uploads | ~200 MB | ~50 MB (Q-04 + Q-08) |
| PDF sanitization peak (max file) | ~60–80 MB | ~30–40 MB (Q-04) |
| User list API (20 users, full bio) | ~1 MB | ~100 KB (Q-01) |
| DM cleanup task (char-cap messages) | O(50K chars/conv) | O(20K chars/conv) (Q-07) |

These quota reductions are complementary to (not replacements for) the architectural changes proposed in MO-01 through MO-23. Applied together, they provide defense-in-depth: quotas bound the input size, while architectural changes bound the processing memory.
