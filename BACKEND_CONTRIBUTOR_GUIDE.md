# AI3L Community Backend -- Contributor Task Guide

> **Last Updated:** 2026-03-02
> **Applies to:** Backend codebase (`backend/`)
> **Audience:** Collaborators working on the FastAPI backend
> **See also:** `FRONTEND_CONTRIBUTOR_GUIDE.md` for frontend tasks

---

## Introduction

This document catalogues backend tasks for the AI3L Community platform.
It covers bug fixes, security hardening, missing features, data integrity
improvements, and infrastructure work. Tasks are organized by category and
include difficulty ratings, affected files, and step-by-step plans.

### Difficulty Scale

| Label | What it means |
|-------|--------------|
| **Beginner** | 1-2 files, small targeted fix |
| **Intermediate** | 3-5 files, requires understanding the service/repo layers |
| **Advanced** | Architectural decisions, multiple subsystems, migrations |

### Architecture Quick Reference

```
backend/app/
├── api/v1/endpoints/   Route handlers (thin: validate, call service, return)
├── services/           Business logic (orchestrates repos, emits events)
├── repositories/       Raw SQL via asyncpg (one module per entity)
├── schemas/            Pydantic request/response models
├── models/             SQLAlchemy models (used by Alembic only)
├── converters/         _row_to_X() functions (dict → schema)
├── core/               Shared infra (deps, database, rate_limit, event_bus, etc.)
├── middleware/         CSRF, idempotency
├── tasks/              Celery async tasks (form_export, virustotal)
└── event_handlers.py   Event bus subscribers
```

**Key rules:**
- All SQL lives in `repositories/`, never in services or endpoints.
- Services raise domain exceptions (`ValueError`, `PermissionError`);
  endpoints catch and map to HTTP status codes.
- Tests mock at the boundary: `app.repositories.X_repo.get_pool` or
  `app.services.X.get_pool` for transactional services.

---

## Section 1: Bug Fixes & Error Handling

---

### 1.1 VirusTotal Check Silently Swallows All Errors

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/files.py:51-57`

**Problem:**
The VirusTotal scan trigger is wrapped in `except Exception: pass`, which
silently swallows import errors, network errors, and storage errors. If
the scan infrastructure is broken, no one will know.

**Fix:**
```python
# Replace bare except with logging:
except ImportError:
    pass  # VirusTotal not configured — acceptable
except Exception:
    logger.warning("VirusTotal scan trigger failed for key=%s", key, exc_info=True)
```

---

### 1.2 WebSocket Send Failures Silently Ignored

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/ws.py:135, 158`

**Problem:**
`except Exception: pass` on WebSocket send means if a broadcast fails,
the client never receives the message and the server has no log entry.

**Fix:**
Add `logger.debug(...)` or `logger.warning(...)` inside the except blocks
so failures are at least visible in logs.

---

## Section 2: Security & Validation Hardening

---

### 2.1 Schema Fields Missing Length Constraints

**Difficulty: Beginner**
**Files:** `app/schemas/form.py`, `app/schemas/user.py`, `app/schemas/post.py`

**Problem:**
Several Pydantic schema fields accept arbitrarily long strings:
- `form.py`: `placeholder` field has no `max_length`.
- `user.py`: `bio`, `affiliation`, `orcid` fields have no `max_length`.
- `post.py`: `keywords` array limits count (`max_length=15`) but not
  individual keyword length — a client could send 15 x 10,000-char strings.

**Fix:**
Add `max_length` constraints:
```python
# form.py
placeholder: str | None = Field(None, max_length=500)

# user.py
bio: str | None = Field(None, max_length=1000)
affiliation: str | None = Field(None, max_length=500)
orcid: str | None = Field(None, max_length=50)

# post.py — add a validator:
@field_validator("keywords")
@classmethod
def validate_keywords(cls, v: list[str] | None) -> list[str] | None:
    if v:
        for kw in v:
            if len(kw) > 100:
                raise ValueError("Each keyword must be 100 characters or fewer.")
    return v
```

---

