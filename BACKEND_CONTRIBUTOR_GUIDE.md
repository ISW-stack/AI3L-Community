# AI3L Community Backend -- Contributor Task Guide

> **Last Updated:** 2026-03-09
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

## Progress Summary

| # | Task | Status |
|---|------|--------|
| 1.1 | VirusTotal silent error logging | ✅ Done |
| 1.2 | WebSocket send failure logging | ⬜ Pending |
| 2.1 | Schema field length constraints | ✅ Done |
| 2.2 | Post update empty payload check | ⬜ Pending |
| 2.3 | Comment delete cross-validate post_id | ✅ Done |
| 2.4 | Form update SIG ownership check | ⬜ Pending |
| 3.1 | SIG deletion cascade to forms/posts | ✅ Done |
| 3.2 | Category deletion cascade to posts | ⬜ Pending |
| 3.3 | SIG leave excludes deleted admins | ✅ Done |
| 3.4 | Form response race condition | ⬜ Pending |
| 4.1 | VirusTotal integration (DB + endpoint) | ✅ Done |
| 4.2 | Bulk operations endpoints | ✅ Done |
| 4.3 | Reports endpoint pagination | ✅ Done |
| 4.4 | Audit log date range filtering | ⬜ Pending |
| 4.5 | Invite code revocation | ✅ Done |
| 4.6 | Single category GET endpoint | ⬜ Pending |
| 5.1 | Celery cross-platform async | ✅ Done |
| 5.2 | Rate limits via environment variables | ⬜ Pending |
| 5.3 | Event bus periodic retry (Celery Beat) | ⬜ Pending |
| 5.4 | WebSocket guest timeout on activity | ✅ Done |
| 5.5 | WebSocket Redis Pub/Sub reconnection | ✅ Done |
| 6.1 | Invite code race condition (atomic UPDATE) | ✅ Done |
| 6.2 | Editor image expiration (proxy endpoint) | ✅ Done |
| 6.3 | Storage quota TOCTOU bypass (Redis lock) | ✅ Done |

---

## Section 1: Bug Fixes & Error Handling

---

### 1.1 VirusTotal Check Silently Swallows All Errors — ✅ DONE

**File:** `app/api/v1/endpoints/files.py`

Fixed. The VirusTotal scan trigger now distinguishes between `ImportError`
(VirusTotal not configured — silenced) and all other exceptions (logged at
`WARNING` level with full traceback via `exc_info=True`).

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

### 2.1 Schema Fields Missing Length Constraints — ✅ DONE

**Files:** `app/schemas/form.py`, `app/schemas/user.py`, `app/schemas/post.py`

Fixed. All major fields now have `max_length` constraints:
- `form.py`: `placeholder` max_length=500
- `user.py`: `bio` max_length=500, `affiliation` max_length=200, `orcid` max_length=50
- `post.py`: keywords validated with `@field_validator`, each capped at 100 chars

---

### 2.2 Post Update Accepts Empty Payload

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/posts.py`

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

### 2.3 Comment Delete Does Not Cross-Validate `post_id` — ✅ DONE

**File:** `app/repositories/comment_repo.py`

Fixed. The soft-delete SQL includes `AND post_id = $2`, ensuring a comment
can only be deleted when the correct `post_id` is provided.

---

### 2.4 Form Update Does Not Validate SIG Ownership

**Difficulty: Beginner**
**File:** `app/api/v1/endpoints/forms.py`

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

### 3.1 SIG Deletion Does Not Cascade to Forms and Posts — ✅ DONE

**Files:** `app/repositories/sig_repo.py`

Fixed. `sig_repo.soft_delete()` runs three statements in a single
transaction: soft-delete all forms where `sig_id = $1`, set
`is_deleted = true` on all posts where `sig_id = $1`, then soft-delete
the SIG itself.

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

### 3.3 SIG Leave Allows Orphaning When Last Admin Is Deleted User — ✅ DONE

**File:** `app/repositories/sig_repo.py`

Fixed. The admin count query joins to `users` and filters
`u.is_deleted = false`, so soft-deleted accounts are not counted as
active admins.

---

### 3.4 Form Response Race Condition

**Difficulty: Intermediate**
**File:** `app/services/form.py`

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

### 4.1 VirusTotal Integration Completion — ✅ DONE

**Files:** `app/tasks/virustotal.py`, `app/repositories/file_scan_repo.py`,
`app/api/v1/endpoints/files.py`,
`alembic/versions/k1l2m3n4o5p6_add_file_scans_table.py`

Done. Full DB-backed VirusTotal scan flow is implemented:
- `file_scans` table with `status` enum (pending/clean/malicious),
  `file_key`, `scan_id`, `created_at`, `updated_at`.
- `file_scan_repo.py` with `insert()`, `find_by_key()`, `update_status()`.
- `virustotal.py` task now persists scan results to the DB.
- `GET /files/scan-status/{key}` endpoint returns current scan status.
- `serve_file()` in `files.py` returns HTTP 451 for malicious files.

> **Frontend:** Task 1.6 (VirusTotal File Safety Indicator) is fully
> implemented in both TiptapEditor (upload-time polling) and
> PostDetailView (read-time overlay for malicious files).

---

### 4.2 Bulk Operations Endpoints — ✅ DONE

**Files:** `app/api/v1/endpoints/posts.py`, `app/api/v1/endpoints/users.py`

Done. The following endpoints are implemented:
- `DELETE /api/v1/posts/bulk` — soft-deletes up to 50 posts (ADMIN+)
- `PUT /api/v1/users/bulk-role` — changes role for up to 50 users (SUPER_ADMIN)

Both run in a single transaction and write audit log entries.

---

### 4.3 Reports Endpoint Pagination — ✅ DONE

**Files:** `app/api/v1/endpoints/reports.py`, `app/repositories/report_repo.py`

Done. `GET /api/v1/reports` accepts `page` and `page_size` query
parameters and returns `total`, `total_pages`, and `reports` in the
response body.

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

### 4.5 Invite Code Revocation — ✅ DONE

**File:** `app/api/v1/endpoints/admin.py`

Done. `DELETE /api/v1/admin/invite-codes/{code_id}` lets SUPER_ADMIN or
ADMIN hard-delete a specific invite code.

---

### 4.6 Single Category GET Endpoint

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
@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: uuid.UUID):
    category = await category_repo.find_by_id(category_id)
    if not category:
        raise HTTPException(404, "Category not found.")
    return CategoryResponse(**category)
```

