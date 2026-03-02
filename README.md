# AI3L Community Platform

A full-stack community platform built for academic groups and special interest groups (SIGs). It provides a discussion forum, survey and form system, real-time notifications, file hosting, and a complete admin suite — all containerized with Docker Compose.

---

## Table of Contents

- [Technology Stack](#technology-stack)
- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Authentication System](#authentication-system)
- [Rate Limiting](#rate-limiting)
- [File Storage](#file-storage)
- [Real-Time Notifications](#real-time-notifications)
- [Background Tasks](#background-tasks)
- [Admin Features](#admin-features)
- [CI/CD Pipeline](#cicd-pipeline)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Scripts](#scripts)
- [Production Deployment](#production-deployment)
- [Security Notes](#security-notes)
- [Contributing](#contributing)

---

## Technology Stack

### Backend

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | FastAPI |
| Async DB driver | asyncpg |
| Schema migrations | Alembic |
| Validation | Pydantic v2 |
| Task queue | Celery + Redis |
| Password hashing | Argon2 (via passlib) |
| Token signing | PyJWT |
| Object storage | boto3 (S3-compatible, MinIO) |
| HTML sanitization | nh3 |
| PDF handling | pypdf |
| CAPTCHA | captcha + Pillow |
| Structured logging | Loguru |
| Error tracking | Sentry SDK |
| APM | ddtrace (Datadog) |

### Frontend

| Component | Technology |
|---|---|
| Framework | Vue 3 (Composition API) |
| Language | TypeScript |
| Build tool | Vite 6 |
| CSS framework | Tailwind CSS v4 |
| State management | Pinia |
| Routing | Vue Router 4 |
| Rich text editor | TipTap 3 |
| HTTP client | Axios |
| HTML sanitization | DOMPurify |
| Icon library | Lucide Vue Next |
| Font | Inter Variable (@fontsource-variable/inter) |

### Infrastructure

| Component | Technology |
|---|---|
| Database | PostgreSQL 15 |
| Cache / queue broker | Redis 7 |
| Object storage | MinIO |
| Reverse proxy | Nginx 1.25 |
| Containerization | Docker Compose |
| Monitoring (optional) | Datadog Agent |

---

## Architecture Overview

```
Browser
  |
  | :3000 (HTTP) / :3443 (HTTPS)
  v
Nginx (reverse proxy, TLS termination, rate limiting)
  |-- /api/v1/ws  --> FastAPI (WebSocket)
  |-- /api/       --> FastAPI (HTTP, port 8000)
  |-- /           --> Static files (Vue SPA build)
       |
       v
   FastAPI :8000
       |-- asyncpg --> PostgreSQL :5432
       |-- aioredis --> Redis :6379
       |-- boto3   --> MinIO :9000
       |-- Celery tasks --> Redis broker (DB 1)
       |-- Celery results --> Redis (DB 2)
```

All services communicate over a private Docker bridge network (`ai3l-network`). Only Nginx exposes ports to the host (`3000` for HTTP, `3443` for HTTPS). The backend, database, Redis, and MinIO are not directly reachable from outside the container network.

### Backend Layer Architecture

```
HTTP Request
  |
  v
API Endpoint (app/api/v1/endpoints/)
  |
  v
Service Layer (app/services/)
  |-- Repository Layer (app/repositories/) --> Database
  |-- Converter Layer (app/converters/)    --> Pydantic Schemas
  |-- Event Bus (app/core/event_bus.py)    --> Async side-effects
```

See `backend/README.md` for detailed backend architecture documentation.

---

## Repository Structure

```
AI3L-Community/
├── backend/                  FastAPI application
│   ├── app/
│   │   ├── api/v1/endpoints/ Route handlers
│   │   ├── core/             Config, DB, security, middleware utilities
│   │   ├── converters/       Model-to-schema transformation
│   │   ├── repositories/     Database query layer
│   │   ├── services/         Business logic
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── models/           SQLAlchemy ORM models
│   │   └── tasks/            Celery task definitions
│   ├── alembic/              Database migrations
│   └── tests/                Pytest test suite
├── frontend/                 Vue 3 application
│   ├── src/
│   │   ├── api/              Axios API modules
│   │   ├── components/       Shared UI components
│   │   │   └── base/         Design system base components
│   │   ├── composables/      Reusable Vue composables
│   │   ├── router/           Vue Router configuration
│   │   ├── stores/           Pinia state stores
│   │   ├── types/            TypeScript type definitions
│   │   ├── utils/            Pure utility functions
│   │   └── views/            Page-level route components
├── nginx/                    Nginx configuration
├── scripts/                  Operational shell scripts
├── docker-compose.yml        Production service definitions
├── docker-compose.override.yml  Development overrides
└── .env.example              Environment variable template
```

---

## Getting Started

### Prerequisites

- Docker Engine 24 or later
- Docker Compose v2
- 8 GB RAM recommended (all services combined)

### 1. Clone and configure

```bash
git clone <repository-url>
cd AI3L-Community
cp .env.example .env
```

Open `.env` and replace every `changeme_*` value with a strong random secret before proceeding.

### 2. Initialize MinIO bucket

```bash
./scripts/init-minio.sh
```

This creates the upload bucket and applies the required access policy. Run this once after the first `docker compose up`.

### 3. Start all services

```bash
docker compose up -d
```

Docker Compose starts services in dependency order. FastAPI waits for PostgreSQL, Redis, and MinIO to pass health checks before starting. Nginx waits for FastAPI. Alembic migrations run automatically on FastAPI startup.

### 4. Access the application

| Service | URL |
|---|---|
| Web application | http://localhost:3000 |
| API docs (development only) | http://localhost:3000/api/docs |
| MinIO console | http://localhost:9001 |

A super admin account is created automatically on first startup using `SUPER_ADMIN_USERNAME` and `SUPER_ADMIN_PASSWORD` from `.env`.

### Stopping and cleanup

```bash
# Stop containers, preserve volumes
docker compose down

# Stop containers and delete all data volumes
docker compose down -v
```

---

## Local Development

For active development, run the frontend Vite dev server separately from the Docker backend services. This gives you hot module replacement on the frontend while the backend services run in Docker.

### Start backend services

```bash
docker compose up -d
```

This starts FastAPI (port 18000), PostgreSQL (port 15432), Redis (port 16379), and MinIO (ports 19000/19001) via the `docker-compose.override.yml` configuration, which also mounts the backend source directory for live code reloading.

### Start the frontend dev server

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on port 15173 and proxies all `/api` requests to FastAPI at `http://localhost:18000`.

| Service | Local URL |
|---|---|
| Frontend (Vite) | http://localhost:15173 |
| FastAPI (direct) | http://localhost:18000 |
| FastAPI Swagger UI | http://localhost:18000/api/docs |
| MinIO console | http://localhost:19001 |
| PostgreSQL | localhost:15432 |
| Redis | localhost:16379 |

---

## Environment Variables

Copy `.env.example` to `.env` and set all values. All `changeme_*` defaults must be replaced before running in any environment.

### PostgreSQL

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `ai3l` | Database user |
| `POSTGRES_PASSWORD` | — | Database password |
| `POSTGRES_DB` | `ai3l_community` | Database name |
| `POSTGRES_HOST` | `postgres` | Hostname (Docker service name) |
| `POSTGRES_PORT` | `5432` | Port |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Hostname |
| `REDIS_PORT` | `6379` | Port |
| `REDIS_PASSWORD` | — | Redis `requirepass` value |

### FastAPI

| Variable | Default | Description |
|---|---|---|
| `FASTAPI_ENV` | `development` | `development` or `production` |
| `FASTAPI_DEBUG` | `true` | Enables Swagger UI and verbose errors |
| `FASTAPI_HOST` | `0.0.0.0` | Bind address |
| `FASTAPI_PORT` | `8000` | Internal port |
| `FASTAPI_WORKERS` | `1` | Uvicorn worker count |
| `SECRET_KEY` | — | Application secret, minimum 32 characters |

### JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | — | Token signing key |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Default token TTL |

### CORS and Cookies

| Variable | Description |
|---|---|
| `CORS_ORIGINS` | Comma-separated list of allowed origins (e.g. `https://your-domain.com`) |
| `COOKIE_SECURE` | Set to `true` in production (requires HTTPS) |
| `COOKIE_SAMESITE` | Cookie `SameSite` policy (`lax` or `strict`) |

### MinIO

| Variable | Default | Description |
|---|---|---|
| `MINIO_ROOT_USER` | `minioadmin` | Admin username |
| `MINIO_ROOT_PASSWORD` | — | Admin password |
| `MINIO_ENDPOINT` | `minio:9000` | Internal endpoint |
| `MINIO_BUCKET_NAME` | `ai3l-uploads` | Upload bucket name |
| `MINIO_USE_SSL` | `false` | Enable TLS for MinIO connection |

### Celery

| Variable | Description |
|---|---|
| `CELERY_BROKER_URL` | Redis URL for task queue (uses DB 1) |
| `CELERY_RESULT_BACKEND` | Redis URL for task results (uses DB 2) |

### Observability (optional)

| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry project DSN for error tracking |
| `SENTRY_TRACES_SAMPLE_RATE` | APM trace sampling rate (0.0 to 1.0) |
| `DD_API_KEY` | Datadog API key |
| `DD_SITE` | Datadog site (`datadoghq.com` or `datadoghq.eu`) |
| `DD_TRACE_ENABLED` | Enable ddtrace auto-instrumentation (`true` or `false`) |

### Super Admin Bootstrap

| Variable | Description |
|---|---|
| `SUPER_ADMIN_USERNAME` | Username for the auto-created super admin account |
| `SUPER_ADMIN_PASSWORD` | Password for the auto-created super admin account |

---

## API Reference

All endpoints are prefixed with `/api/v1/`. Full interactive documentation is available at `/api/docs` when `FASTAPI_DEBUG=true`.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/captcha` | None | Get CAPTCHA image (base64) and session ID |
| POST | `/auth/login` | None | Authenticate with username, password, CAPTCHA |
| POST | `/auth/register` | None | Create a new member account |
| POST | `/auth/guest/{invite_code}` | None | Create a temporary guest session |
| POST | `/auth/logout` | Required | Terminate the current session |
| POST | `/auth/heartbeat` | Required | Extend session TTL |
| POST | `/auth/invite-code` | Member+ | Generate an invite code |
| GET | `/auth/invite-code/{code}` | None | Verify invite code validity |
| POST | `/auth/ws-ticket` | Required | Issue a one-time WebSocket authentication ticket (30-second TTL) |

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | Required | Get own profile |
| GET | `/users/{user_id}` | Required | Get any user's public profile |
| PUT | `/users/{user_id}` | Required | Update own profile |
| PUT | `/users/{user_id}/avatar` | Required | Upload avatar image |
| POST | `/users/me/consent` | Required | Record privacy policy consent |
| POST | `/users/apply-member` | Guest | Submit membership application |
| GET | `/users` | Admin | List all users (paginated) |
| POST | `/users` | Admin | Create user account manually |
| PUT | `/users/{user_id}/role` | Super Admin | Change user role |
| PUT | `/users/{user_id}/ban` | Admin | Ban user |
| PUT | `/users/{user_id}/unban` | Admin | Remove ban |
| DELETE | `/users/{user_id}` | Admin | Anonymize user (GDPR erasure) |

### Forum

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/categories` | Required | List categories |
| POST | `/categories` | Super Admin | Create category |
| GET | `/posts` | Required | List posts (filterable by category, SIG, keyword) |
| POST | `/posts` | Member+ | Create post (50 posts per user per day) |
| GET | `/posts/search` | Required | Full-text search |
| GET | `/posts/{post_id}` | Required | Get single post |
| PUT | `/posts/{post_id}` | Owner | Edit post (versioned) |
| DELETE | `/posts/{post_id}` | Owner/Admin | Soft delete post |
| GET | `/posts/{post_id}/history` | Required | Get edit history |
| POST | `/posts/{post_id}/report` | Member+ | Flag post for moderation |
| GET | `/posts/{post_id}/comments` | Required | List comments |
| POST | `/posts/{post_id}/comments` | Required | Add comment |
| PUT | `/posts/{post_id}/comments/{comment_id}` | Owner | Edit comment |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | Owner/Admin | Delete comment |
| POST | `/posts/{post_id}/comments/{comment_id}/reactions` | Required | Add reaction |

### Special Interest Groups (SIGs)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/sigs` | Required | List all SIGs |
| POST | `/sigs` | Member+ | Create a SIG |
| GET | `/sigs/{sig_id}` | Required | Get SIG detail |
| PUT | `/sigs/{sig_id}` | SIG Admin | Update SIG metadata |
| DELETE | `/sigs/{sig_id}` | Admin | Soft delete SIG |
| GET | `/sigs/{sig_id}/members` | Required | List members |
| POST | `/sigs/{sig_id}/members` | Required | Join SIG |
| DELETE | `/sigs/{sig_id}/members/{user_id}` | Member/Admin | Leave or remove member |
| PUT | `/sigs/{sig_id}/sub-admin` | SIG Admin | Promote member to sub-admin |
| GET | `/sigs/{sig_id}/posts` | Required | Posts in this SIG |
| GET | `/sigs/{sig_id}/forms` | Required | Forms in this SIG |
| POST | `/sigs/{sig_id}/forms` | SIG Admin | Create form |

### Forms

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/forms/{form_id}` | Required | Get form and response count |
| PUT | `/forms/{form_id}` | Owner | Edit form (locked after first response) |
| DELETE | `/forms/{form_id}` | Owner | Soft delete form |
| POST | `/forms/{form_id}/responses` | Required | Submit a response |
| GET | `/forms/{form_id}/responses` | Member+ | View responses |
| POST | `/forms/{form_id}/export` | SIG Admin | Start CSV export (async task) |

### Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/notifications` | Required | Paginated notification feed |
| PUT | `/notifications/{notif_id}/read` | Required | Mark one notification as read |
| PUT | `/notifications/read-all` | Required | Mark all notifications as read |

### Files

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/files/upload/editor` | Required | Upload file (PNG, JPEG, PDF, DOCX, max 20 MB) |
| GET | `/files/presigned/{key}` | Required | Generate presigned download URL |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/dashboard` | Admin | Platform statistics |
| GET | `/admin/reports` | Admin | Pending post reports |
| PUT | `/admin/reports/{report_id}/review` | Admin | Resolve or dismiss report |
| GET | `/admin/applications` | Admin | Membership applications |
| PUT | `/admin/applications/{app_id}/review` | Admin | Approve or reject application |
| GET | `/admin/invite-codes` | Admin | List invite codes |
| POST | `/admin/invite-codes` | Admin | Generate invite code |
| GET | `/admin/audit-logs` | Super Admin | Paginated audit log |

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | PostgreSQL and Redis connectivity check |
| GET | `/tasks/{task_id}` | Required | Celery task status and result |
| WS | `/ws?ticket={ticket}` | Required | Real-time notification stream (ticket obtained from `/auth/ws-ticket`) |

---

## Authentication System

### Roles

| Role | Capabilities |
|---|---|
| `GUEST` | Read forum, submit forms, apply for membership. Session limited to 45 minutes. |
| `MEMBER` | Post to forum, create SIGs, generate invite codes. |
| `ADMIN` | Moderate reports, manage applications, ban users, view dashboard. |
| `SUPER_ADMIN` | All of the above plus role assignment, audit log access, category management. |

### Session Flow

1. Client calls `GET /auth/captcha` to receive a base64-encoded CAPTCHA image and a session ID.
2. Client submits credentials and CAPTCHA answer to `POST /auth/login`.
3. Server validates the CAPTCHA, authenticates the user, creates a JWT, stores the token's `jti` (JWT ID) in Redis, and responds by setting two cookies: an HttpOnly `access_token` cookie containing the JWT, and a readable `csrf_token` cookie.
4. The browser automatically sends the `access_token` cookie on all subsequent same-origin requests. The `Authorization: Bearer <token>` header is supported as a fallback for non-browser API clients.
5. Server validates every request against both the JWT signature and the existence of the `jti` in Redis (dual validation). A valid signature alone is not sufficient.
6. Client calls `POST /auth/heartbeat` every 30 seconds to extend the Redis session TTL.
7. On logout, the `jti` is added to a Redis blacklist and removed from the active session store.

### Token TTLs

| Role | Session Duration |
|---|---|
| GUEST | 45 minutes |
| MEMBER | 3 hours |
| ADMIN | 5 hours |
| SUPER_ADMIN | 8 hours |

### Guest Sessions

Guest accounts are created via `POST /auth/guest/{invite_code}`. The platform enforces a concurrent guest capacity limit (default: 30 simultaneous guests). Guests may apply for full membership through `POST /users/apply-member`.

### Password Policy

Minimum 8 characters, at least one uppercase letter, one lowercase letter, and one digit. Passwords are hashed with Argon2id.

### CSRF Protection

All state-mutating requests require a valid CSRF token. The server sets a `csrf_token` cookie on authentication. Clients must include this value in the `X-CSRF-Token` request header.

---

## Rate Limiting

Rate limiting is enforced at two independent layers.

### Nginx Layer

| Zone | Limit | Applies To |
|---|---|---|
| `global` | 20 requests/second per IP | All `/api/` endpoints |
| `write` | 5 requests/minute per IP | POST, PUT, PATCH, DELETE |

GET and HEAD requests bypass the write zone. Both zones allow short bursts with `nodelay`. Clients exceeding the limit receive `429 Too Many Requests`.

### Application Layer

Post creation is limited to 50 posts per user per day, tracked with a Redis counter. The endpoint returns error code `SYS_429` when the limit is reached.

---

## File Storage

Files are stored in MinIO (S3-compatible API). Objects are never publicly accessible. All reads go through presigned URLs generated at request time with a 7-day TTL.

### Upload Validation

Before accepting an upload, the server reads the file's magic bytes to verify the actual file type against the declared content type. Accepted formats are PNG, JPEG, PDF, and DOCX. Maximum upload size is 20 MB. Files that fail magic number validation are rejected with error code `FILE_001`.

### Object Key Format

Editor uploads are stored at `editor/{user_id}/{uuid}.{ext}`. Avatar uploads are stored at `avatars/{user_id}/{uuid}.{ext}`.

---

## Real-Time Notifications

### WebSocket Endpoint

WebSocket connections use ticket-based authentication to avoid exposing the session cookie over the WebSocket upgrade request.

1. The client calls `POST /api/v1/auth/ws-ticket` while authenticated (cookie is sent automatically).
2. The server generates a one-time ticket, stores it in Redis with a 30-second TTL, and returns it.
3. The client connects using the ticket:

```
ws://host/api/v1/ws?ticket=<one-time-ticket>
```

The server validates the ticket on connection and immediately deletes it from Redis. Expired or already-used tickets are rejected. Unauthenticated connections are closed immediately.

### Heartbeat Protocol

The server sends a `PING` frame every 30 seconds:

```json
{"type": "PING", "timestamp": "2026-01-01T00:00:00Z"}
```

The client must respond with:

```json
{"type": "PONG"}
```

Connections that do not respond within 90 seconds are closed.

### Server-Sent Message Types

| Type | Description |
|---|---|
| `NOTIFICATION` | New activity (comment, reaction, mention) |
| `FORCE_LOGOUT` | Server-initiated session termination (e.g., account banned) |

---

## Background Tasks

Celery workers use Redis as both the broker (DB 1) and result backend (DB 2).

### Tasks

| Task | Trigger | Description |
|---|---|---|
| `form_export` | Admin requests CSV export | Serializes all responses to CSV and stores the result in Redis |

### Checking Task Status

```
GET /api/v1/tasks/{task_id}
```

Returns the task state (`PENDING`, `SUCCESS`, `FAILURE`) and result data if the task has completed.

### Inspecting Workers

```bash
docker compose exec celery celery -A app.celery_app:celery inspect ping
```

---

## Admin Features

### Moderation

**Post Reports**: Members flag posts for review. Admins view pending reports at `GET /admin/reports` and either resolve (act on the post) or dismiss (no action required).

**Membership Applications**: Guests apply via `POST /users/apply-member`. Admins review at `GET /admin/applications`. Approving an application upgrades the user role from `GUEST` to `MEMBER`.

### User Management

Admins can ban users with a required reason. Banning terminates all active sessions immediately and sends a `FORCE_LOGOUT` WebSocket message to any connected clients. Super Admins can change user roles.

### Invite Codes

Admins and Super Admins generate single-use invite codes via `POST /admin/invite-codes`. Each code can be used once for either guest access (`POST /auth/guest/{code}`) or new member registration.

### Audit Log

Every sensitive action (authentication events, admin decisions, bans, role changes) is written to the `audit_logs` table with the actor's user ID, IP address, timestamp, and target entity. Accessible only to Super Admins at `GET /admin/audit-logs`.

---

## CI/CD Pipeline

Three GitHub Actions workflows run on every push to `main` and on pull requests that touch their respective paths.

### Workflows

| Workflow | Trigger Path | Jobs |
|---|---|---|
| Backend CI | `backend/**` | Lint and type check, Tests, Dependency audit |
| Frontend CI | `frontend/**` | Lint, type check, unit tests, and build, Dependency audit |
| Docker Build Check | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `nginx/**`, `requirements.txt`, `package.json` | Build backend image, Build frontend image |

### Backend CI Jobs

- **Lint and Type Check**: Runs Black (format), isort (import order), Flake8 (lint), and mypy (type check). The test job requires this job to pass before it starts.
- **Tests**: Runs `pytest` with the full test suite. All database interactions are mocked; no running database is required.
- **Dependency Audit**: Runs `pip-audit` with `--strict` to detect known vulnerabilities in Python dependencies.

### Frontend CI Jobs

- **Lint, Test and Build**: Runs Prettier (format check), ESLint, TypeScript type check (`vue-tsc`), Vitest unit tests, and a full production Vite build.
- **Dependency Audit**: Runs `npm audit --audit-level=high` to detect high and critical vulnerabilities in npm dependencies.

### Branch Protection

The `main` branch is protected by a Ruleset with the following requirements:

- Status checks must pass: `Lint & Type Check`, `Tests`, `Lint, Test & Build`
- Linear history required (rebase only, no merge commits)
- Force pushes blocked

---

## Testing

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

The test suite uses `pytest-asyncio` in auto mode. All tests mock the asyncpg pool and Redis client using `unittest.mock.AsyncMock`. No running database, Redis, or MinIO instance is required.

### Frontend

```bash
cd frontend
npm install
npm run test:unit       # Vitest unit tests
npm run test:e2e        # Playwright end-to-end tests
```

Type check only:

```bash
npx vue-tsc --noEmit
```

---

## Database Migrations

Migrations are managed with Alembic and run automatically on FastAPI startup via `alembic upgrade head`.

### Creating a new migration

```bash
docker compose exec fastapi alembic revision --autogenerate -m "short description"
```

### Manual migration commands

```bash
# Apply all pending migrations
docker compose exec fastapi alembic upgrade head

# Roll back one migration
docker compose exec fastapi alembic downgrade -1

# Show current revision
docker compose exec fastapi alembic current
```

### Migration History

| Revision | Description |
|---|---|
| `af05d5a5a98b` | Initial schema: users, invite codes |
| `83ded9c22efe` | Forum: categories, posts, post history, comments |
| `c3f8a1b2d4e5` | SIGs, SIG members, post reports |
| `d4e5f6a7b8c9` | Forms and form responses |
| `e5f6a7b8c9d0` | Notifications |
| `6b1be57feb6e` | Membership applications, privacy consents |
| `f6a7b8c9d0e1` | Audit logs, user ban fields |
| `h8i9j0k1l2m3` | Composite indexes for query performance |

---

## Scripts

All scripts are in `scripts/`. Make them executable with `chmod +x scripts/*.sh`.

### `backup-db.sh`

Creates a compressed PostgreSQL dump.

```bash
./scripts/backup-db.sh
```

Output is written to `./backups/ai3l_community_YYYYMMDD_HHMMSS.sql.gz`. The last 30 backups are retained automatically.

### `restore-db.sh`

Restores the database from a backup file.

```bash
./scripts/restore-db.sh ./backups/ai3l_community_20260101_030000.sql.gz
```

### `init-letsencrypt.sh`

Issues a TLS certificate from Let's Encrypt for a domain. Run once before enabling HTTPS.

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

Certificates are written to `./nginx/ssl/`.

### `renew-certs.sh`

Renews Let's Encrypt certificates and reloads Nginx. Schedule with cron:

```bash
0 3 */60 * * /path/to/ai3l-community/scripts/renew-certs.sh
```

### `init-minio.sh`

Creates the MinIO bucket and applies access policies. Run once after the first `docker compose up`.

```bash
./scripts/init-minio.sh
```

---

## Production Deployment

### 1. Configure environment

In `.env`, set the following for production:

```bash
FASTAPI_ENV=production
FASTAPI_DEBUG=false
FASTAPI_WORKERS=4          # set to the number of available CPU cores
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://your-domain.com
COOKIE_SECURE=true
```

Replace all `changeme_*` values with strong, randomly generated secrets.

### 2. Issue TLS certificates

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

### 3. Enable HTTPS in Nginx

In `nginx/conf.d/default.conf`, uncomment the HTTPS server block and the HTTP-to-HTTPS redirect. Replace `YOUR_DOMAIN` with your domain name.

### 4. Start services

```bash
docker compose up -d
```

### 5. Enable Datadog monitoring (optional)

```bash
DD_API_KEY=your_key docker compose --profile monitoring up -d
```

### 6. Schedule automated tasks

Add to crontab on the host machine:

```bash
0 3 * * *       /path/to/scripts/backup-db.sh
0 3 */60 * *    /path/to/scripts/renew-certs.sh
```

### Production Checklist

- All `changeme_*` values replaced with strong random secrets
- `FASTAPI_ENV=production` and `FASTAPI_DEBUG=false`
- `CORS_ORIGINS` set to the actual production domain
- `COOKIE_SECURE=true`
- TLS certificates issued and HTTPS server block enabled in Nginx
- `SENTRY_DSN` configured for error tracking
- Database backups scheduled via cron
- `FASTAPI_WORKERS` set to match available CPU cores

---

## Security Notes

**Dual-validation tokens**: JWT tokens are validated against both the cryptographic signature and an active Redis session record (`jti`). A compromised token is invalidated server-side on logout by blacklisting its `jti` in Redis.

**CAPTCHA enforcement**: Login and registration endpoints require a CAPTCHA solution to prevent automated credential stuffing.

**CSRF protection**: A CSRF token is issued as a cookie on authentication and must be present in the `X-CSRF-Token` header on all state-mutating requests.

**File upload security**: Magic number validation rejects files whose content does not match their declared MIME type. PDF files are sanitized before storage using pypdf.

**Rate limiting**: Nginx enforces IP-level request rate limits on all API endpoints, with a stricter limit on write operations. Redis counters enforce per-user daily post quotas.

**XSS prevention**: User-generated HTML is sanitized with DOMPurify on the frontend before rendering, and with nh3 on the backend before storage.

**Audit trail**: Authentication events, admin decisions, content moderation actions, and role changes are recorded in `audit_logs` with the actor's user ID, IP address, and target entity.

**SQL injection**: All database interactions use asyncpg parameterized queries. No raw string interpolation is used in any database query.

**Trusted host enforcement**: In production, Starlette `TrustedHostMiddleware` validates the `Host` header against the configured domain.

---

## Contributing

### Workflow

This repository enforces a rebase-only merge strategy on the `main` branch. All contributions must go through a pull request.

```bash
# Create a feature branch from the latest main
git fetch origin
git checkout -b feature/my-feature origin/main

# Work and commit
git add .
git commit -m "feat: describe the change"

# Rebase onto main before opening the PR
git fetch origin
git rebase origin/main

# Push the branch
git push origin feature/my-feature
```

### Commit Message Format

Follow the Conventional Commits convention:

```
<type>: <short description>

[optional body]
```

Common types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

### Pull Request Requirements

All of the following status checks must pass before a PR can be merged:

- `Lint & Type Check` (backend)
- `Tests` (backend)
- `Lint, Test & Build` (frontend)

Direct pushes to `main` are blocked.