### 2.2 Post Update Accepts Empty Payload

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/posts.py:104-129`

**Problem:**
The post update endpoint does not validate that at least one field is
being changed. A client can send an empty update with a valid version
number, causing a wasted database transaction that increments the version
without any actual change.

**Fix:**
Add a check in the endpoint or schema:
```python
if not any([req.title, req.content, req.category_id, req.keywords is not None]):
    raise HTTPException(status_code=400, detail="At least one field must be provided.")
```

---

### 2.3 Comment Delete Does Not Cross-Validate `post_id`

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/comments.py:92-102`

**Problem:**
The delete comment endpoint accepts `post_id` and `comment_id` as path
parameters, but does not verify that the comment belongs to the specified
post. The soft-delete in the repo layer only checks `comment_id` and
`user_id`. If the wrong `post_id` is passed, the comment is still deleted
and the wrong post's `comment_count` is decremented.

**Fix:**
Before calling `soft_delete()`, fetch the comment and verify
`comment.post_id == post_id`. Or modify the repo query to include
`AND post_id = $X`.

---

### 2.4 Form Update Does Not Validate SIG Ownership

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/forms.py:105-131`

**Problem:**
The update form endpoint checks if the user is an admin but does not
validate that the form belongs to the expected SIG. A user could
theoretically update a form in a different SIG if they know the form_id.

**Fix:**
After fetching the form, verify `form["sig_id"]` matches the expected
context (either add a `sig_id` path parameter or check the user's SIG
admin role against the form's actual `sig_id`).

---

## Section 3: Data Integrity

---

### 3.1 SIG Deletion Does Not Cascade to Forms and Posts

**Difficulty: Intermediate**
**Files:** `app/services/sig.py`, `app/repositories/sig_repo.py`,
`app/repositories/form_repo.py`, `app/repositories/post_repo.py`

**Problem:**
When a SIG is soft-deleted, its associated forms and posts are orphaned.
Forms remain accessible if someone knows the form_id. Posts still appear
in feeds with a stale `sig_id`.

**Fix:**
In `sig_repo.soft_delete()`, within the same transaction:
1. Soft-delete all forms where `sig_id = $1`.
2. Set `sig_id = NULL` on all posts where `sig_id = $1`.
3. Then soft-delete the SIG itself.

---

### 3.2 Category Deletion Does Not Handle Associated Posts

**Difficulty: Beginner**
**File:** `app/repositories/category_repo.py`

**Problem:**
Deleting a category leaves posts with a dangling `category_id` foreign key.
Depending on the FK constraint, this may block deletion or silently orphan.

**Fix:**
Before deleting, set `category_id = NULL` on all posts in that category:
```sql
UPDATE posts SET category_id = NULL WHERE category_id = $1;
DELETE FROM categories WHERE id = $1;
```

---

### 3.3 SIG Leave Allows Orphaning When Last Admin Is Deleted User

**Difficulty: Intermediate**
**File:** `app/services/sig.py`

**Problem:**
`leave_sig()` checks `admin_count` to prevent the last admin from leaving.
However, if some admins are deleted (soft-deleted) users, `admin_count`
may overcount. A non-deleted admin could leave, thinking another admin
exists, but that admin is actually a deleted account.

**Fix:**
Change the admin count query to exclude deleted users:
```sql
SELECT COUNT(*) FROM sig_members
WHERE sig_id = $1 AND role IN ('ADMIN', 'SUB_ADMIN')
  AND user_id IN (SELECT id FROM users WHERE is_deleted = false)
