# AI3L Community -- System Design & Specification

> **Version:** 2.0.0
> **Last Updated:** 2026-03-01
> **Status:** Phase 6 Complete. Phase 7 (Production Hardening) in progress.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture & Tech Stack](#2-system-architecture--tech-stack)
3. [Infrastructure & Deployment](#3-infrastructure--deployment)
4. [Data Model & ERD](#4-data-model--erd)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [Academic Forum](#6-academic-forum)
7. [Special Interest Groups (SIGs)](#7-special-interest-groups-sigs)
8. [Built-in Forms System](#8-built-in-forms-system)
9. [Notification System](#9-notification-system)
10. [File Upload & Storage](#10-file-upload--storage)
11. [Full API Specification](#11-full-api-specification)
12. [Frontend Pages & Components](#12-frontend-pages--components)
13. [Security & Threat Model](#13-security--threat-model)
14. [Resource Quotas & Rate Limiting](#14-resource-quotas--rate-limiting)
15. [Engineering Guidelines](#15-engineering-guidelines)
16. [DevOps & Observability](#16-devops--observability)
17. [Error Code Registry](#17-error-code-registry)
18. [Implementation Status](#18-implementation-status)

---

## 1. Project Overview

**Project Name:** AI3L Community (AI in Language Learning and Literacy)

**Purpose:** A cross-border academic exchange platform for researchers, educators, and students working on AI applications in language learning and literacy.

**Target Audience:** International academic community (China, Taiwan, global users).

**UI Language:** English only.

**Deployment:** Single-server monolith in Hong Kong, Docker Compose environment.

**Minimum Hardware:** 8 vCPU / 16 GB RAM.

**Compliance:**
- **GDPR Right to be Forgotten:** Account deletion performs anonymization (PII overwritten with `Deleted_User_{UUID}`), not hard delete. Foreign keys preserved.
- **Data Residency Disclosure:** Mandatory privacy consent modal at registration, first login, and every guest session. Consent is recorded in the `privacy_consents` table (guests use an in-memory Redis record).
- **Search Engine Blocking:** `robots.txt` Disallow all, `X-Robots-Tag: noindex, nofollow` on all responses.

---

## 2. System Architecture & Tech Stack

### 2.1 Architecture

Decoupled full-stack architecture (frontend and backend fully separated).

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Vue 3 (Composition API) + TypeScript + Vite + Tailwind CSS v4 | SPA served by Nginx |
| **Backend** | Python 3.12 + FastAPI | Controller-Service-Repository-Converter layered architecture, async |
| **Database** | PostgreSQL 15+ (asyncpg driver) | SQLAlchemy ORM for model definition and Alembic migrations; raw asyncpg pool for runtime queries |
| **Cache & State** | Redis 7 (AOF + RDB hybrid persistence) | Sessions, counters, rate limits, Pub/Sub for WebSocket fanout |
| **Task Queue** | Celery + Redis (broker + result backend) | Async CSV export, guest cleanup, file scanning |
| **File Storage** | MinIO (S3-compatible) | Avatars, editor attachments. Object keys stored in DB; presigned URLs generated on demand |
| **Reverse Proxy** | Nginx 1.27 | TLS termination, rate limiting, SPA serving |
| **Observability** | Sentry Cloud (errors), Datadog (metrics, optional profile) | SaaS to avoid local memory pressure |

### 2.2 Deployment Topology

```
Client (Browser)
    |
    v HTTP/HTTPS :80/:443
+------------------------------------------+
|         Docker Compose Environment        |
|                                          |
|  Nginx ──> FastAPI (:8000)               |
|    |              |                      |
|    |       +------+------+               |
|    |       v      v      v               |
|    |    PostgreSQL Redis  MinIO           |
|    |              ^                      |
|    |              |                      |
|    |    Celery Worker + Celery Beat       |
|    |                                     |
|    +──> Vue SPA (static files)           |
+------------------------------------------+
         |              |
         v              v
     Sentry Cloud    Datadog (optional)
```

### 2.3 Backend Layered Architecture

```
Endpoint (FastAPI router)
    |
    v
Service (business logic)
    |
    v
Repository (asyncpg raw SQL queries)
    |
    v
PostgreSQL

Service --> Converter --> Response Schema (Pydantic)
```

The **Converter** layer transforms raw asyncpg `Record` objects into Pydantic response schemas without coupling services to the API schema.

### 2.4 Scaling Trigger

MinIO initially co-exists on the same server. If concurrent traffic exceeds 200 users or disk I/O reaches warning thresholds (large file I/O delaying PostgreSQL fsync), MinIO must be separated to an independent storage instance.

---

## 3. Infrastructure & Deployment

### 3.1 Docker Services

| Service | Image | CPU | Memory | Health Check |
|---------|-------|-----|--------|-------------|
| nginx | nginx:1.25-alpine | 0.5 | 256 MB | `wget http://127.0.0.1/health-nginx` |
| fastapi | ./backend (Python 3.12-slim) | 2.0 | 3 GB | urllib `http://localhost:8000/api/v1/health` |
| postgres | postgres:15-alpine | 2.0 | 4 GB | `pg_isready` |
| redis | redis:7-alpine | 0.5 | 1 GB | `redis-cli ping` |
| celery | ./backend | 1.0 | 1.5 GB | `celery inspect ping` |
| celery-beat | ./backend | 0.25 | 256 MB | (no health check; restarts on failure) |
| minio | minio/minio:latest | 1.0 | 1.5 GB | `mc ready local` |
| datadog-agent | gcr.io/datadoghq/agent:7 | 1.0 | 1 GB | (optional; activated via `--profile monitoring`) |

### 3.2 Ports

**Production** (via Nginx):

| Host Port | Container Port | Service |
|-----------|---------------|---------|
| 3000 | 80 | HTTP |
| 3443 | 443 | HTTPS |

**Development** (override, direct access):

| Port | Service |
|------|---------|
| 18000 | FastAPI |
| 15432 | PostgreSQL |
| 16379 | Redis |
| 19000 | MinIO API |
| 19001 | MinIO Console |
| 15173 | Vite Dev Server |

### 3.3 Named Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| pgdata | postgres:/var/lib/postgresql/data | Database files |
| redis-data | redis:/data | AOF + RDB persistence |
| minio-data | minio:/data | Object storage |
| certbot-webroot | nginx:/var/www/certbot | Let's Encrypt ACME challenges |
| backups | (host-mapped) | Database backup archives |

### 3.4 PostgreSQL Tuning

```
shared_buffers = 1GB
effective_cache_size = 2GB
work_mem = 16MB
max_connections = 100
```

### 3.5 Redis Configuration

```
maxmemory 512mb
maxmemory-policy noeviction
appendonly yes
save 60 1000
```

Redis database allocation:
- DB 0: sessions, rate limits, captchas, idempotency keys, WebSocket tickets
- DB 1: Celery broker
- DB 2: Celery result backend

### 3.6 Environment Variables

Defined in `.env.example` (`.env` is gitignored):

| Group | Variables |
|-------|----------|
| PostgreSQL | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` |
| FastAPI | `FASTAPI_ENV`, `FASTAPI_DEBUG`, `SECRET_KEY`, `FASTAPI_WORKERS` |
| JWT | `JWT_SECRET_KEY`, `JWT_ALGORITHM` |
| CORS | `CORS_ORIGINS` (comma-separated origins) |
| Cookies | `COOKIE_SECURE`, `COOKIE_SAMESITE`, `COOKIE_DOMAIN` |
| CSRF | `CSRF_HEADER_NAME` (default `X-CSRF-Token`) |
| MinIO | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_BUCKET_NAME`, `MINIO_USE_SSL` |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Sentry | `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` |
| Datadog | `DD_API_KEY`, `DD_SITE`, `DD_TRACE_ENABLED`, `DD_AGENT_HOST` |
| Super Admin | `SUPER_ADMIN_USERNAME`, `SUPER_ADMIN_PASSWORD` |
| Logging | `LOG_LEVEL`, `LOG_FORMAT` |
| Storage | (implicit) `MAX_USER_STORAGE_BYTES` = 1 GB |
| VirusTotal | `VT_API_KEY` |
| Trusted Hosts | `TRUSTED_HOSTS` (comma-separated; enforced in production) |

### 3.7 HTTPS & TLS

**Certificate:** Let's Encrypt (free, auto-renewing via Certbot).

**Setup:**
- Certbot runs as a one-shot Docker container for initial certificate issuance and periodic renewal (cron every 60 days).
- Certificates stored in `certbot-webroot` volume, mounted into Nginx.
- Nginx HTTPS server block is present in `nginx/conf.d/default.conf` but commented out during development. Uncomment and set `server_name` before production deployment.
- HTTP to HTTPS redirect enforced in production.
- HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- TLS 1.2 and 1.3 only. Modern cipher suite. OCSP stapling enabled.

**Domain (TBD):** Not yet confirmed. Recommended candidates:
- `ai3l.org` -- Short, academic tone (.org), easy to remember.
- `ai3l-community.org` -- Descriptive, clear purpose.
- `ai3l.community` -- Modern TLD, exact project name match.

Once domain is confirmed, update: Nginx `server_name`, CORS `allow_origins`, CSP `img-src` (for MinIO subdomain or path), `COOKIE_DOMAIN`, `COOKIE_SECURE=true`, `TRUSTED_HOSTS`, `.env.example`.

---

## 4. Data Model & ERD

### 4.1 Entity Relationship Diagram

```
USERS ||--o{ POSTS : creates
USERS ||--o{ COMMENTS : writes
USERS ||--o{ AUDIT_LOGS : triggers
USERS ||--o{ NOTIFICATIONS : receives
USERS ||--o{ INVITE_CODES : generates
USERS ||--o{ MEMBERSHIP_APPLICATIONS : submits
USERS ||--o{ SIG_MEMBERS : joins_via
USERS ||--o{ PRIVACY_CONSENTS : records

CATEGORIES ||--o{ POSTS : contains
SIGS ||--o{ POSTS : contains
SIGS ||--o{ FORMS : hosts
SIGS ||--o{ SIG_MEMBERS : has

POSTS ||--o{ COMMENTS : has
POSTS ||--o{ POST_HISTORY : tracks_versions
POSTS ||--o{ POST_REPORTS : reported_on

FORMS ||--o{ FORM_RESPONSES : receives

COMMENTS ||--o{ COMMENTS : replies_to (self-ref via parent_id)
```

### 4.2 Table Definitions

#### USERS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | uuid4 |
| username | VARCHAR(50) | NOT NULL, UNIQUE, INDEX | |
| password_hash | VARCHAR(255) | NOT NULL | Argon2id |
| role | VARCHAR(20) | NOT NULL, default `MEMBER` | SUPER_ADMIN / ADMIN / MEMBER / GUEST |
| display_name | VARCHAR(100) | NOT NULL, default `''` | |
| avatar_url | VARCHAR(500) | NULL | MinIO object key (not presigned URL); presigned URL generated on read |
| orcid | VARCHAR(50) | NULL | |
| affiliation | VARCHAR(200) | NULL | |
| bio | TEXT | NULL | |
| is_deleted | BOOLEAN | NOT NULL, default `false` | GDPR anonymization flag |
| is_banned | BOOLEAN | NOT NULL, default `false` | Ban flag |
| ban_reason | TEXT | NULL | Reason recorded at time of ban |
| created_at | TIMESTAMPTZ | NOT NULL, server_default `now()` | |
| updated_at | TIMESTAMPTZ | NOT NULL, server_default `now()` | |

#### INVITE_CODES

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| code | VARCHAR(50) | NOT NULL, UNIQUE, INDEX | Format `INV-{8HEX}` |
| created_by | UUID | FK -> users.id | |
| expires_at | TIMESTAMPTZ | NOT NULL | 7-day expiry |
| consumed_at | TIMESTAMPTZ | NULL | Set when consumed |
| consumed_by | UUID | NULL, FK -> users.id | User who registered with this code |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### MEMBERSHIP_APPLICATIONS

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK -> users.id, INDEX |
| description | TEXT | NOT NULL |
| status | VARCHAR(20) | NOT NULL, default `PENDING` |
| reviewed_by | UUID | NULL, FK -> users.id |
| reviewed_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### PRIVACY_CONSENTS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK -> users.id, INDEX | |
| ip_address | VARCHAR(45) | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

Guest consent is recorded in Redis (`guest_consent:{user_id}` with session TTL), not in this table.

#### CATEGORIES

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL, UNIQUE |
| description | VARCHAR(500) | NULL |
| sub_admin_ids | UUID[] | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### POSTS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK -> users.id, INDEX | |
| category_id | UUID | NULL, FK -> categories.id, INDEX | |
| sig_id | UUID | NULL, FK -> sigs.id, INDEX | SIG association |
| title | VARCHAR(300) | NOT NULL | |
| content | TEXT | NOT NULL | HTML, sanitized server-side |
| keywords | TEXT[] | NULL | Up to 15 keywords |
| allow_comments | BOOLEAN | NOT NULL, default `true` | |
| version | INTEGER | NOT NULL, default `1` | Optimistic locking |
| comment_count | INTEGER | NOT NULL, default `0` | Denormalized counter |
| is_deleted | BOOLEAN | NOT NULL, default `false` | Soft delete |
| search_vector | TSVECTOR | NULL, GIN INDEX | Auto-updated by DB trigger |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Trigger:** `trg_posts_search_vector_update` -- BEFORE INSERT/UPDATE on `title, content`:
```sql
NEW.search_vector :=
    setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
```

#### POST_HISTORY

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| post_id | UUID | FK -> posts.id, INDEX |
| version | INTEGER | NOT NULL |
| title | VARCHAR(300) | NOT NULL |
| content | TEXT | NOT NULL |
| edited_at | TIMESTAMPTZ | NOT NULL, default `now()` |

#### COMMENTS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| post_id | UUID | FK -> posts.id, INDEX | |
| user_id | UUID | FK -> users.id, INDEX | |
| parent_id | UUID | NULL, FK -> comments.id (self-ref) | Flat thread with quote/reply |
| content | TEXT | NOT NULL | HTML, sanitized |
| mentions | TEXT[] | NULL | Array of usernames |
| reactions | JSONB | NULL | `{"LIKE": ["uid1", ...]}` |
| is_deleted | BOOLEAN | NOT NULL, default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### POST_REPORTS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| post_id | UUID | FK -> posts.id, INDEX | Reported post |
| user_id | UUID | FK -> users.id, INDEX | Reporter |
| reason | TEXT | NOT NULL | Free-text reason |
| status | VARCHAR(20) | NOT NULL, default `PENDING` | PENDING / REVIEWED / DISMISSED |
| reviewed_by | UUID | NULL, FK -> users.id | Admin who reviewed |
| reviewed_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### SIGS

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL, UNIQUE |
| description | TEXT | NULL |
| created_by | UUID | FK -> users.id |
| is_deleted | BOOLEAN | default `false` |
| member_count | INTEGER | default `0` |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### SIG_MEMBERS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| sig_id | UUID | FK -> sigs.id, INDEX | |
| user_id | UUID | FK -> users.id, INDEX | |
| role | VARCHAR(20) | NOT NULL, default `MEMBER` | ADMIN / SUB_ADMIN / MEMBER |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

Unique constraint: `(sig_id, user_id)`.

#### FORMS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| sig_id | UUID | FK -> sigs.id, INDEX | |
| created_by | UUID | FK -> users.id | |
| title | VARCHAR(300) | NOT NULL | |
| description | TEXT | NULL | |
| banner_url | VARCHAR(500) | NULL | MinIO object key |
| deadline | TIMESTAMPTZ | NULL | |
| max_respondents | INTEGER | NULL | |
| questions | JSONB | NOT NULL | Schema definition |
| is_schema_locked | BOOLEAN | default `false` | Locked after first response |
| is_deleted | BOOLEAN | default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### FORM_RESPONSES

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| form_id | UUID | FK -> forms.id, INDEX | |
| user_id | UUID | FK -> users.id | |
| answers | JSONB | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

Unique constraint: `(form_id, user_id)` -- one response per user per form.

#### NOTIFICATIONS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK -> users.id, INDEX | Receiver |
| trigger_user_id | UUID | NULL, FK -> users.id | Who caused the notification (NULL for system events) |
| action_type | VARCHAR(20) | NOT NULL | MENTION / REPLY / SYSTEM |
| entity_type | VARCHAR(20) | NULL | `post` or `comment` |
| entity_id | UUID | NULL | Post or Comment ID |
| message | TEXT | NOT NULL | Pre-rendered message text |
| is_read | BOOLEAN | default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |

#### AUDIT_LOGS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK -> users.id, INDEX | Actor |
| action | VARCHAR(100) | NOT NULL | e.g. LOGIN, LOGOUT, BAN, ROLE_CHANGE, ADMIN_DELETE_POST |
| target_type | VARCHAR(50) | NULL | e.g. `user`, `post`, `application` |
| target_id | UUID | NULL | |
| ip_address | VARCHAR(45) | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, INDEX | |

---

## 5. Authentication & Authorization

### 5.1 RBAC Permission Matrix

| Action | Super Admin | Admin | Member | Guest |
|--------|:-----------:|:-----:|:------:|:-----:|
| Browse public content | Y | Y | Y | Y (45 min) |
| Edit display name | Y | Y | Y | Y |
| Edit full profile (avatar, ORCID, etc.) | Y | Y | Y | N |
| Change password | Y | Y | Y | N |
| Create posts / comments / upload files | Y | Y | Y | N |
| Apply to become Member | N/A | N/A | N/A | Y |
| Generate invite codes | Y | Y | Y | N |
| Review Guest -> Member applications | Y | Y | N | N |
| Promote Member -> Admin | Y | N | N | N |
| Create SIG / Category | Y | Y | N | N |
| Assign SIG sub-admin | Y | Y | N | N |
| Create / export forms (within SIG, if SIG admin) | Y | Y | N | N |
| Ban / unban users | Y | N | N | N |
| View audit logs | Y | N | N | N |
| Access admin dashboard | Y | Y | N | N |

### 5.2 Authentication Flow

**Cookie-Based JWT:**

1. On successful login, register, or guest login, the server sets two cookies:
   - `access_token` (HttpOnly, Secure in production, SameSite=Lax) -- contains the JWT.
   - `csrf_token` (NOT HttpOnly, readable by JavaScript) -- random token for CSRF protection.
2. Every state-changing request (POST, PUT, PATCH, DELETE) must include the `X-CSRF-Token` header matching the `csrf_token` cookie value (double-submit cookie pattern).
3. On every authenticated request, the backend validates: (a) the `access_token` cookie JWT is not expired, (b) the JWT `jti` is not blacklisted in Redis, and (c) a Redis session key exists for the user.
4. The frontend stores only `role` and `expiresAt` in `localStorage` for UI state; the actual JWT never touches JavaScript.

**Password Hashing:** Argon2id via `passlib`.

**Password Policy:** Minimum 8 characters, at least one uppercase, one lowercase, one digit.

**CAPTCHA:** Server-generated image captcha, 4-char alphanumeric, stored in Redis with 5-minute TTL. Deleted on successful verification (one-time use). Required for: **login, registration, guest login**.

### 5.3 Session TTLs by Role

| Role | JWT Expiry | Redis Session TTL |
|------|-----------|-------------------|
| GUEST | 45 minutes | 45 minutes |
| MEMBER | 3 hours | 3 hours |
| ADMIN | 5 hours | 5 hours |
| SUPER_ADMIN | 8 hours | 8 hours |

### 5.4 Redis Key Schema

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `session:{role}:{user_id}` | Role-based | Active session token |
| `jwt:blacklist:{jti}` | 8 hours | Revoked JWT |
| `online_count:guest` | Persistent | Concurrent guest counter (max 30) |
| `captcha:{captcha_id}` | 5 minutes | One-time captcha code |
| `idempotency:{user_sha16}:{key}` | 5 minutes | POST/PUT replay prevention |
| `post_limit:{user_id}:{YYYY-MM-DD}` | 24 hours | Daily post count |
| `ws:ticket:{ticket}` | 30 seconds | One-time WebSocket auth ticket |
| `ws:user:{user_id}` | (Pub/Sub channel) | Real-time message delivery |
| `ws:logout:{user_id}` | (Pub/Sub channel) | Force-logout delivery |
| `rl:login:{ip}` | 60 seconds | Login rate limit counter |
| `rl:register:{ip}` | 60 seconds | Register rate limit counter |
| `rl:guest:{ip}` | 60 seconds | Guest login rate limit counter |
| `rl:invite:{user_id}` | 3600 seconds | Invite code generation rate limit counter |
| `rl:invite_verify:{ip}` | 60 seconds | Invite code verification rate limit counter |
| `rl:comment:{user_id}` | 60 seconds | Comment rate limit counter |
| `rl:notif:{user_id}` | 60 seconds | Notification list rate limit counter |
| `rl:notif_del:{user_id}` | 60 seconds | Notification delete rate limit counter |
| `guest:ip:{ip}` | 3600 seconds | Per-IP active guest session counter |

### 5.5 Account Lifecycle

- **Super Admin Bootstrap:** On startup, if `SUPER_ADMIN_USERNAME` does not exist in DB, auto-creates with `SUPER_ADMIN_PASSWORD` from `.env`. Supports creating additional Super Admins via UI.
- **Invite Codes:** Single-use, 7-day expiry, format `INV-{8HEX}`. Generated by Member, Admin, or Super Admin via `POST /auth/invite-code`. Members limited to 5 active codes at a time (rate-limited to 5 generations per hour). Admins can soft-revoke (`PATCH /admin/invite-codes/{id}/revoke`) or hard-delete (`DELETE /admin/invite-codes/{id}`); both actions are audit-logged. Marked as consumed (`consumed_at`, `consumed_by`) on first registration.
- **Guest Login:** Requires **invite code + captcha** (`POST /api/v1/auth/guest/{invite_code}`). Ephemeral -- Guest users exist only in Redis, not in the `users` table. Max 30 concurrent guests (global) and max 3 concurrent guest sessions per IP per hour enforced.
- **Guest 45-Minute Enforcement:** JWT `exp` = 45 min, Redis session TTL = 45 min, WebSocket server schedules `FORCE_LOGOUT` task at 45 min. HTTP 429 returned when guest capacity is reached.
- **Registration Captcha:** Required. Even though the system is invite-only, captcha provides defense-in-depth against automated abuse of leaked invite codes.
- **GDPR Anonymization:** `DELETE /api/v1/users/me` overwrites PII with `Deleted_User_{UUID}`, sets `is_banned=false`, `is_deleted=true`, invalidates session. DB entity and FKs preserved.
- **Ban:** Super Admin can ban a user via `POST /api/v1/users/{user_id}/ban`. Sets `is_banned=true`, records `ban_reason`, revokes all Redis sessions. Banned users receive 403 on next login. Unban via `POST /api/v1/users/{user_id}/unban`.

---

## 6. Academic Forum

### 6.1 Post Editor UI

- **Rich Text Editor:** Tiptap (ProseMirror-based, Vue 3 native). Extensions: bold, italic, underline, strikethrough, heading (H1-H3), bullet/ordered list, blockquote, code block, horizontal rule, link, image (via `/api/v1/files/upload/editor`), table.
- Attachment upload area showing uploaded files with delete button (single file max 20 MB).
- Category selector (single select).
- Keywords/tags input (Enter key to create, up to 15 per post).
- "Allow Comments" toggle.

### 6.2 Post List & Search

- Displays: title, author (clickable -> profile), category badge, publish date, comment count.
- Compound search bar: keyword input, category dropdown, date range picker, AND/OR logic toggle.
- Sort options: newest, oldest, most_comments.
- Pagination (page-based, default 20 per page).

### 6.3 Post Detail & History

- Edit History button (visible when `version > 1`): opens modal showing past version snapshots.
- **Report button:** Modal requesting reason text. Reports are queued for Admin manual review -- no automatic hiding. Admin sees reported posts in the `/admin/reports` dashboard and decides whether to delete or dismiss.
- Author and admins can edit/delete posts.
- Optimistic locking: update requires current `version`; 409 Conflict on mismatch.

### 6.4 Comments Section

- Flat thread display with quote/reply via `parent_id` (indented with border).
- @username autocomplete in comment input.
- Emoji reactions: LIKE, SMILE, CRY (toggle per user, stored in JSONB).
- Attachment upload support in comments.
- Comment editing (author only, `PUT /api/v1/posts/{id}/comments/{id}`).
- Max 200 comments per post.

### 6.5 Full-Text Search

- PostgreSQL `tsvector` column with GIN index on `posts.search_vector`.
- DB trigger auto-updates on INSERT/UPDATE of `title` (weight A) and `content` (weight B).
- Search API supports compound filters: keyword, category, tag array, date range, AND/OR operator.
- Response includes `total`, `total_pages`, `current_page`.

---

## 7. Special Interest Groups (SIGs)

### 7.1 SIG Directory

- Card-based list: SIG name, description, admin info, member count.
- Admin+ sees "Create SIG" button.
- Authenticated users can view the SIG directory and join SIGs.

### 7.2 SIG Internal Structure

- Post feed tab: mirrors Forum but filtered by `sig_id`.
- Forms tab: SIG-specific surveys/registration forms.
- Members tab: lists admins, sub-admins, and members.

### 7.3 SIG Roles

| Role | Assignment | Permissions |
|------|-----------|-------------|
| ADMIN | Global Admin+ assigns | Full SIG management, create/export forms, remove members |
| SUB_ADMIN | Global Admin+ assigns | Create/export forms |
| MEMBER | Auto-assigned on join | Post in SIG, submit forms |

### 7.4 SIG Deletion Cascade

When a SIG is soft-deleted (`is_deleted = true`), the application layer hides its Posts and Forms without setting `is_deleted` on child objects, preserving restoration flexibility.

### 7.5 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sigs` | Required | List all SIGs (paginated, `offset`/`limit`) |
| POST | `/sigs` | Admin+ | Create a SIG (409 if name exists) |
| GET | `/sigs/{sig_id}` | Required | Get SIG details |
| PUT | `/sigs/{sig_id}` | Admin+ or SIG ADMIN | Update SIG name/description |
| DELETE | `/sigs/{sig_id}` | Admin+ | Soft-delete SIG |
| POST | `/sigs/{sig_id}/sub-admin` | Admin+ | Assign sub-admin role to a member |
| GET | `/sigs/{sig_id}/posts` | Required | List SIG posts (paginated) |
| GET | `/sigs/{sig_id}/members` | Required | List SIG members (paginated) |
| DELETE | `/sigs/{sig_id}/members/me` | Member+ | Leave a SIG |
| DELETE | `/sigs/{sig_id}/members/{user_id}` | Admin+ or SIG ADMIN | Remove a member from a SIG |

---

## 8. Built-in Forms System

### 8.1 Form Builder UI (SIG Admin / Sub-Admin Only)

- Top section: banner upload, title, description, deadline (datetime picker), max respondents.
- Questions section: dynamic add/delete/reorder questions. Each question has:
  - Type: text, textarea, single-choice, multiple-choice, dropdown, rating (Likert scale), file upload.
  - Label text.
  - Required toggle.
  - Options list (for choice types, dynamic add/remove).
  - Placeholder text (for text/textarea types).

### 8.2 Form Submission UI

- Dynamic HTML rendering based on stored JSONB schema.
- Frontend validates required fields and file formats before submit.
- If past deadline or max respondents reached: all inputs disabled, "Closed" banner displayed.
- One response per user per form (enforced by unique constraint and service layer).

### 8.3 Schema Freeze Rule

After the first response is submitted, the form schema is locked (`is_schema_locked = true`). Only title, description, and deadline may be modified. Questions cannot be added, removed, or reordered.

### 8.4 JSONB Schema Design

The `forms.questions` column stores an ordered array of question objects:

```json
{
  "questions": [
    {
      "id": "q_uuid1",
      "type": "text",
      "label": "Your full name",
      "required": true,
      "placeholder": "Enter name...",
      "max_length": 500
    },
    {
      "id": "q_uuid2",
      "type": "single_choice",
      "label": "Research area",
      "required": true,
      "options": [
        {"id": "opt_1", "label": "NLP"},
        {"id": "opt_2", "label": "Computer Vision"},
        {"id": "opt_3", "label": "Other"}
      ]
    },
    {
      "id": "q_uuid3",
      "type": "rating",
      "label": "Rate your experience (1-5)",
      "required": false,
      "min": 1,
      "max": 5,
      "labels": {"1": "Poor", "5": "Excellent"}
    },
    {
      "id": "q_uuid4",
      "type": "file_upload",
      "label": "Upload your paper (PDF)",
      "required": false,
      "allowed_types": ["pdf"],
      "max_size_mb": 20
    }
  ]
}
```

**Question types:**

| Type | Input Rendered | Extra Fields |
|------|---------------|--------------|
| `text` | Single-line input | `placeholder`, `max_length` (default 500) |
| `textarea` | Multi-line input | `placeholder`, `max_length` (default 5000) |
| `single_choice` | Radio buttons | `options: [{id, label}]` |
| `multiple_choice` | Checkboxes | `options: [{id, label}]` |
| `dropdown` | Select element | `options: [{id, label}]` |
| `rating` | Likert scale buttons | `min`, `max`, `labels` (optional endpoint labels) |
| `file_upload` | File input | `allowed_types`, `max_size_mb` |

**Answers JSONB (`form_responses.answers`):**

```json
{
  "q_uuid1": "Alice Chen",
  "q_uuid2": "opt_1",
  "q_uuid3": 4,
  "q_uuid4": {"key": "forms/file_uuid.pdf", "filename": "paper.pdf"}
}
```

Server-side validation: iterate over `questions`, check `required` fields present in answers, validate type-specific constraints (max_length, option ID membership, rating range, file type).

### 8.5 CSV Export

- SIG Admin/Sub-Admin clicks "Export CSV" -> button enters loading state.
- Backend triggers async Celery task -> returns `task_id` (HTTP 202).
- Frontend polls `GET /api/v1/tasks/{task_id}/status` until `SUCCESS`.
- On completion, response includes `download_url` (presigned MinIO URL) -> browser auto-downloads.

### 8.6 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/sigs/{sig_id}/forms` | SIG Admin/Sub-Admin | Create form (max 20 active forms per SIG) |
| GET | `/sigs/{sig_id}/forms` | Required | List forms for a SIG (paginated) |
| GET | `/forms/{form_id}` | Required | Get form schema + `is_active`, `user_is_sig_admin` |
| PUT | `/forms/{form_id}` | SIG Admin/Sub-Admin | Update form (questions locked if `is_schema_locked`) |
| DELETE | `/forms/{form_id}` | SIG Admin/Sub-Admin or Admin+ | Soft-delete form |
| POST | `/forms/{form_id}/submit` | Member+ | Submit response (409 if already submitted) |
| POST | `/forms/{form_id}/export` | SIG Admin/Sub-Admin | Trigger async CSV export -> `{task_id}` |
| GET | `/tasks/{task_id}/status` | Required | Poll Celery task status -> `{task_id, status, download_url}` |

### 8.7 Quotas

- Max 20 active (non-deleted) forms per SIG.

---

## 9. Notification System

### 9.1 Design Philosophy

**No email service.** The platform avoids all external email or push services. Notifications are delivered via two channels only:

1. **Real-time:** WebSocket push when the user is online (connected via WS).
2. **Persistent storage:** All notifications are saved in the `notifications` DB table. When a user logs in or opens the app, unread notifications are fetched from the database and displayed via bell icon badge.

This design is self-contained -- no SMTP server, no third-party push service. Users who miss real-time notifications will see them on their next visit.

### 9.2 Notification Types

| Action Type | Trigger | Entity | Template |
|-------------|---------|--------|----------|
| MENTION | User @mentioned in a comment | comment | "{display_name} mentioned you in a comment" |
| REPLY | Someone replies to your comment | comment | "{display_name} replied to your comment" |
| SYSTEM | Application approved/rejected, role changed, post deleted by admin | varies | Context-specific message |

### 9.3 Notification UI

- **Navbar bell icon** with red badge showing unread count (fetched on app mount via `GET /api/v1/notifications?unread=true&page_size=0`).
- **Dropdown list** of recent 10 notifications on bell click (lazy-loaded on first click).
- **"View All"** link -> full `/notifications` page with paginated list.
- Each notification shows: trigger user's display name (or "Deleted User"), message text, relative timestamp.
- Click -> marks as read (style dims), Vue Router navigates to the related entity.
- Individual delete via `DELETE /api/v1/notifications/{id}`.

### 9.4 Real-Time Delivery Flow

1. Backend event occurs (e.g., comment created with `@alice`).
2. Service layer inserts row into `notifications` table.
3. Service publishes `NEW_NOTIFICATION` message to Redis Pub/Sub channel `ws:user:{target_user_id}`.
4. The Redis Pub/Sub subscriber task (started in FastAPI lifespan) receives the message and calls `_local_send()` for any local WebSocket connections.
5. If the user is offline: notification waits in DB, user sees it on next login/page load.

This architecture supports future horizontal scaling: multiple FastAPI workers each subscribe to the same Redis channels.

### 9.5 RTBF Protection

Notification records store `trigger_user_id` only (no hardcoded display names). Frontend dynamically resolves display names from the users table. If the trigger user is deleted, the notification renders as "Deleted User" automatically.

### 9.6 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | Required | List user's notifications (paginated, `?unread=true` filter) |
| PUT | `/notifications/{id}/read` | Required | Mark single notification as read |
| PUT | `/notifications/read-all` | Required | Mark all notifications as read |
| DELETE | `/notifications/{id}` | Required | Delete a notification |

---

## 10. File Upload & Storage

### 10.1 Storage Architecture

MinIO (S3-compatible), single bucket `ai3l-uploads`, private access. Files served via presigned URLs generated on demand.

**Key namespaces:**
- `avatars/{user_id}/{uuid}.{ext}` -- Profile avatars
- `editor/{user_id}/{uuid}.{ext}` -- Rich text editor attachments

**URL strategy:** `users.avatar_url` and `forms.banner_url` store the MinIO object key, not a presigned URL. Fresh presigned URLs are generated when serving profile data, eliminating the need for a URL refresh mechanism.

### 10.2 Avatar Upload

- Endpoint: `PUT /api/v1/users/me/avatar`
- Allowed: PNG, JPEG only.
- Max size: 2 MB.
- Stores MinIO object key in `users.avatar_url`.

### 10.3 Editor File Upload

- Endpoint: `POST /api/v1/files/upload/editor`
- Allowed: PNG, JPEG, PDF, DOCX.
- Max size: 20 MB.
- **Magic number validation:** File bytes compared against expected signatures (not just Content-Type header).
- After upload: VirusTotal hash check triggered asynchronously via Celery (non-blocking).
- Returns 7-day presigned URL.

### 10.4 Presigned URL Expiry

| File Type | Endpoint | Expiry |
|-----------|---------|--------|
| Editor upload (immediate) | `POST /files/upload/editor` | 7 days |
| On-demand download | `GET /files/presigned/{key}` | 1 hour |
| Avatar (generated on profile read) | (internal) | 7 days |

### 10.5 File Security

| Defense | Implementation |
|---------|---------------|
| Magic number validation | Byte signature check for PNG (`\x89PNG`), JPEG (`\xFF\xD8\xFF`), PDF (`%PDF`), DOCX (`PK\x03\x04`) |
| HTML sanitization | Server-side sanitization (`app.core.file_validation.sanitize_html`) using allowlist of safe tags; DOMPurify on frontend before rendering |
| PDF sanitization | Strip `/JS`, `/JavaScript`, `/AA`, `/OpenAction` from uploaded PDFs via pikepdf (C++ qpdf engine); invalid PDFs rejected before storage |
| VirusTotal integration | Celery task computes local SHA-256 hash, queries VT API with hash only (never uploads raw file) |
| Size limits | 2 MB (avatars), 20 MB (editor files), 25 MB (Nginx `client_max_body_size`) |
| Path traversal | `GET /files/presigned/{key}` validates key against `^[a-zA-Z0-9/_.\-]+$` and rejects `..` |

### 10.6 Per-User Storage Quota

Each user account has a total storage limit of 1 GB (all avatars + attachments combined). Enforced at upload time: `GET /users/me` (storage used tracked via `async_storage.get_user_storage_used()`). Exceeding the limit returns 400.

---

## 11. Full API Specification

**Base URL:** `/api/v1`
**Auth:** HttpOnly cookie `access_token` (set automatically on login/register/guest login).
**CSRF Header:** `X-CSRF-Token: {csrf_token_cookie_value}` required on all POST/PUT/PATCH/DELETE requests (except login, register, guest login, and captcha endpoints).
**Idempotency Header:** `Idempotency-Key: {uuid}` (POST/PUT write operations, no `X-` prefix per RFC 6648). Backend stores in Redis with 300s TTL. Duplicate key within window returns cached response (or 409 if still processing).

### 11.1 Health

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/health` | None | `{"status": "healthy", "dependencies": [{name, status, latency_ms}]}` |

### 11.2 Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/captcha` | None | Generate captcha image -> `{captcha_id, image_base64}` |
| POST | `/auth/login` | None | Login (captcha required) -> sets `access_token` + `csrf_token` cookies; returns `{role, expires_in, requires_consent}` |
| POST | `/auth/guest/{invite_code}` | None | Guest login with invite code + captcha -> Guest session cookies |
| POST | `/auth/logout` | Required | Invalidate session, blacklist JWT, clear cookies |
| POST | `/auth/register` | None | Create account (invite code + captcha required) -> sets session cookies; returns `{role, expires_in, requires_consent}` |
| POST | `/auth/heartbeat` | Required | Refresh Redis session TTL -> full role TTL reset (client calls every 30 s) |
| POST | `/auth/ws-ticket` | Required | Generate one-time WebSocket auth ticket (30 s TTL) -> `{ticket}` |
| POST | `/auth/invite-code` | Member+ | Generate single-use invite code (7-day expiry) -> `{invite_code, expires_at}` |
| GET | `/auth/invite-code/{code}` | None | Validate invite code -> 200 if valid, 404 if invalid/expired |

### 11.3 Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Required | Get own profile |
| PUT | `/users/me` | Required | Update profile fields (display_name, bio, affiliation, orcid) |
| PUT | `/users/me/avatar` | Required | Upload avatar (PNG/JPEG, 2 MB max) |
| PUT | `/users/me/password` | Member+ | Change password (requires current password; session invalidated on success) |
| POST | `/users/me/consent` | Required | Record privacy consent acceptance |
| DELETE | `/users/me` | Required | GDPR anonymization (session invalidated) |
| GET | `/users` | Admin+ | List all users (paginated, `offset`/`limit`) |
| POST | `/users/admin/create-account` | Admin+ | Create account directly (only Super Admin can create Admin role) |
| PUT | `/users/{user_id}/role` | Super Admin | Change role (revokes target sessions; cannot self-demote) |
| POST | `/users/{user_id}/ban` | Super Admin | Ban user with reason (revokes sessions) |
| POST | `/users/{user_id}/unban` | Super Admin | Unban user |
| GET | `/users/admin/audit-logs` | Super Admin | List audit logs (paginated, `?user_id=` filter) |

### 11.4 Applications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/users/apply-member` | Guest only | Submit membership application |
| GET | `/admin/applications` | Admin+ | List applications (filterable by `?status=`) |
| PUT | `/admin/applications/{app_id}/review` | Admin+ | Approve or reject (auto-promotes to Member on approve) |

### 11.5 Categories

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/categories` | Required | List all categories |
| POST | `/categories` | Admin+ | Create category (409 if name exists) |
| PUT | `/categories/{category_id}` | Admin+ | Update category name/description |
| DELETE | `/categories/{category_id}` | Admin+ | Delete category |

### 11.6 Posts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/posts` | Member+ | Create post (sanitized, 50/day limit) |
| GET | `/posts` | Required | List posts (paginated; `?category_id=`, `?sort=newest\|oldest\|most_comments`) |
| POST | `/posts/search` | Required | Full-text search with compound filters |
| GET | `/posts/{post_id}` | Required | Get single post |
| PUT | `/posts/{post_id}` | Member+ | Update post (optimistic locking via `version`, saves history) |
| DELETE | `/posts/{post_id}` | Member+ | Soft delete (admins can delete any; members own only) |
| GET | `/posts/{post_id}/history` | Required | Get all edit history snapshots |

### 11.7 Comments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/posts/{post_id}/comments` | Required | List comments (`offset`/`limit`, max 200) |
| POST | `/posts/{post_id}/comments` | Member+ | Create comment (30/min rate limit; `parent_id` for reply; `mentions` array) |
| PUT | `/posts/{post_id}/comments/{comment_id}` | Member+ | Edit own comment |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | Member+ | Soft delete comment (author or admin) |
| POST | `/posts/{post_id}/comments/{comment_id}/reactions` | Member+ | Toggle reaction (LIKE/SMILE/CRY) |

### 11.8 Reports

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/posts/{post_id}/report` | Member+ | Report a post with free-text reason (409 if already reported by this user) |
| GET | `/admin/reports` | Admin+ | List reports (filterable by `?status_filter=`; `offset`/`limit`) |
| PUT | `/admin/reports/{report_id}/review` | Admin+ | Set status to REVIEWED or DISMISSED |

### 11.9 Files

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/files/upload/editor` | Member+ | Upload PNG/JPEG/PDF/DOCX (20 MB, magic validated, async VirusTotal check) |
| GET | `/files/presigned/{key:path}` | Member+ | Get 1-hour presigned download URL (admin: any file; member: own files only) |

### 11.10 SIGs

See Section 7.5.

### 11.11 Forms & Tasks

See Section 8.6.

### 11.12 Notifications

See Section 9.6.

### 11.13 Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/dashboard` | Admin+ | Platform stats (user count, post count, active guests, etc.) |
| GET | `/admin/invite-codes` | Admin+ | List all invite codes (filterable by `?status=`; `offset`/`limit`) |
| PATCH | `/admin/invite-codes/{id}/revoke` | Admin+ | Soft-revoke active invite code (sets `expires_at = NOW()`; audit-logged) |
| DELETE | `/admin/invite-codes/{id}` | Admin+ | Hard-delete invite code (audit-logged) |

### 11.14 WebSocket

| Protocol | Path | Auth |
|----------|------|------|
| WS | `/api/v1/ws?ticket={ticket}` | One-time ticket from `POST /auth/ws-ticket` |

**WebSocket ticket flow:**
1. Client calls `POST /auth/ws-ticket` (authenticated via cookie) to obtain a single-use 30-second ticket.
2. Client connects `WS /api/v1/ws?ticket={ticket}`.
3. Server validates ticket from Redis (deletes on use -- truly one-time).
4. Connection registered in in-memory registry.

**Server-initiated messages:**
- `{"type": "PING", "timestamp": <float>}` (every 30 s) -- client must reply `{"type": "PONG"}` within 90 s or connection is closed (code 4002).
- `{"type": "FORCE_LOGOUT"}` -- forces client disconnect (code 4003); triggered on ban or guest 45-min timeout.
- `{"type": "NEW_NOTIFICATION", ...}` -- real-time notification push from Redis Pub/Sub.

**Client reconnection:** Exponential backoff (initial 1 s, max 30 s). Page Visibility API pauses reconnect on `document.hidden`.

---

## 12. Frontend Pages & Components

### 12.1 Routes

| Path | Component | Auth Guard | Description |
|------|-----------|------------|-------------|
| `/` | HomeView | None | Landing page / welcome |
| `/login` | LoginView | Guest-only | Username + password + captcha |
| `/register` | RegisterView | Guest-only | Account creation with invite code + captcha |
| `/guest` | GuestLoginView | Guest-only | Guest login with display name + invite code + captcha |
| `/profile` | ProfileView | requiresAuth | Edit profile, upload avatar, change password |
| `/notifications` | NotificationsView | requiresAuth | Full paginated notification list |
| `/forum` | ForumView | requiresAuth | Post list, search, filter, pagination |
| `/forum/create` | PostCreateView | requiresAuth | Create new post |
| `/forum/:id` | PostDetailView | requiresAuth | View/edit post, comments, reactions, history |
| `/sigs` | SigsDirectoryView | requiresAuth | SIG listing |
| `/sigs/:id` | SigDetailView | requiresAuth | SIG posts / forms / members tabs |
| `/sigs/:sigId/forms/new` | FormBuilderView | requiresAuth | Create new form (SIG admin/sub-admin) |
| `/forms/:formId` | FormView | requiresAuth | Form submission |
| `/forms/:formId/edit` | FormBuilderView | requiresAuth | Edit existing form (SIG admin/sub-admin) |
| `/admin` | AdminDashboardView | requiresAdmin | Platform statistics dashboard |
| `/admin/users` | UsersView | requiresAdmin | User management, role changes, create accounts, ban/unban |
| `/admin/applications` | ApplicationsView | requiresAdmin | Review membership applications |
| `/admin/reports` | ReportsView | requiresAdmin | Review post reports |
| `/admin/invite-codes` | InviteCodesView | requiresAdmin | View and manage invite codes |
| `/admin/audit-logs` | AuditLogsView | requiresSuperAdmin | View audit log (Super Admin only) |
| `/:pathMatch(.*)` | NotFoundView | None | 404 fallback |

### 12.2 Shared Components

| Component | Description |
|-----------|-------------|
| AppNavbar | Sticky top nav: logo, Forum/SIGs links, admin dropdown, user dropdown with role badge, notification bell |
| ToastNotification | Fixed toast stack, listens to toast Pinia store events, 5 s auto-dismiss |
| NotificationBell | Navbar bell icon with unread count badge; dropdown showing latest 10 notifications |
| TiptapEditor | Tiptap WYSIWYG editor with toolbar (bold, italic, heading, list, code block, image upload, table) + DOMPurify output sanitization |
| PrivacyConsentModal | Full-screen modal shown when `requires_consent` is true after login/register/guest login |
| SkeletonLoader | Loading placeholder for list and detail views |
| EmptyState | Reusable empty state component with icon, title, and optional action button |

### 12.3 Base Component Library

| Component | Description |
|-----------|-------------|
| BaseAlert | Alert/notice box with severity levels |
| BaseBadge | Pill badge for roles, statuses |
| BaseButton | Button with variant (primary, secondary, danger) and loading state |
| BaseCard | Card container |
| BaseInput | Text input with label, error, and hint |
| BaseModal | Accessible modal dialog |
| BasePagination | Page-based pagination controls |
| BaseSelect | Styled select dropdown |
| BaseTable | Sortable data table |
| BaseTextarea | Textarea with label and error |

### 12.4 State Management (Pinia)

**Auth Store (`stores/auth.ts`):**
- State: `role`, `expiresAt` (localStorage persisted), `user` (UserProfile object), `requiresConsent`
- Computed: `isAuthenticated`, `isAdmin`, `isSuperAdmin`, `isGuest`
- Actions: `login()`, `guestLogin()`, `register()`, `logout()`, `fetchProfile()`
- 30-second heartbeat interval (auto-starts on authenticated page load)
- JWT is in HttpOnly cookie; only `role` and `expiresAt` in localStorage for UI state

**Notifications Store (`stores/notifications.ts`):**
- State: `notifications`, `unreadCount`
- Actions: fetch, mark read, delete

**Toast Store (`stores/toast.ts`):**
- State: `toasts` list
- Actions: `add()`, `remove()`

**Axios API Client (`composables/api.ts`):**
- Base URL: `/api/v1`, 15 s timeout
- Request interceptor: reads `csrf_token` cookie and injects `X-CSRF-Token` header on state-changing requests
- Response interceptor: 401 -> clear session + redirect to login; 429 -> dispatch toast with Retry-After

---

## 13. Security & Threat Model

### 13.1 XSS Prevention

- **Backend:** Server-side HTML sanitization on all post/comment content before storage (allowlist of safe HTML tags). Allowed tags include: `p, br, strong, em, u, s, h1-h6, ul, ol, li, blockquote, pre, code, a, img, table, thead, tbody, tr, th, td, span, div, sub, sup, hr`.
- **Frontend:** DOMPurify before rendering any user-generated HTML content. Tiptap editor output is sanitized before display, not on input.

### 13.2 CSRF Protection

**Double-submit cookie pattern:**
1. On login/register/guest login, server sets `csrf_token` cookie (NOT HttpOnly).
2. JavaScript reads this cookie and injects it as the `X-CSRF-Token` header on every state-changing request.
3. `CSRFMiddleware` compares the cookie value to the header value. Mismatch returns 403.

Exempt paths (user does not yet have a CSRF token): `/auth/login`, `/auth/register`, `/auth/guest/...`, `/auth/captcha`.

### 13.3 Content Security Policy

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: <minio-domain>;
font-src 'self';
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

`<minio-domain>` in `img-src` must be updated once the production domain and MinIO endpoint are confirmed.

### 13.4 CORS Policy

Strict `allow_origins` from `CORS_ORIGINS` environment variable. Wildcard (`*`) is prohibited. `allow_credentials=True` enabled. `allow_headers` is restricted to `["Content-Type", "X-CSRF-Token", "X-Idempotency-Key"]`.

### 13.5 File Upload Defense

| Layer | Check |
|-------|-------|
| Extension whitelist | .png, .jpg, .jpeg, .pdf, .docx |
| Magic number | Byte signature validation |
| Size limit | 2 MB (avatar), 20 MB (editor), 25 MB (Nginx) |
| Path traversal | Key regex `^[a-zA-Z0-9/_.\-]+$` + `..` rejection |
| Sanitization | HTML sanitization (server-side allowlist); PDF script stripping via pikepdf (`/JS`, `/JavaScript`, `/AA`, `/OpenAction`) |
| Antivirus | VirusTotal hash-only query via Celery (non-blocking; upload not gated on result) |

### 13.6 Password Security

- Argon2id hashing (via passlib)
- Policy: 8+ chars, uppercase, lowercase, digit
- No plaintext storage anywhere
- Password changes are audit-logged as `PASSWORD_CHANGE` action and revoke all existing sessions

### 13.7 Session Security

- JWT stored in HttpOnly cookie (inaccessible to JavaScript)
- CSRF double-submit cookie for state-changing requests
- JWT + Redis dual validation on every request
- JWT blacklisting on logout
- Session invalidation on role change and ban
- No session sharing across roles
- Trusted host middleware in production (prevents Host header injection); disabled with warning log if `TRUSTED_HOSTS` is not configured
- On startup in production mode, warnings are logged for any credential still set to its default `changeme_*` value and if `COOKIE_SECURE=false`

### 13.8 Banned User Handling

- `is_banned=true` checked on every login attempt; returns 403 with `AUTH_004` error code.
- All Redis sessions revoked at ban time.
- Re-login is blocked even with valid credentials.

---

## 14. Resource Quotas & Rate Limiting

### 14.1 Nginx Rate Limiting

| Zone | Rate | Burst | Applied To |
|------|------|-------|------------|
| `global` | 20 req/s | 10 | All `/api/` routes |
| `write` | 5 req/min | 5 (dev) / 2 (prod) | POST/PUT/DELETE `/api/v1/(posts\|comments\|forms)` only; GET/HEAD exempt |

On 429: Nginx returns HTTP 429 Too Many Requests. Frontend interceptor shows toast: "You are performing actions too frequently. Please try again in N seconds."

### 14.2 Application-Level Rate Limits (Redis)

| Endpoint | Limit | Window | Key |
|----------|-------|--------|-----|
| Login | 10 attempts | per IP per 60 s | `rl:login:{ip}` |
| Register | 5 attempts | per IP per 60 s | `rl:register:{ip}` |
| Guest login | 10 attempts | per IP per 60 s | `rl:guest:{ip}` |
| Invite code generation | 5 codes | per user per 3600 s | `rl:invite:{user_id}` |
| Invite code verification | 30 checks | per IP per 60 s | `rl:invite_verify:{ip}` |
| Comment creation | 30 comments | per user per 60 s | `rl:comment:{user_id}` |
| Report post | 5 reports | per user per 60 s | `rl:report:{user_id}` |
| File upload | 10 uploads | per user per 60 s | `rl:file_upload:{user_id}` |
| Form submission | 5 submits | per user per 60 s | `rl:form_submit:{user_id}` |
| Notification list | 60 requests | per user per 60 s | `rl:notif:{user_id}` |
| Notification delete | 30 requests | per user per 60 s | `rl:notif_del:{user_id}` |

### 14.3 Application-Level Quotas

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Posts per user per day | 50 | Redis counter `post_limit:{uid}:{date}` |
| Comments per post | 200 | Service-layer check on `comment_count` |
| Concurrent guests (global) | 30 | Redis atomic counter `online_count:guest` |
| Concurrent guest sessions per IP | 3 / hour | Redis counter `guest:ip:{ip}` |
| Active invite codes per user | 5 | DB count check at generation time |
| Keywords per post | 15 | Schema validation |
| Storage per user | 1 GB | Checked at upload time |
| Active forms per SIG | 20 | Service-layer check |
| WebSocket messages per connection | 60 / min | In-memory counter per connection |
| WebSocket message size | 64 KB | Checked on receive; connection closed on violation |

---

## 15. Engineering Guidelines

### 15.1 Transaction Consistency

All cross-table writes (e.g., create comment + increment post counter) must be wrapped in `async with conn.transaction():` for ACID atomicity.

### 15.2 Idempotency

POST/PUT operations accept `Idempotency-Key` header (alphanumeric + hyphen, max 256 chars, no `X-` prefix per RFC 6648). Backend stores in Redis with 300 s TTL. Duplicate key within window returns cached response (or 409 if still processing). Keys are namespaced by user token hash to prevent cross-user collisions.

### 15.3 Database Architecture

- **SQLAlchemy ORM** is used for model definition (enabling Alembic migration autogeneration) and eager-loaded relationship traversal in select queries.
- **All runtime write queries and performance-sensitive reads** use raw `asyncpg` via connection pool (`pool.acquire()` + `conn.fetchrow/fetch/execute`).
- The `server_default` parameter (not Python `default`) must be used for columns that need DB-level defaults (asyncpg bypasses Python-side defaults).
- The **Repository layer** encapsulates all DB access. Services call repositories; endpoints call services.
- The **Converter layer** transforms raw asyncpg `Record` dicts into Pydantic response schemas.

### 15.4 API Versioning

All routes prefixed with `/api/v1`. Semantic versioning (`vX.Y.Z`) for frontend and backend releases.

### 15.5 Database Migration Policy

- **Tool:** Alembic only. Manual `ALTER TABLE` on production is prohibited.
- **Backward compatibility:** All schema changes must be zero-downtime compatible.
- **Column rename/delete:** Three-phase deployment (Expand -> Migrate Data -> Contract).

### 15.6 WebSocket Reliability

- **Server-initiated ping:** Every 30 s (`WS_PING_INTERVAL`). Client auto-responds with PONG. 90 s timeout (`WS_PING_TIMEOUT`) -> disconnect (code 4002).
- **Heartbeat TTL:** Full role TTL reset on each HTTP heartbeat call (every 30 s by client).
- **Client reconnection:** Exponential backoff (initial 1 s, max 30 s).
- **Page Visibility API:** Pause reconnect on `document.hidden`, graceful reconnect on visible.
- **Multi-worker support:** WebSocket messages are published via Redis Pub/Sub (`ws:user:{id}` channels). All worker instances subscribe and deliver to their local connections.

### 15.7 Event Bus

An in-process event bus (`app.core.event_bus`) decouples side-effect handlers (audit logging, notifications) from core service logic. Events are emitted as fire-and-forget coroutines. Handlers are registered in `app.event_handlers.register_all()` called from the FastAPI lifespan.

---

## 16. DevOps & Observability

### 16.1 CI/CD

Three GitHub Actions workflows:
- `backend-ci.yml` -- lint (flake8, mypy) + pytest on push
- `frontend-ci.yml` -- ESLint + Prettier + Vitest + Playwright on push
- `docker-build.yml` -- Docker image build verification

Merge requests blocked on test failure.

### 16.2 Testing Strategy

| Type | Tool | Target |
|------|------|--------|
| Backend unit/integration | pytest + pytest-asyncio | Service layer and repositories; 38 test files |
| Frontend unit | Vitest | Components and stores |
| Frontend E2E | Playwright | Core flows: login, post creation |
| Linting | flake8 + mypy (Python), ESLint v9 + Prettier (Vue/TS) | All source files |

### 16.3 Structured Logging

Loguru JSON format to stderr. Docker json-file log driver captures output.

**Required fields per log entry:**
- `timestamp`
- `level` (INFO, WARNING, ERROR)
- `message`
- `user_id` (if authenticated, injected contextually)

Nginx uses `json_combined` log format including `request_id` for trace correlation.

**Log level guidelines:**
- **INFO:** Core business events (login, post creation, Super Admin bootstrap)
- **WARNING:** Tolerable anomalies (rate limit hit, wrong password, 404, storage init skipped)
- **ERROR:** System failures (DB connection lost, 500 errors)

### 16.4 Sentry

Sentry SDK initialized in FastAPI lifespan on startup when `SENTRY_DSN` is set. Captures unhandled exceptions and performance traces at `SENTRY_TRACES_SAMPLE_RATE`. Does not start in development if `SENTRY_DSN` is empty.

### 16.5 Datadog

Datadog agent runs as an optional Docker Compose service (`--profile monitoring`). FastAPI traces patched via `ddtrace.patch_all()` on startup when `DD_TRACE_ENABLED=true`.

### 16.6 SLA & SLO

| Metric | Target |
|--------|--------|
| Uptime | 99.9% |
| API latency (P95) | < 300 ms (excluding large file transfers) |
| DB query time | < 50 ms for core list queries with joins |

---

## 17. Error Code Registry

| Code | HTTP Status | Meaning |
|------|------------|---------|
| AUTH_001 | 401 | Token expired / invalid / missing Redis session |
| AUTH_002 | 401 | Token in blacklist (revoked) |
| AUTH_003 | 429 | Guest limit reached (30 concurrent) |
| AUTH_004 | 403 | Account is banned |
| SYS_403 | 403 | Forbidden (generic) |
| SYS_404 | 404 | Entity not found |
| SYS_409 | 409 | Version conflict / idempotency key conflict |
| SYS_422 | 422 | Validation error |
| SYS_429 | 429 | Rate limit exceeded |
| FILE_001 | 400 | Invalid magic number / malware detected |
| FORM_001 | 400 | Form deadline passed or max respondents reached |

---

## 18. Implementation Status

### Completed

| Phase | Scope | Commit |
|-------|-------|--------|
| Phase 0 | Infrastructure: Docker Compose (7 services + optional Datadog), Nginx, CI/CD, CODEOWNERS | `62e58d4` |
| Phase 1A | DB models (User, InviteCode), JWT+Redis auth, HttpOnly cookie auth, CSRF middleware, captcha, RBAC, guest limits | `ac7b502` |
| Phase 1B | Admin APIs, membership applications, avatar upload, idempotency middleware, WebSocket, frontend auth UI (10+ pages) | `1308c28` |
| Phase 2 | Forum: Categories, Posts (CRUD + optimistic locking + FTS), PostHistory, Comments (threaded + reactions + edit + delete), file upload with magic validation, HTML sanitization | `d65d463` |
| Phase 3 | SIGs (CRUD, sub-admin, leave, remove member, directory UI, internal post feed), Post Reports (submit + admin review), WebSocket ticket auth, Redis Pub/Sub multi-worker WS, guest force-logout, WS exponential backoff, DOMPurify frontend, Tiptap editor | (post-d65d463) |
| Phase 4 | Forms: JSONB schema builder UI, submission, schema freeze, one-response-per-user constraint, Celery CSV export, task polling | (post-Phase 3) |
| Phase 5 | Notifications: DB model, MENTION/REPLY/SYSTEM triggers, WebSocket push via Redis Pub/Sub, NotificationBell UI, NotificationsView | (post-Phase 4) |
| Phase 6 | Audit logs (event bus + DB), user ban/unban, Sentry init in lifespan, privacy consent modal + API, password change API, invite code management (admin view + consumption tracking), storage quota enforcement, AdminDashboardView, structured error codes | (post-Phase 5) |

### Phase 7 Remaining (Pre-deploy)

| Item | Status |
|------|--------|
| Domain name confirmed | Pending |
| HTTPS Nginx config (`server_name`, certs) | Config ready; pending domain |
| `COOKIE_SECURE=true` in production `.env` | Pending domain |
| CSP `img-src` MinIO domain | Pending domain |
| `TRUSTED_HOSTS` set in production `.env` | Pending domain |
| PDF script stripping (sanitize uploaded PDFs) | Complete |
| 80% backend test coverage | In progress (38 test files exist) |
| Database backup automation | `scripts/backup-db.sh` exists; cron scheduling pending |
| Datadog production configuration | `--profile monitoring` ready; API key pending |

### No Outstanding Known Gaps

All items previously listed as "known gaps" in v1.1.0 have been resolved:

| Item | Resolution |
|------|-----------|
| Guest login requires invite code | Implemented: `POST /auth/guest/{invite_code}` |
| Guest limit returns 429 (not 503) | Fixed: `AUTH_003` mapped to 429 |
| Member can generate invite codes | Implemented: `require_role("SUPER_ADMIN", "ADMIN", "MEMBER")` |
| Idempotency header name `Idempotency-Key` | Implemented: `IDEMPOTENCY_HEADER = "Idempotency-Key"` |
| Registration captcha | Implemented: `verify_captcha()` called in `POST /auth/register` |
| Tiptap rich text editor | Implemented: `TiptapEditor.vue` |
| DOMPurify frontend sanitization | Implemented |
| Comment delete endpoint | Implemented: `DELETE /posts/{id}/comments/{id}` |
| Post report + admin review | Implemented: full reports endpoints and `ReportsView.vue` |
| Privacy consent modal UI | Implemented: `PrivacyConsentModal.vue` + `POST /users/me/consent` |
| WS 45-min guest force logout | Implemented: `asyncio.create_task(_guest_timeout())` in WS handler |
| WS exponential backoff | Implemented in frontend `useWebSocket.ts` |
| Page Visibility API | Implemented in frontend WS composable |
| Sentry initialization | Implemented in FastAPI lifespan |
| Avatar URL refresh mechanism | Resolved by storing object key instead of presigned URL |
| Comment edit endpoint | Implemented: `PUT /posts/{id}/comments/{id}` |
| User unban endpoint | Implemented: `POST /users/{id}/unban` |
