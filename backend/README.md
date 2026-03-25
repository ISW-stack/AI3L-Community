# Backend — AI3L Community Platform

This document covers the backend application architecture, development workflow, and conventions for the AI3L Community Platform. The backend is a Python async web service built with FastAPI, PostgreSQL (via asyncpg), Redis, and Celery.

---

## Table of Contents

- [Technology Stack](#technology-stack)
- [Directory Structure](#directory-structure)
- [Architecture Overview](#architecture-overview)
- [Core Modules](#core-modules)
- [Layer-by-Layer Guide](#layer-by-layer-guide)
  - [API Endpoints](#api-endpoints)
  - [Service Layer](#service-layer)
  - [Repository Layer](#repository-layer)
  - [Converter Layer](#converter-layer)
  - [Event Bus](#event-bus)
- [Error Handling](#error-handling)
- [Authentication and Authorization](#authentication-and-authorization)
- [CSRF Protection](#csrf-protection)
- [Rate Limiting](#rate-limiting)
- [File Validation](#file-validation)
- [Background Tasks](#background-tasks)
- [Testing](#testing)
- [Code Style](#code-style)
- [Development Setup](#development-setup)
- [Adding a New Feature](#adding-a-new-feature)

---

## Technology Stack

| Purpose | Library |
|---|---|
| Web framework | FastAPI |
| ASGI server | Uvicorn with uvloop |
| Async PostgreSQL driver | asyncpg |
| Schema migrations | Alembic |
| Validation and serialization | Pydantic v2 |
| Task queue | Celery |
| Queue broker and cache | Redis (aioredis) |
| Object storage | boto3 (MinIO / S3) |
| Password hashing | argon2-cffi via passlib |
| Token signing | PyJWT |
| HTML sanitization | nh3 |
| PDF sanitization | pikepdf (C++ qpdf engine) |
| CAPTCHA generation | captcha + Pillow |
| Structured logging | Loguru |
| Error tracking | Sentry SDK |
| APM tracing | ddtrace (Datadog) |

---

## Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/       Route handlers (one file per domain)
│   │       │   ├── about.py
│   │       │   ├── auth.py
│   │       │   ├── users.py
│   │       │   ├── posts.py
│   │       │   ├── comments.py
│   │       │   ├── sigs.py
│   │       │   ├── forms.py
│   │       │   ├── files.py
│   │       │   ├── notifications.py
│   │       │   ├── dm.py
│   │       │   ├── reports.py
│   │       │   ├── applications.py
│   │       │   ├── categories.py
│   │       │   ├── admin.py
│   │       │   ├── tasks.py
│   │       │   ├── health.py
│   │       │   └── ws.py        WebSocket endpoint
│   │       └── router.py        Registers all endpoint routers
│   ├── core/
│   │   ├── config.py            Pydantic Settings (reads .env)
│   │   ├── constants.py         Domain-wide constants
│   │   ├── database.py          asyncpg connection pool lifecycle
│   │   ├── deps.py              FastAPI dependency functions
│   │   ├── errors.py            AppError base class and error codes
│   │   ├── security.py          JWT creation and validation
│   │   ├── rate_limit.py        Application-level Redis rate limiter
│   │   ├── redis.py             Redis client lifecycle
│   │   ├── storage.py           MinIO/S3 client wrapper
│   │   ├── async_storage.py     Async MinIO upload/download helpers
│   │   ├── file_validation.py   Magic number MIME type verification
│   │   ├── csrf.py              CSRF middleware and token validation
│   │   ├── event_bus.py         Lightweight async publish/subscribe
│   │   └── logging.py           Loguru configuration
│   ├── converters/              Model-to-Pydantic-schema transformers
│   │   ├── user_converter.py
│   │   ├── post_converter.py
│   │   ├── comment_converter.py
│   │   ├── sig_converter.py
│   │   ├── form_converter.py
│   │   ├── notification_converter.py
│   │   ├── dm_converter.py
│   │   ├── application_converter.py
│   │   └── report_converter.py
│   ├── repositories/            Database query functions (asyncpg)
│   │   ├── user_repo.py
│   │   ├── auth_repo.py
│   │   ├── post_repo.py
│   │   ├── comment_repo.py
│   │   ├── category_repo.py
│   │   ├── sig_repo.py
│   │   ├── form_repo.py
│   │   ├── notification_repo.py
│   │   ├── dm_repo.py
│   │   ├── report_repo.py
│   │   ├── application_repo.py
│   │   ├── audit_repo.py
│   │   ├── dashboard_repo.py
│   │   ├── invite_code_repo.py
│   │   └── privacy_repo.py
│   ├── services/                Business logic
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── post.py
│   │   ├── comment.py
│   │   ├── sig.py
│   │   ├── form.py
│   │   ├── notification.py
│   │   ├── dm.py
│   │   ├── report.py
│   │   ├── application.py
│   │   ├── audit.py
│   │   ├── category.py
│   │   ├── dashboard.py
│   │   ├── invite_code.py
│   │   ├── captcha.py
│   │   └── privacy_consent.py
│   ├── schemas/                 Pydantic request and response models
│   ├── models/                  SQLAlchemy table definitions (for Alembic)
│   ├── middleware/              Custom Starlette middleware
│   ├── tasks/                   Celery task definitions (including dm_cleanup.py)
│   ├── celery_app.py            Celery application instance
│   ├── event_handlers.py        Event bus subscriber registrations
│   └── main.py                  FastAPI app factory and lifespan
├── alembic/
│   ├── versions/                Migration scripts
│   └── env.py                   Alembic environment configuration
├── tests/
│   ├── conftest.py              Shared fixtures (mock pool, mock Redis)
│   ├── test_auth_endpoints.py
│   ├── test_user_endpoints.py
│   ├── test_posts.py
│   ├── test_sigs.py
│   ├── test_categories.py
│   ├── test_files.py
│   ├── test_audit.py
│   ├── test_errors.py
│   ├── test_phase9.py
│   ├── test_privacy_consent.py
│   ├── test_users.py
│   ├── test_ws.py               WebSocket endpoint and ticket auth tests
│   ├── test_event_bus.py        Event bus pub/sub and retry logic tests
│   ├── test_converters.py       All converter layer unit tests
│   ├── test_core_modules.py     Core module tests (config, security, rate limiting)
│   ├── test_celery_tasks.py     Celery task unit tests
│   ├── test_dm.py               Direct message tests (repo, service, endpoints, Celery, events, converters)
│   └── integration/             Integration tests (require INTEGRATION_TEST=1 + Docker)
├── Dockerfile
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## Architecture Overview

Requests flow through four distinct layers. Each layer has a single, well-defined responsibility.

```
HTTP Request
    |
    v
[API Endpoint]      app/api/v1/endpoints/
    |  - Validates request schema (Pydantic)
    |  - Extracts dependencies (auth, DB pool, Redis)
    |  - Delegates to service layer
    v
[Service]           app/services/
    |  - Enforces business rules and authorization
    |  - Calls repositories for data access
    |  - Calls converters to build response schemas
    |  - Publishes domain events to the event bus
    v
[Repository]        app/repositories/
    |  - Contains all asyncpg SQL queries
    |  - Returns raw asyncpg Record objects
    |  - No business logic, no schema coupling
    v
[Database]          PostgreSQL via asyncpg connection pool
```

The converter layer sits between the repository and service layers. Converters transform asyncpg `Record` objects into Pydantic response schemas, keeping type conversion centralized and off the service layer.

The event bus decouples side-effects (sending notifications, writing audit log entries) from the primary service call. Handlers are registered in `app/event_handlers.py` and execute asynchronously after the main operation completes.

---

## Core Modules

### `app/core/config.py`

A `pydantic_settings.BaseSettings` subclass. All environment variables are declared here with their types and defaults. Access configuration anywhere via the `settings` singleton:

```python
from app.core.config import settings

print(settings.DATABASE_URL)
print(settings.REDIS_URL)
```

### `app/core/database.py`

Manages the `asyncpg` connection pool lifecycle. The pool is created during the FastAPI lifespan startup and closed on shutdown. Endpoints receive a connection via the `get_db` dependency.

### `app/core/deps.py`

FastAPI dependency functions injected into endpoints:

| Dependency | Description |
|---|---|
| `get_db` | Yields an asyncpg connection from the pool |
| `get_redis` | Returns the Redis client instance |
| `get_current_user` | Validates JWT and Redis session, returns user payload |
| `require_role(roles)` | Extends `get_current_user` with role enforcement |
| `get_optional_user` | Same as `get_current_user` but returns None if unauthenticated |

### `app/core/errors.py`

Defines `AppError`, a custom exception that carries a structured error code, HTTP status, and message. All application-level errors subclass `AppError`. FastAPI's exception handler converts `AppError` instances to consistent JSON responses:

```json
{
  "code": "AUTH_003",
  "message": "Invalid credentials.",
  "status": 401
}
```

### `app/core/security.py`

JWT creation (`create_access_token`) and validation (`decode_access_token`). Tokens contain the user ID, role, and a unique `jti` (JWT ID) used for Redis session tracking and blacklisting.

### `app/core/event_bus.py`

A minimal publish/subscribe system backed by `asyncio`. Services publish typed events and handlers registered in `event_handlers.py` run in the background without blocking the response.

```python
# Publishing an event from a service
await event_bus.publish("post.created", {"post_id": post_id, "author_id": user_id})

# Subscribing in event_handlers.py
@event_bus.subscribe("post.created")
async def on_post_created(data: dict) -> None:
    await notification_service.notify_followers(data["post_id"])
```

### `app/core/file_validation.py`

Reads the first bytes of an uploaded file and compares the magic number signature against a whitelist of allowed file types (PNG, JPEG, PDF, DOCX). Raises `AppError` with code `FILE_001` for mismatches.

### `app/core/csrf.py`

CSRF middleware that verifies the `X-CSRF-Token` request header matches the `csrf_token` cookie on all non-safe HTTP methods. A CSRF token is generated and set as a cookie when a session is established.

### `app/core/rate_limit.py`

Application-level rate limiting using Redis atomic counters with TTL. Used for per-user daily post limits. Returns error code `SYS_429` when a limit is exceeded.

---

## Layer-by-Layer Guide

### API Endpoints

Each file in `app/api/v1/endpoints/` corresponds to one domain. Endpoints are responsible only for:

1. Declaring the route, HTTP method, and response model.
2. Validating the request body against a Pydantic schema.
3. Extracting injected dependencies (current user, DB connection, Redis).
4. Calling the appropriate service function.
5. Returning the service result.

Endpoints contain no business logic. Example pattern:

```python
@router.post("/posts", response_model=PostResponse, status_code=201)
async def create_post(
    body: PostCreate,
    user: UserPayload = Depends(require_role(["MEMBER", "ADMIN", "SUPER_ADMIN"])),
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PostResponse:
    return await post_service.create_post(db, redis, user, body)
```

### Service Layer

Services in `app/services/` contain all business logic. A service function:

1. Enforces authorization (e.g., only the owner may edit a post).
2. Calls repository functions to query or mutate data.
3. Applies business rules (e.g., daily post limit check).
4. Calls converters to transform raw database rows into response schemas.
5. Publishes domain events for side-effects.

Services do not contain raw SQL. They delegate all database access to repositories.

### Repository Layer

Repositories in `app/repositories/` contain all SQL. Each function accepts an `asyncpg.Connection` and returns either a raw `asyncpg.Record`, a list of records, or a scalar value. No Pydantic schemas are used at this layer.

Example pattern:

```python
# app/repositories/post_repo.py

async def get_post_by_id(
    conn: asyncpg.Connection, post_id: uuid.UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT * FROM posts WHERE id = $1 AND is_deleted = FALSE",
        post_id,
    )
```

By keeping SQL in repositories, it is straightforward to test query logic independently and to swap out database drivers without modifying business logic.

### Converter Layer

Converters in `app/converters/` transform `asyncpg.Record` objects (which are dict-like) into Pydantic response schema instances. This prevents service functions from containing repetitive field-mapping code.

```python
# app/converters/post_converter.py

def to_post_response(row: asyncpg.Record) -> PostResponse:
    return PostResponse(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        author=UserSummary(
            id=row["author_id"],
            display_name=row["author_display_name"],
        ),
        created_at=row["created_at"],
    )
```

### Event Bus

The event bus in `app/core/event_bus.py` decouples services from their side-effects. After a service completes its primary operation, it publishes an event. Registered handlers then execute asynchronously.

All handler registrations live in `app/event_handlers.py`, which is imported once during FastAPI startup. This keeps the service layer clean and makes it easy to add or remove side-effects without touching service code.

---

## Error Handling

All application errors extend `AppError` from `app/core/errors.py`. The base class carries:

- `code`: A string identifier (e.g., `AUTH_001`, `POST_404`, `FILE_001`)
- `message`: Human-readable description
- `status_code`: HTTP status code (default 400)

The FastAPI exception handler converts any unhandled `AppError` to a JSON response. The frontend uses the `code` field to display localized error messages.

Do not raise raw HTTP exceptions (`HTTPException`) from services. Raise an `AppError` subclass instead.

---

## Authentication and Authorization

Authentication is handled by the `get_current_user` dependency in `app/core/deps.py`. It performs two checks:

1. Validates the JWT signature and expiry using `app/core/security.py`.
2. Verifies the token's `jti` exists in Redis (confirming the session is still active and has not been logged out or force-expired).

Authorization is handled by `require_role(roles)`, which wraps `get_current_user` and raises `AppError` if the user's role is not in the allowed list.

Role hierarchy: `GUEST` < `MEMBER` < `ADMIN` < `SUPER_ADMIN`.

---

## CSRF Protection

The CSRF middleware (`app/core/csrf.py`) is mounted on the FastAPI app and runs on all requests. It:

1. Skips safe methods (GET, HEAD, OPTIONS).
2. Reads the `csrf_token` cookie from the request.
3. Reads the `X-CSRF-Token` header from the request.
4. Rejects requests where the two values do not match.

When a session is created (login or guest access), the server generates a CSRF token and sets it as an `HttpOnly=False` cookie so the frontend JavaScript can read it. The frontend must include this value in all mutating requests.

---

## Rate Limiting

The application-level rate limiter (`app/core/rate_limit.py`) uses a Redis counter with a fixed TTL window. Limits are defined in `app/core/constants.py` and applied inline at each endpoint. Key limits:

| Endpoint | Limit | Key |
|---|---|---|
| `POST /auth/login` | 10 / min | per IP |
| `POST /auth/register` | 5 / min | per IP |
| `POST /auth/guest/{code}` | 10 / min | per IP |
| `POST /auth/invite-code` | 5 / hour | per user |
| `GET /auth/invite-code/{code}` | 30 / min | per IP |
| `POST /files/upload/editor` | 10 / min | per user |
| `POST /forms/{id}/submit` | 5 / min | per user |
| `GET /notifications` | 60 / min | per user |
| `DELETE /notifications` | 30 / min | per user |
| `POST /dm/conversations/{id}/messages` | 30 / min | per user |
| `GET /dm/conversations` | 60 / min | per user |

Post creation is additionally limited to 50 posts per user per day (error code `SYS_429`).

Nginx enforces a separate, coarser IP-level rate limit (20 req/s global, 5 writes/min).

---

## File Validation

Before any file is written to MinIO, `app/core/file_validation.py` inspects the first bytes of the uploaded content to verify the magic number. If the detected type does not match the declared content type, the upload is rejected.

Accepted types:

| Extension | MIME Type | Magic Bytes |
|---|---|---|
| `.png` | `image/png` | `\x89PNG` |
| `.jpg` / `.jpeg` | `image/jpeg` | `\xFF\xD8\xFF` |
| `.pdf` | `application/pdf` | `%PDF` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `PK\x03\x04` |

PDF files undergo additional sanitization via pikepdf (backed by the C++ qpdf engine) to strip embedded JavaScript (`/JS`, `/JavaScript`), auto-actions (`/AA`, `/OpenAction`), and other potentially dangerous objects. Corrupted or invalid PDFs are rejected with a `ValueError` before reaching storage.

---

## Background Tasks

Celery workers are defined in `app/celery_app.py`. Tasks are located in `app/tasks/`.

Configured tasks:

| Task | Schedule | Description |
|---|---|---|
| `form_export` | On-demand | Serializes all form responses to CSV and stores the result in Redis. The frontend polls `GET /api/v1/tasks/{task_id}` for completion. |
| `cleanup_dm_expired_files` | Hourly (Beat) | Deletes MinIO DM file attachments older than 3 days and refunds each sender's storage quota. |
| `cleanup_dm_expired_text` | Hourly (Beat) | Deletes DM message text older than 7 days and adjusts each conversation's `total_chars` counter. |

To add a new task:

1. Create a function in `app/tasks/` decorated with `@celery_app.task`.
2. Call `task.delay(...)` or `task.apply_async(...)` from the relevant service.
3. The task result is automatically stored in Redis DB 2.

---

## Testing

### Running tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v --tb=short
```

### Fixtures

All test fixtures are defined in `tests/conftest.py`. Key fixtures:

| Fixture | Description |
|---|---|
| `client` | `httpx.AsyncClient` wrapping the FastAPI app. DB and Redis init calls are patched out. Includes CSRF cookie and header by default. |
| `mock_conn` | `AsyncMock` of an asyncpg connection with `fetchrow`, `fetch`, `fetchval`, `execute`, and `transaction` methods. |
| `mock_pool` | `MagicMock` of an asyncpg pool whose `acquire()` context manager yields `mock_conn`. |
| `mock_redis` | `AsyncMock` of a Redis client with all common methods mocked. |
| `auth_headers` | Factory fixture. Call `auth_headers(role="ADMIN")` to get `(headers_dict, user_id, jti)`. |

### Test strategy

Tests mock all external dependencies (database and Redis) using `unittest.mock.AsyncMock`. This means:

- No running PostgreSQL, Redis, or MinIO is required.
- Tests run fast and deterministically.
- Integration tests for database query logic live in `tests/integration/`. They require the `INTEGRATION_TEST=1` environment variable and a running PostgreSQL and Redis instance (use `docker-compose.test.yml`).

`mock_conn.fetchrow` returns `None` by default. Override it in individual tests:

```python
async def test_get_post(client, mock_pool, mock_conn, auth_headers):
    headers, user_id, _ = auth_headers("MEMBER")
    mock_conn.fetchrow.return_value = {
        "id": uuid.uuid4(),
        "title": "Test post",
        ...
    }
    response = await client.get("/api/v1/posts/some-id", headers=headers)
    assert response.status_code == 200
```

---

## Code Style

The project uses the following linting and formatting tools, all configured in `pyproject.toml`:

| Tool | Purpose | Command |
|---|---|---|
| Black | Code formatter | `black .` |
| isort | Import sorter | `isort .` |
| Flake8 | Linter | `flake8 .` |
| mypy | Static type checker | `mypy app/ --ignore-missing-imports` |

Run all checks:

```bash
black --check .
isort --check-only .
flake8 .
mypy app/ --ignore-missing-imports
```

Auto-format:

```bash
black .
isort .
```

---

## Development Setup

### Option 1: Docker (recommended)

```bash
# From the repository root
docker compose up --build   # first time (builds images)
docker compose up           # subsequent runs
```

The `docker-compose.override.yml` mounts the `backend/` directory into the container and starts Uvicorn with `--reload`, so code changes take effect immediately without rebuilding the image. The `migrate` service runs `alembic upgrade head` automatically before FastAPI starts — no manual migration step is needed.

### Option 2: Local Python environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

You still need PostgreSQL, Redis, and MinIO running. Use Docker Compose for the infrastructure services only:

```bash
# From the repository root
docker compose up -d postgres redis minio
```

Then configure `.env` with `POSTGRES_HOST=localhost`, `REDIS_HOST=localhost`, etc. (matching the override port numbers), and start the server:

```bash
cd backend
uvicorn app.main:app --reload --port 18000
```

---

## Adding a New Feature

This section describes the standard process for adding a new domain (for example, a "bookmarks" feature).

### 1. Create the migration

Add a new Alembic migration that creates the required tables.

```bash
docker compose exec fastapi alembic revision --autogenerate -m "add bookmarks table"
```

Edit the generated file in `alembic/versions/` and verify the schema.

### 2. Define Pydantic schemas

Create `app/schemas/bookmark.py` with request and response models.

### 3. Add the repository

Create `app/repositories/bookmark_repo.py` with all SQL functions. Each function takes an `asyncpg.Connection` and returns raw records.

### 4. Add the converter

Create `app/converters/bookmark_converter.py` to transform records into response schemas.

### 5. Add the service

Create `app/services/bookmark.py`. Call repository functions, apply business rules, and use converters to build the return value.

### 6. Add the endpoint

Create `app/api/v1/endpoints/bookmarks.py`. Register the router in `app/api/v1/router.py`.

### 7. Register event handlers (if applicable)

If the feature should trigger notifications or audit log entries, publish an event from the service and register a handler in `app/event_handlers.py`.

### 8. Write tests

Add `tests/test_bookmarks.py`. Mock `mock_conn.fetchrow` or `mock_conn.fetch` to return test data for each scenario.