```

---

### 3.4 Form Response Race Condition

**Difficulty: Intermediate**
**File:** `app/services/form.py:155-156`

**Problem:**
When submitting a form response, the service checks if the form exists
and if `max_respondents` has been reached. However, between the check and
the insert, another user could submit, exceeding the limit. Also, the form
could be deleted between check and insert.

**Fix:**
Use `SELECT ... FOR UPDATE` on the form row within the transaction, and
re-check `is_deleted` and respondent count after acquiring the lock.

---

## Section 4: Missing Features

---

### 4.1 VirusTotal Integration Completion

**Difficulty: Advanced**
**Files:** `app/tasks/virustotal.py`, new `app/models/file_scan.py`,
new `app/repositories/file_scan_repo.py`, `app/api/v1/endpoints/files.py`

**Background:**
The VirusTotal scan task exists but results are fire-and-forget. Scan
results are not stored, and malicious files can still be downloaded via
presigned URLs.

**Implementation Plan:**
1. Create a `file_scans` table (columns: `id`, `file_key`, `status`
   enum pending/clean/malicious, `scan_id`, `created_at`, `updated_at`).
2. Create the Alembic migration.
3. Create `file_scan_repo.py` with `insert()`, `find_by_key()`,
   `update_status()`.
4. Modify `virustotal.py` to update the scan record when results arrive.
5. Add `GET /files/{key}/scan-status` endpoint.
6. Modify `generate_presigned_url()` to reject keys flagged as malicious.

> **Frontend dependency:** This unblocks frontend task 1.6 (VirusTotal
> File Safety Indicator) in `FRONTEND_CONTRIBUTOR_GUIDE.md`.

---

### 4.2 Bulk Operations Endpoints

**Difficulty: Intermediate**
**Files:** `app/api/v1/endpoints/posts.py`, `app/api/v1/endpoints/users.py`,
`app/schemas/post.py`, `app/schemas/user.py`

**Implementation Plan:**
1. Add `BulkDeletePostsRequest` schema with `post_ids: list[uuid.UUID]`
   (max 50 items).
2. Add `DELETE /api/v1/posts/bulk` endpoint (SUPER_ADMIN/ADMIN only).
   Calls `post_repo.soft_delete()` in a loop within a single transaction.
3. Add `BulkRoleChangeRequest` schema with `user_ids: list[uuid.UUID]`
   and `role: str`.
4. Add `PUT /api/v1/users/bulk-role` endpoint (SUPER_ADMIN only).
   Validate role enum, then update in a single transaction.
5. Add audit log entries for each bulk action.

> **Frontend dependency:** This unblocks frontend task 2.6 (Admin Bulk
> Operations UI) in `FRONTEND_CONTRIBUTOR_GUIDE.md`.

---

### 4.3 Reports Endpoint Pagination

**Difficulty: Beginner**
**Files:** `app/api/v1/endpoints/reports.py`, `app/services/report.py`,
`app/repositories/report_repo.py`

**Problem:**
`GET /api/v1/reports` returns all reports without pagination. This will
cause performance issues as the platform grows.

**Fix:**
Add `page: int = Query(1, ge=1)` and `page_size: int = Query(20, ge=1, le=100)`
parameters. Use `LIMIT/OFFSET` in the repo query and return total count
using `COUNT(*) OVER()`.

> **Frontend dependency:** This unblocks frontend task 2.7 (Admin Reports
> Pagination) in `FRONTEND_CONTRIBUTOR_GUIDE.md`.

---

### 4.4 Audit Log Date Filtering

**Difficulty: Beginner**
**Files:** `app/services/audit.py`, `app/api/v1/endpoints/audit.py`

**Problem:**
`list_audit_logs()` has no date range filtering. Admins cannot query logs
for a specific time period without scrolling through all entries.

**Fix:**
Add optional `date_from` and `date_to` query parameters. In the repo
query, add:
```sql
AND created_at >= $X::timestamptz  -- if date_from provided
AND created_at <= $Y::timestamptz  -- if date_to provided
```

---

### 4.5 Invite Code Revocation

**Difficulty: Beginner**
**Files:** `app/api/v1/endpoints/invite_codes.py`,
`app/repositories/invite_code_repo.py`

**Problem:**
Admins cannot revoke a specific invite code. If a code is being abused,
the only option is to delete all codes or wait for it to expire.

**Fix:**
Add `DELETE /api/v1/invite-codes/{code_id}` endpoint (SUPER_ADMIN/ADMIN
only). Soft-delete or hard-delete the code from the database.

---

### 4.6 Single Category Endpoint

**Difficulty: Beginner**
**Files:** `app/api/v1/endpoints/categories.py`,
`app/repositories/category_repo.py`

**Problem:**
Only `GET /categories` (list all) exists. There is no
`GET /categories/{id}` endpoint. Clients must filter the full list to find
a single category.

**Fix:**
Add a simple endpoint:
```python
@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: uuid.UUID):
    category = await category_repo.find_by_id(category_id)
    if not category:
        raise HTTPException(404, "Category not found.")
    return CategoryResponse(**category)