---

## Section 5: Infrastructure & Resilience

---

### 5.1 Cross-Platform Celery Task Compatibility — ✅ DONE

**File:** `app/tasks/form_export.py`

Fixed. Async coroutines are run inside a `ThreadPoolExecutor` with a
dedicated `asyncio.run()` call, which is safe on all platforms.

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

### 5.3 Event Bus Periodic Retry (Celery Beat)

**Difficulty: Intermediate**
**Files:** `app/core/event_bus.py`, `app/celery_app.py`

**Background:**
Failed events are persisted to a Redis list with `retry_count`. However,
there is no background task to retry them. They accumulate indefinitely.

**Fix:**
Create a periodic Celery Beat task (e.g., every 5 minutes) that:
1. Reads failed events from the Redis list.
2. Re-dispatches events where `retry_count < MAX_RETRIES` (e.g., 3).
3. Increments `retry_count` on each attempt.
4. Logs at ERROR and removes events that have exceeded `MAX_RETRIES`.
5. Apply a Redis key TTL (24h) as a safety net.

---

### 5.4 WebSocket Guest Timeout Reset on Activity — ✅ DONE

**File:** `app/api/v1/endpoints/ws.py`

Fixed. `last_activity` is updated on each received message. The 45-minute
timeout now measures inactivity rather than total connection time.

---

### 5.5 WebSocket Redis Pub/Sub Error Recovery — ✅ DONE

**File:** `app/api/v1/endpoints/ws.py`

Fixed. The Redis Pub/Sub subscriber runs inside a reconnection wrapper
that catches crashes, logs the error, and retries after an increasing
delay (up to 60 seconds).

---

## Section 6: Concurrency & Architecture Fixes (Completed 2026-03-03)

These were identified by systemic analysis and have all been fixed.

---

### 6.1 Invite Code Race Condition — ✅ DONE

**File:** `app/services/auth.py`

**Problem:** The `UPDATE invite_codes` in `register_new_user()` did not
include `AND consumed_at IS NULL`. Two concurrent registration requests
using the same code could both succeed.

**Fix:** Added `AND consumed_at IS NULL` to the UPDATE statement and
checks `result == "UPDATE 1"`. If the UPDATE affects 0 rows (code already
consumed), the transaction is rolled back and a `ValueError` is raised,
which the endpoint maps to HTTP 400.

---

### 6.2 Editor Images Expire After 7 Days — ✅ DONE

**Files:** `app/api/v1/endpoints/files.py`, `app/core/storage.py`,
`app/core/async_storage.py`

**Problem:** Editor-uploaded images were stored as 7-day presigned URLs
embedded directly in post HTML. After expiry, images permanently broke
for all readers.

**Fix:** Added `GET /api/v1/files/content/{key:path}` proxy endpoint that
streams file content from MinIO. Editor-uploaded files are now accessible
to any authenticated user. The upload response now returns the stable
proxy URL (`/api/v1/files/content/{key}`) instead of a presigned URL.

---

### 6.3 Storage Quota TOCTOU Bypass — ✅ DONE

**Files:** `app/api/v1/endpoints/files.py`, `app/services/user.py`

**Problem:** Concurrent upload requests all passed the quota check before
any upload completed, allowing users to burst past the 1 GB limit.

**Fix:** A per-user Redis lock (`upload_lock:{user_id}`, 120s TTL, NX
semantics) wraps the quota check + upload block in both the editor upload
endpoint and the avatar upload service. Concurrent uploads from the same
user receive HTTP 429.

---

## Appendix: Testing & Development

### Running Tests

```bash
# Unit tests (525 tests)
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
| Rate limits | `app/core/constants.py` | Hardcoded (pending 5.2) |
| CSRF | `app/core/csrf.py` | Double-submit cookie pattern |
| Auth | `app/core/deps.py` | HttpOnly cookie + Bearer fallback |
| Event bus | `app/core/event_bus.py` | In-process async, MAX_RETRIES=2, Redis persistence |
| Upload lock | Redis | `upload_lock:{user_id}`, 120s TTL, NX |
