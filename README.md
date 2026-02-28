# AI3L Community Platform

A full-stack community platform built for academic groups and special interest groups (SIGs). It provides a discussion forum, survey/form system, real-time notifications, file hosting, and a complete admin suite — all containerized with Docker Compose.

---

## Table of Contents

- [Technology Stack](#technology-stack)
- [Architecture Overview](#architecture-overview)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Authentication System](#authentication-system)
- [Rate Limiting](#rate-limiting)
- [File Storage](#file-storage)
- [Real-Time Notifications](#real-time-notifications)
- [Background Tasks](#background-tasks)
- [Admin Features](#admin-features)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Scripts](#scripts)
- [Production Deployment](#production-deployment)
- [Security Notes](#security-notes)

---

## Technology Stack

**Backend**
- Python 3.12, FastAPI, asyncpg (async PostgreSQL driver)
- Alembic (schema migrations), Pydantic v2 (validation)
- Celery + Redis (task queue)
- Passlib/Argon2 (password hashing), PyJWT (tokens)
- boto3 (MinIO/S3), bleach (HTML sanitization)
- Loguru (structured logging), Sentry SDK, ddtrace (Datadog APM)

**Frontend**
- Vue 3, TypeScript, Vite
- Pinia (state management), Vue Router 4
- TipTap (rich text editor), Tailwind CSS v4
- Axios, DOMPurify

**Infrastructure**
- PostgreSQL 15, Redis 7, MinIO (S3-compatible storage)
- Nginx 1.25 (reverse proxy, rate limiting, TLS termination)
- Docker Compose
- Datadog Agent (optional, monitoring profile)

---

## Architecture Overview

```
Browser
  |
  | :3000 (HTTP) / :3443 (HTTPS)
  v
Nginx (reverse proxy)
  |-- /api/v1/ws  --> FastAPI (WebSocket)
  |-- /api/       --> FastAPI (HTTP)
  |-- /           --> Static files (Vue SPA build)
       |
       v
   FastAPI :8000
       |-- asyncpg --> PostgreSQL :5432
       |-- aioredis --> Redis :6379
       |-- boto3   --> MinIO :9000
       |-- Celery tasks --> Redis broker
```

All services share a Docker bridge network (`ai3l-network`). No service port except Nginx is exposed to the host.

---

## Getting Started

### Prerequisites

- Docker Engine 24+ and Docker Compose v2
- 8 GB RAM recommended (all services combined)

### 1. Clone and configure

```bash
git clone <repository-url>
cd AI3L-Community
cp .env.example .env
```

Edit `.env` and change every `changeme_*` value before proceeding.

### 2. Initialize MinIO bucket

```bash
./scripts/init-minio.sh
```

### 3. Start all services

```bash
docker compose up -d
```

Docker Compose will start services in dependency order. FastAPI waits for PostgreSQL, Redis, and MinIO to be healthy before starting. Nginx waits for FastAPI.

Alembic migrations run automatically on FastAPI startup.

### 4. Access the application

| Service | URL |
|---|---|
| Web application | http://localhost:3000 |
| API docs (dev only) | http://localhost:3000/api/docs |
| MinIO console | http://localhost:9001 |

A super admin account is created automatically on first startup using `SUPER_ADMIN_USERNAME` and `SUPER_ADMIN_PASSWORD` from `.env`.

### Stopping

```bash
docker compose down
```

Volumes (`pgdata`, `redis-data`, `minio-data`) persist across restarts. To wipe everything:

```bash
docker compose down -v
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values. The table below describes each variable.

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
| `FASTAPI_WORKERS` | `1` | Uvicorn worker count (set to CPU count in production) |
| `SECRET_KEY` | — | App secret, minimum 32 characters |

### JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | — | Signing key |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Default token TTL |

### CORS

| Variable | Description |
|---|---|
| `CORS_ORIGINS` | Comma-separated list of allowed origins |

### MinIO

| Variable | Default | Description |
|---|---|---|
| `MINIO_ROOT_USER` | `minioadmin` | Admin username |
| `MINIO_ROOT_PASSWORD` | — | Admin password |
| `MINIO_ENDPOINT` | `minio:9000` | Internal endpoint |
| `MINIO_BUCKET_NAME` | `ai3l-uploads` | Bucket for file uploads |
| `MINIO_USE_SSL` | `false` | TLS for MinIO connection |

### Celery

| Variable | Description |
|---|---|
| `CELERY_BROKER_URL` | Redis URL for task queue (DB 1) |
| `CELERY_RESULT_BACKEND` | Redis URL for task results (DB 2) |

### Observability (optional)

| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry project DSN |
| `SENTRY_TRACES_SAMPLE_RATE` | APM trace sampling rate (0.0–1.0) |
| `DD_API_KEY` | Datadog API key |
| `DD_SITE` | Datadog site (`datadoghq.com` or `datadoghq.eu`) |
| `DD_TRACE_ENABLED` | Enable ddtrace auto-instrumentation (`true`/`false`) |

### Super Admin Bootstrap

| Variable | Description |
|---|---|
| `SUPER_ADMIN_USERNAME` | Username for the auto-created super admin |
| `SUPER_ADMIN_PASSWORD` | Password for the auto-created super admin |

---

## API Reference

All endpoints are prefixed with `/api/v1/`.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/captcha` | None | Get CAPTCHA image (base64) + session ID |
| POST | `/auth/login` | None | Login with username, password, CAPTCHA |
| POST | `/auth/register` | None | Create new account |
| POST | `/auth/guest/{invite_code}` | None | Create temporary guest session |
| POST | `/auth/logout` | Required | Terminate session |
| POST | `/auth/heartbeat` | Required | Extend session TTL |
| POST | `/auth/invite-code` | Member+ | Generate invite code |
| GET | `/auth/invite-code/{code}` | None | Verify invite code validity |

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | Required | Own profile |
| GET | `/users/{user_id}` | Required | Any user's public profile |
| PUT | `/users/{user_id}` | Required | Update own profile |
| PUT | `/users/{user_id}/avatar` | Required | Upload avatar image |
| POST | `/users/me/consent` | Required | Record privacy policy consent |
| POST | `/users/apply-member` | Guest | Apply for full membership |
| GET | `/users` | Admin | List all users (paginated) |
| POST | `/users` | Admin | Create user manually |
| PUT | `/users/{user_id}/role` | Super Admin | Change user role |
| PUT | `/users/{user_id}/ban` | Admin | Ban user |
| PUT | `/users/{user_id}/unban` | Admin | Remove ban |
| DELETE | `/users/{user_id}` | Admin | Anonymize user (GDPR erasure) |

### Forum

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/categories` | Required | List categories |
| POST | `/categories` | Super Admin | Create category |
| GET | `/posts` | Required | List posts (filter by category, SIG, keyword) |
| POST | `/posts` | Member+ | Create post (limit: 50/day) |
| GET | `/posts/search` | Required | Full-text search |
| GET | `/posts/{post_id}` | Required | Single post |
| PUT | `/posts/{post_id}` | Owner | Edit post (versioned) |
| DELETE | `/posts/{post_id}` | Owner/Admin | Soft delete post |
| GET | `/posts/{post_id}/history` | Required | Edit history |
| POST | `/posts/{post_id}/report` | Member+ | Flag post for review |
| GET | `/posts/{post_id}/comments` | Required | List comments |
| POST | `/posts/{post_id}/comments` | Required | Add comment |
| PUT | `/posts/{post_id}/comments/{comment_id}` | Owner | Edit comment |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | Owner/Admin | Delete comment |
| POST | `/posts/{post_id}/comments/{comment_id}/reactions` | Required | Add emoji reaction |

### Special Interest Groups (SIGs)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/sigs` | Required | List all SIGs |
| POST | `/sigs` | Member+ | Create SIG |
| GET | `/sigs/{sig_id}` | Required | SIG detail |
| GET | `/sigs/{sig_id}/members` | Required | Member list |
| POST | `/sigs/{sig_id}/members` | Required | Join SIG |
| DELETE | `/sigs/{sig_id}/members/{user_id}` | Member/Admin | Leave or remove member |
| PUT | `/sigs/{sig_id}/sub-admin` | SIG Admin | Assign category admin |
| GET | `/sigs/{sig_id}/posts` | Required | Posts in this SIG |
| GET | `/sigs/{sig_id}/forms` | Required | Forms in this SIG |
| POST | `/sigs/{sig_id}/forms` | SIG Admin | Create form |

### Forms

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/forms/{form_id}` | Required | Form detail and response count |
| PUT | `/forms/{form_id}` | Owner | Edit form (locked after first response) |
| DELETE | `/forms/{form_id}` | Owner | Soft delete form |
| POST | `/forms/{form_id}/responses` | Required | Submit a response |
| GET | `/forms/{form_id}/responses` | Member+ | View responses (CSV export available) |

### Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/notifications` | Required | Paginated notification feed |
| PUT | `/notifications/{notif_id}/read` | Required | Mark one as read |
| PUT | `/notifications/read-all` | Required | Mark all as read |

### Files

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/files/upload/editor` | Required | Upload file (PNG, JPEG, PDF, DOCX, max 20MB) |
| GET | `/files/presigned/{key}` | Required | Generate presigned download URL |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/reports` | Admin | Pending post reports |
| PUT | `/admin/reports/{report_id}/review` | Admin | Approve or dismiss report |
| GET | `/admin/applications` | Admin | Pending membership applications |
| PUT | `/admin/applications/{app_id}/review` | Admin | Approve or reject application |
| GET | `/admin/audit-logs` | Super Admin | Paginated audit log |

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | PostgreSQL and Redis health status |
| GET | `/tasks/{task_id}` | Required | Celery task status |
| WS | `/ws?token={jwt}` | Required | Real-time notification stream |

---

## Authentication System

### Roles

| Role | Capabilities |
|---|---|
| `GUEST` | Read forum, submit forms, apply for membership, 45-minute session |
| `MEMBER` | Post to forum, create SIGs, generate invite codes |
| `ADMIN` | Moderate reports, manage applications, ban users |
| `SUPER_ADMIN` | All of the above plus role assignment, audit log access, category creation |

### Session Flow

1. Client calls `GET /auth/captcha` to receive a base64 CAPTCHA image and a session ID.
2. Client submits credentials and the CAPTCHA answer to `POST /auth/login`.
3. Server validates the CAPTCHA, authenticates the user, creates a JWT, and stores the JWT's `jti` in Redis.
4. Client includes the JWT in the `Authorization: Bearer <token>` header on subsequent requests.
5. Server validates every request by checking both the JWT signature and the existence of the `jti` in Redis (dual validation).
6. Client calls `POST /auth/heartbeat` every 30 seconds to extend the Redis session TTL.
7. On logout, the `jti` is added to a Redis blacklist and removed from the session store.

### Token TTLs

| Role | Session Duration |
|---|---|
| GUEST | 45 minutes |
| MEMBER | 3 hours |
| ADMIN | 5 hours |
| SUPER_ADMIN | 8 hours |

### Guest Accounts

Guest accounts are created via `POST /auth/guest/{invite_code}`. The platform enforces a concurrent guest capacity limit (default: 30). Guests can apply for full membership through `POST /users/apply-member`.

### Password Policy

Minimum 8 characters, at least one uppercase letter, one lowercase letter, and one digit. Passwords are hashed with Argon2.

---

## Rate Limiting

Rate limiting is enforced at two layers.

### Nginx Layer

| Zone | Limit | Applies To |
|---|---|---|
| `global` | 20 requests/second per IP | All `/api/` endpoints |
| `write` | 5 requests/minute per IP | POST, PUT, PATCH, DELETE only |

GET and HEAD requests are excluded from the write zone via an Nginx `map` directive. Both zones allow a burst of 10 and 5 respectively with `nodelay`.

Clients that exceed the limit receive HTTP `429 Too Many Requests`.

### Application Layer

Post creation is limited to 50 posts per user per day. This is tracked in Redis and returns error code `SYS_429` when exceeded.

---

## File Storage

Files are stored in MinIO using S3-compatible APIs.

### Upload Validation

Before upload, the server reads the first bytes of the file to verify the magic number matches the declared content type (malware detection). Allowed formats are PNG, JPEG, PDF, and DOCX. Maximum file size is 20MB for editor uploads.

Error code `FILE_001` is returned for files that fail magic number validation.

### Object Keys and URLs

Uploaded objects are stored with keys in the format `editor/{user_id}/{uuid}.{ext}`. The raw key is stored in the database. Presigned URLs (7-day TTL) are generated on read so they are always fresh.

Avatar uploads store the MinIO key in the `avatar_url` column. The endpoint generates a presigned URL each time the user profile is fetched.

---

## Real-Time Notifications

### WebSocket Endpoint

```
ws://localhost:3000/api/v1/ws?token=<jwt>
```

The server validates the JWT and Redis session on connection. Unauthenticated connections are rejected immediately.

### Protocol

The server sends a `PING` frame every 30 seconds:

```json
{"type": "PING", "timestamp": "2026-02-28T00:00:00Z"}
```

The client must respond with:

```json
{"type": "PONG"}
```

Connections that do not respond within 90 seconds are closed.

### Message Types

| Type | Description |
|---|---|
| `NOTIFICATION` | New activity (comment, reaction, mention) |
| `FORCE_LOGOUT` | Server-initiated session termination (e.g., account banned) |

Guest sessions are automatically closed after 45 minutes by the server.

---

## Background Tasks

Celery workers use Redis as both the broker (DB 1) and result backend (DB 2).

### Configured Tasks

| Task | Trigger | Description |
|---|---|---|
| `form_export` | Admin requests CSV export | Serializes all form responses to CSV and stores result in Redis |

### Checking Task Status

```bash
GET /api/v1/tasks/{task_id}
```

Returns task state (`PENDING`, `SUCCESS`, `FAILURE`) and result if available.

### Starting Workers Manually

```bash
docker compose exec celery celery -A app.celery_app:celery inspect ping
```

---

## Admin Features

### Moderation

**Post Reports**: Members can flag posts. Admins review reports at `GET /admin/reports` and either resolve (take action on the post) or dismiss (no action needed).

**Membership Applications**: Guests apply via the application form. Admins approve or reject at `GET /admin/applications`. Approval automatically upgrades the user role from `GUEST` to `MEMBER`.

### User Management

Admins can ban users with a reason. Banning terminates all active sessions and sends a `FORCE_LOGOUT` WebSocket message to connected clients. Super Admins can change user roles.

### Audit Log

Every sensitive action (login, logout, ban, application review, etc.) is written to the `audit_logs` table with the actor's user ID, IP address, and target. Accessible at `GET /admin/audit-logs` (Super Admin only).

---

## Testing

### Backend

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Run with coverage report:

```bash
pytest tests/ --cov=app/services --cov-report=term-missing
```

The test suite uses `pytest-asyncio` with `asyncio_mode = auto`. All tests mock the asyncpg pool and Redis client — no running database is required.

### Frontend

```bash
cd frontend
npm install
npm run test:unit      # Vitest unit tests
npm run test:e2e       # Playwright end-to-end tests
```

TypeScript type check:

```bash
npx vue-tsc --noEmit
```

---

## Database Migrations

Migrations are managed with Alembic and run automatically on FastAPI startup.

To create a new migration after changing a model:

```bash
docker compose exec fastapi alembic revision --autogenerate -m "description"
```

To apply migrations manually:

```bash
docker compose exec fastapi alembic upgrade head
```

To roll back one step:

```bash
docker compose exec fastapi alembic downgrade -1
```

### Migration History

| Revision | Description |
|---|---|
| `af05d5a5a98b` | Initial schema: users, invite codes |
| `83ded9c22efe` | Forum: categories, posts, post history, comments |
| `c3f8a1b2d4e5` | SIGs, sig members, post reports |
| `d4e5f6a7b8c9` | Forms and form responses |
| `e5f6a7b8c9d0` | Notifications |
| `6b1be57feb6e` | Membership applications, privacy consents |
| `f6a7b8c9d0e1` | Audit logs, user ban fields |

---

## Scripts

All scripts are in the `scripts/` directory. Make them executable with `chmod +x scripts/*.sh` before use.

### `backup-db.sh`

Creates a compressed PostgreSQL dump.

```bash
./scripts/backup-db.sh
```

Output is written to `./backups/ai3l_community_YYYYMMDD_HHMMSS.sql.gz`. The last 30 backups are retained automatically.

### `restore-db.sh`

Restores the database from a backup file.

```bash
./scripts/restore-db.sh ./backups/ai3l_community_20260228_030000.sql.gz
```

### `init-letsencrypt.sh`

Issues a TLS certificate via Let's Encrypt for a domain. Run this once before enabling HTTPS.

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

Certificates are written to `./nginx/ssl/`.

### `renew-certs.sh`

Renews certificates and reloads Nginx. Schedule with cron:

```bash
0 3 */60 * * /path/to/ai3l-community/scripts/renew-certs.sh
```

### `init-minio.sh`

Creates the MinIO bucket and applies access policies.

```bash
./scripts/init-minio.sh
```

Run this once after the first `docker compose up`.

---

## Production Deployment

### 1. Configure environment

In `.env`, set the following for production:

```bash
FASTAPI_ENV=production
FASTAPI_DEBUG=false
FASTAPI_WORKERS=4          # match your CPU count
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://your-domain.com
```

Change all `changeme_*` values to strong random secrets.

### 2. Issue TLS certificates

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

### 3. Enable HTTPS in Nginx

In `nginx/conf.d/default.conf`, uncomment the HTTPS server block and the HTTP-to-HTTPS redirect block. Replace `YOUR_DOMAIN` with your domain name.

### 4. Start with the HTTPS config

```bash
docker compose up -d
```

### 5. Enable Datadog monitoring (optional)

```bash
DD_API_KEY=your_key docker compose --profile monitoring up -d
```

### 6. Schedule backups

Add to crontab on the host:

```bash
0 3 * * * /path/to/ai3l-community/scripts/backup-db.sh
0 3 */60 * * /path/to/ai3l-community/scripts/renew-certs.sh
```

### Production Checklist

- All `changeme_*` values replaced with strong random secrets
- `FASTAPI_ENV=production` and `FASTAPI_DEBUG=false`
- `CORS_ORIGINS` set to your actual domain
- TLS certificates issued and HTTPS server block enabled
- `SENTRY_DSN` configured for error tracking
- Database backups scheduled
- `FASTAPI_WORKERS` set to match available CPU cores

---

## Security Notes

**Authentication**: JWT tokens are validated against both their cryptographic signature and an active Redis session record. A compromised token is invalidated server-side on logout by adding its `jti` to a Redis blacklist.

**CAPTCHA**: Required on all login and registration endpoints to prevent automated credential stuffing.

**File uploads**: Magic number validation prevents disguised file uploads. HTML content from the rich text editor is sanitized with bleach before storage.

**Rate limiting**: Nginx enforces IP-level rate limits on all API endpoints and separate write limits on mutating endpoints. Server-side Redis counters enforce per-user daily post limits.

**XSS prevention**: All user-generated HTML is sanitized with DOMPurify on the frontend and bleach on the backend before rendering or storage.

**Audit trail**: Every authentication event, admin action, and content moderation decision is recorded in the `audit_logs` table with the actor's IP address.

**SQL injection**: The application uses asyncpg parameterized queries exclusively. No raw string interpolation is used in database queries.

**Host header attacks**: In production, Starlette's `TrustedHostMiddleware` is active.