```

---

## Section 5: Infrastructure & Resilience

---

### 5.1 Cross-Platform Celery Task Compatibility

**Difficulty: Intermediate**
**File:** `app/tasks/form_export.py`

**Problem:**
`form_export.py` uses `asyncio.run()` inside a Celery sync worker. This
can fail on Windows (default `ProactorEventLoop` may conflict) or when a
loop is already running (nested event loop error).

**Fix:**
Use `asgiref.sync.async_to_sync` or a dedicated helper that creates a
new event loop in a thread:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def run_async(coro):
    """Run an async coroutine from a sync Celery task, cross-platform."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()
```
Apply this pattern to all Celery tasks that call async code.

---

### 5.2 Rate Limits via Environment Variables

**Difficulty: Beginner**
**File:** `app/core/constants.py`

**Problem:**
All rate limits are hardcoded tuples (e.g., `RATE_LIMIT_COMMENT = (30, 60)`).
Different deployment environments (staging, production) may need different
limits, but changing them requires a code change and redeployment.

**Fix:**
Read from environment variables with fallback defaults:
```python
import os

def _rate_limit(env_key: str, default_max: int, default_window: int) -> tuple[int, int]:
    max_val = int(os.getenv(f"RATE_LIMIT_{env_key}_MAX", str(default_max)))
    window = int(os.getenv(f"RATE_LIMIT_{env_key}_WINDOW", str(default_window)))
    return (max_val, window)

RATE_LIMIT_COMMENT = _rate_limit("COMMENT", 30, 60)
RATE_LIMIT_POST = _rate_limit("POST", 10, 86400)
RATE_LIMIT_CAPTCHA = _rate_limit("CAPTCHA", 20, 60)
RATE_LIMIT_FILE_UPLOAD = _rate_limit("FILE_UPLOAD", 10, 60)
RATE_LIMIT_FORM_SUBMIT = _rate_limit("FORM_SUBMIT", 5, 60)
```
Document the available environment variables in `.env.example`.

---

### 5.3 Event Bus Bounded Retry Mechanism

**Difficulty: Intermediate**
**Files:** `app/core/event_bus.py`

**Problem:**
Failed events are persisted to Redis but never retried. They accumulate
indefinitely, wasting Redis memory. There is no mechanism to recover from
transient failures (e.g., temporary database unavailability).

**Fix:**
1. Add a `retry_count` field to the persisted event payload.
2. Create a periodic Celery Beat task (e.g., every 5 minutes) that:
   - Reads failed events from the Redis list.
   - Re-dispatches events where `retry_count < MAX_RETRIES` (e.g., 3).
   - Increments `retry_count` on each attempt.
   - Uses exponential backoff: delay = `2^retry_count` seconds.
   - Events exceeding `MAX_RETRIES` are logged at ERROR level and removed
     from the queue.
3. Add a Redis key TTL (e.g., 24 hours) as a safety net so old events
   are automatically cleaned up even if the retry task is not running.

---

### 5.4 WebSocket Guest Timeout Reset on Activity

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/ws.py:50-60`

**Problem:**
Guest WebSocket connections have an absolute 45-minute timeout. Active
guests (sending messages, clicking) are forcibly disconnected after 45
minutes regardless of activity.

**Fix:**
Track `last_activity` timestamp. On each received message or PONG, update
`last_activity`. Change the timeout check from:
```python
if time.time() - connect_time > GUEST_TIMEOUT:
```
to:
```python
if time.time() - last_activity > GUEST_TIMEOUT:
```

---

### 5.5 WebSocket Redis Pub/Sub Error Recovery

**Difficulty: Intermediate**
**File:** `app/api/v1/endpoints/ws.py:162-198`

**Problem:**
The Redis Pub/Sub subscriber has no error recovery. If the Redis connection
drops or the subscriber coroutine crashes, WebSocket broadcasts stop
silently. No reconnection is attempted.

**Fix:**
Wrap the subscriber loop in a retry wrapper:
```python
async def _subscribe_with_retry():
    while True:
        try:
            await _subscribe_to_redis()
        except Exception:
            logger.error("Redis Pub/Sub subscriber crashed, reconnecting in 5s", exc_info=True)
            await asyncio.sleep(5)
```
Use exponential backoff (5s, 10s, 20s, capped at 60s) for reconnection
attempts. Reset the backoff on successful reconnection.

---

### 5.6 Data Integrity: SIG Deletion Cascade

**Difficulty: Intermediate**
**Files:** `app/repositories/sig_repo.py`, `app/repositories/form_repo.py`,
`app/repositories/post_repo.py`

**Problem:**
When a SIG is soft-deleted:
- Forms belonging to the SIG remain active and accessible.
- Posts with `sig_id` pointing to the deleted SIG show stale references.

**Fix:**
In `sig_repo.soft_delete()`, within a single transaction:
```sql
-- 1. Soft-delete all forms in the SIG
UPDATE forms SET is_deleted = true, updated_at = NOW() WHERE sig_id = $1 AND is_deleted = false;

-- 2. Nullify sig_id on all posts
UPDATE posts SET sig_id = NULL, updated_at = NOW() WHERE sig_id = $1;

-- 3. Soft-delete the SIG
UPDATE sigs SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND is_deleted = false;
```

---

### 5.7 Data Integrity: Category Deletion Cascade

**Difficulty: Beginner**
**File:** `app/repositories/category_repo.py`

**Fix:**
Before deleting a category, nullify references:
```sql
UPDATE posts SET category_id = NULL WHERE category_id = $1;
DELETE FROM categories WHERE id = $1;
```

---

### 5.8 Data Integrity: SIG Leave Admin Validation

**Difficulty: Beginner**
**File:** `app/services/sig.py`

**Fix:**
Change the admin count query to exclude soft-deleted users:
```sql
SELECT COUNT(*) FROM sig_members sm
JOIN users u ON sm.user_id = u.id
WHERE sm.sig_id = $1 AND sm.role IN ('ADMIN', 'SUB_ADMIN')
  AND u.is_deleted = false
```

---

## Appendix: Testing & Development

### Running Tests

```bash
# Unit tests (146 tests)
cd backend && python -m pytest tests/ -v

# Integration tests (requires Docker — PostgreSQL + Redis)
cd backend && docker compose -f docker-compose.test.yml up -d
INTEGRATION_TEST=1 python -m pytest tests/integration/ -v
docker compose -f docker-compose.test.yml down
```

### Mock Path Convention

When writing unit tests, mock at the point of use:

| Service type | Mock path |
|---|---|
| Repo-delegating service | `app.repositories.X_repo.get_pool` |
| Transactional service | `app.services.X.get_pool` |
| Endpoint-level import | `app.api.v1.endpoints.X.function_name` |

Rate-limited endpoints require `check_rate_limit` to be mocked as well.

### Adding a New Feature Checklist

1. **Schema** — Define request/response in `app/schemas/`.
2. **Repository** — Add SQL queries in `app/repositories/`.
3. **Service** — Add business logic in `app/services/`.
4. **Endpoint** — Wire up route in `app/api/v1/endpoints/`.
5. **Tests** — Add unit tests in `tests/` following mock path convention.
6. **Migration** — If schema changes DB, add Alembic migration in
   `alembic/versions/`.

### Key Configuration

| Setting | Location | Current value |
|---|---|---|
| DB pool | `app/core/database.py` | min=10, max=30, timeout=60s |
| Rate limits | `app/core/constants.py` | Various (moving to env vars) |
| CSRF | `app/core/csrf.py` | Double-submit cookie pattern |
| Auth | `app/core/deps.py` | HttpOnly cookie + Bearer fallback |
| Event bus | `app/core/event_bus.py` | In-process async, MAX_RETRIES=2 |
