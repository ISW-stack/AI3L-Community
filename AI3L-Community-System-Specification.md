# AI3L Community — System Design & Specification

> **Version:** 1.1.0
> **Last Updated:** 2026-02-28
> **Status:** Phase 2 Complete (Forum), Phases 3–7 Pending

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
- **Data Residency Disclosure:** Mandatory privacy consent at registration/first login stating data is stored in Hong Kong.
- **Search Engine Blocking:** `robots.txt` Disallow all, `X-Robots-Tag: noindex, nofollow` on all responses.

---

## 2. System Architecture & Tech Stack

### 2.1 Architecture

Decoupled full-stack architecture (frontend and backend fully separated).

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Vue 3 (Composition API) + TypeScript + Vite + Tailwind CSS v4 | SPA served by Nginx |
| **Backend** | Python 3.11 + FastAPI | Controller-Service-Model, async |
| **Database** | PostgreSQL 15+ (asyncpg driver) | Raw async queries, NOT ORM sessions |
| **Cache & State** | Redis 7 (AOF + RDB hybrid persistence) | Sessions, counters, rate limits |
| **Task Queue** | Celery + Redis | Async CSV export, file scanning |
| **File Storage** | MinIO (S3-compatible) | Avatars, editor attachments |
| **Reverse Proxy** | Nginx 1.25 | TLS termination, rate limiting, SPA serving |
| **Observability** | Sentry Cloud (errors), Datadog (metrics) | SaaS to avoid local memory pressure |

### 2.2 Deployment Topology

```
Client (Browser)
    │
    ▼ HTTP/HTTPS :80/:443
┌──────────────────────────────────────────┐
│         Docker Compose Environment        │
│                                          │
│  Nginx ──► FastAPI (:8000)               │
│    │              │                      │
│    │       ┌──────┼──────┐               │
│    │       ▼      ▼      ▼               │
│    │    PostgreSQL Redis  MinIO           │
│    │              ▲                      │
│    │              │                      │
│    │         Celery Worker               │
│    │                                     │
│    └──► Vue SPA (static files)           │
└──────────────────────────────────────────┘
         │              │
         ▼              ▼
     Sentry Cloud    Datadog
```

### 2.3 Scaling Trigger

MinIO initially co-exists on the same server. If concurrent traffic exceeds 200 users or disk I/O reaches warning thresholds (large file I/O delaying PostgreSQL fsync), MinIO must be separated to an independent storage instance.

---

## 3. Infrastructure & Deployment

### 3.1 Docker Services

| Service | Image | CPU | Memory | Health Check |
|---------|-------|-----|--------|-------------|
| nginx | nginx:1.25-alpine | 0.5 | 256 MB | `wget http://127.0.0.1/health-nginx` |
| fastapi | ./backend (Python 3.11-slim) | 2.0 | 3 GB | urllib `http://localhost:8000/api/v1/health` |
| postgres | postgres:15-alpine | 2.0 | 4 GB | `pg_isready` |
| redis | redis:7-alpine | 0.5 | 1 GB | `redis-cli ping` |
| celery | ./backend | 1.0 | 1.5 GB | `celery inspect ping` |
| minio | minio/minio:latest | 1.0 | 1.5 GB | `mc ready local` |

### 3.2 Ports

**Production** (via Nginx):

| Port | Service |
|------|---------|
| 10080 | HTTP |
| 10443 | HTTPS |

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

### 3.6 Environment Variables

Defined in `.env.example` (`.env` is gitignored):

| Group | Variables |
|-------|----------|
| PostgreSQL | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` |
| FastAPI | `FASTAPI_ENV`, `FASTAPI_DEBUG`, `SECRET_KEY` |
| JWT | `JWT_SECRET_KEY`, `JWT_ALGORITHM` |
| CORS | `CORS_ORIGINS` (comma-separated origins) |
| MinIO | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_BUCKET_NAME`, `MINIO_USE_SSL` |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Sentry | `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` |
| Datadog | `DD_AGENT_HOST`, `DD_TRACE_ENABLED` |
| Super Admin | `SUPER_ADMIN_USERNAME`, `SUPER_ADMIN_PASSWORD` |
| Logging | `LOG_LEVEL`, `LOG_FORMAT` |

### 3.7 HTTPS & TLS

**Certificate:** Let's Encrypt (free, auto-renewing via Certbot).

**Setup:**
- Certbot runs as a one-shot Docker container for initial certificate issuance and periodic renewal (cron every 60 days).
- Certificates stored in `certbot-webroot` volume, mounted into Nginx.
- Nginx config has HTTPS server block (commented out during development, uncommented for production).
- HTTP → HTTPS redirect enforced in production.
- HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

**Domain (TBD):** Not yet confirmed. Recommended candidates:
- `ai3l.org` — Short, academic tone (.org), easy to remember.
- `ai3l-community.org` — Descriptive, clear purpose.
- `ai3l.community` — Modern TLD, exact project name match.

Once domain is confirmed, update: Nginx `server_name`, CORS `allow_origins`, CSP `img-src` (for MinIO subdomain or path), `.env.example`.

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

CATEGORIES ||--o{ POSTS : contains
SIGS ||--o{ POSTS : contains
SIGS ||--o{ FORMS : hosts

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
| avatar_url | VARCHAR(500) | NULL | MinIO presigned URL |
| orcid | VARCHAR(50) | NULL | |
| affiliation | VARCHAR(200) | NULL | |
| bio | TEXT | NULL | |
| is_deleted | BOOLEAN | NOT NULL, default `false` | GDPR anonymization flag |
| created_at | TIMESTAMPTZ | NOT NULL, server_default `now()` | |
| updated_at | TIMESTAMPTZ | NOT NULL, server_default `now()` | |

#### INVITE_CODES

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| code | VARCHAR(50) | NOT NULL, UNIQUE, INDEX |
| created_by | UUID | FK → users.id |
| expires_at | TIMESTAMPTZ | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### MEMBERSHIP_APPLICATIONS

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, INDEX |
| description | TEXT | NOT NULL |
| status | VARCHAR(20) | NOT NULL, default `PENDING` |
| reviewed_by | UUID | NULL, FK → users.id |
| reviewed_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### PRIVACY_CONSENTS

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, INDEX |
| ip_address | VARCHAR(45) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

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
| user_id | UUID | FK → users.id, INDEX | |
| category_id | UUID | NULL, FK → categories.id, INDEX | |
| sig_id | UUID | NULL, INDEX | Reserved for SIG association |
| title | VARCHAR(300) | NOT NULL | |
| content | TEXT | NOT NULL | HTML, sanitized via bleach |
| keywords | TEXT[] | NULL | Up to 15 keywords |
| allow_comments | BOOLEAN | NOT NULL, default `true` | |
| version | INTEGER | NOT NULL, default `1` | Optimistic locking |
| comment_count | INTEGER | NOT NULL, default `0` | Denormalized counter |
| is_deleted | BOOLEAN | NOT NULL, default `false` | Soft delete |
| search_vector | TSVECTOR | NULL, GIN INDEX | Auto-updated by DB trigger |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Trigger:** `trg_posts_search_vector_update` — BEFORE INSERT/UPDATE on `title, content`:
```sql
NEW.search_vector :=
    setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
```

#### POST_HISTORY

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| post_id | UUID | FK → posts.id, INDEX |
| version | INTEGER | NOT NULL |
| title | VARCHAR(300) | NOT NULL |
| content | TEXT | NOT NULL |
| edited_at | TIMESTAMPTZ | NOT NULL, default `now()` |

#### COMMENTS

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| post_id | UUID | FK → posts.id, INDEX | |
| user_id | UUID | FK → users.id, INDEX | |
| parent_id | UUID | NULL, FK → comments.id (self-ref) | Flat thread with quote/reply |
| content | TEXT | NOT NULL | HTML, sanitized |
| mentions | TEXT[] | NULL | Array of usernames |
| reactions | JSONB | NULL | `{"LIKE": ["uid1", ...]}` |
| is_deleted | BOOLEAN | NOT NULL, default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### POST_REPORTS *(Not yet implemented)*

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| post_id | UUID | FK → posts.id, INDEX | Reported post |
| user_id | UUID | FK → users.id | Reporter |
| reason | TEXT | NOT NULL | Free-text reason |
| status | VARCHAR(20) | NOT NULL, default `PENDING` | PENDING / REVIEWED / DISMISSED |
| reviewed_by | UUID | NULL, FK → users.id | Admin who reviewed |
| reviewed_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

#### SIGS *(Not yet implemented)*

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL, UNIQUE |
| description | TEXT | NULL |
| created_by | UUID | FK → users.id |
| is_deleted | BOOLEAN | default `false` |
| member_count | INTEGER | default `0` |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

#### SIG_MEMBERS *(Not yet implemented)*

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| sig_id | UUID | FK → sigs.id |
| user_id | UUID | FK → users.id |
| role | VARCHAR(20) | `ADMIN` / `SUB_ADMIN` / `MEMBER` |
| created_at | TIMESTAMPTZ | NOT NULL |

#### FORMS *(Not yet implemented)*

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| sig_id | UUID | FK → sigs.id | |
| created_by | UUID | FK → users.id | |
| title | VARCHAR(300) | NOT NULL | |
| description | TEXT | NULL | |
| banner_url | VARCHAR(500) | NULL | MinIO presigned URL |
| deadline | TIMESTAMPTZ | NULL | |
| max_respondents | INTEGER | NULL | |
| questions | JSONB | NOT NULL | Schema definition |
| is_schema_locked | BOOLEAN | default `false` | Locked after first response |
| is_deleted | BOOLEAN | default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### FORM_RESPONSES *(Not yet implemented)*

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| form_id | UUID | FK → forms.id |
| user_id | UUID | FK → users.id |
| answers | JSONB | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

#### NOTIFICATIONS *(Not yet implemented)*

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, INDEX | Receiver |
| trigger_user_id | UUID | FK → users.id | Who caused the notification |
| action_type | VARCHAR(20) | NOT NULL | MENTION / REPLY / SYSTEM |
| entity_id | UUID | NULL | Post or Comment ID |
| is_read | BOOLEAN | default `false` | |
| created_at | TIMESTAMPTZ | NOT NULL | |

#### AUDIT_LOGS *(Not yet implemented)*

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| action | VARCHAR(100) | NOT NULL |
| target_type | VARCHAR(50) | NULL |
| target_id | UUID | NULL |
| ip_address | VARCHAR(45) | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

---

## 5. Authentication & Authorization

### 5.1 RBAC Permission Matrix

| Action | Super Admin | Admin | Member | Guest |
|--------|:-----------:|:-----:|:------:|:-----:|
| Browse public content | Y | Y | Y | Y (45 min) |
| Edit display name | Y | Y | Y | Y |
| Edit full profile (avatar, ORCID, etc.) | Y | Y | Y | N |
| Create posts / comments / upload files | Y | Y | Y | N |
| Apply to become Member | N/A | N/A | N/A | Y |
| Review Guest → Member applications | Y | Y | N | N |
| Promote Member → Admin | Y | N | N | N |
| Create SIG / Category / assign sub-admin | Y | Y | N | N |
| Create / export built-in forms (within SIG) | Y | Y | N | N |
| Ban users / view audit logs | Y | N | N | N |

### 5.2 Authentication Flow

1. **JWT + Redis Dual Validation:** Every request validates that (a) the JWT is not expired, (b) the JWT `jti` is not blacklisted in Redis, and (c) a Redis session key exists for the user.
2. **Password Hashing:** Argon2id via `passlib`.
3. **Password Policy:** Minimum 8 characters, at least one uppercase, one lowercase, one digit.
4. **CAPTCHA:** Server-generated image captcha, 4-char alphanumeric, stored in Redis with 5-minute TTL. Deleted on successful verification (one-time use). Required for: **login, registration, guest login**.

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

### 5.5 Account Lifecycle

- **Super Admin Bootstrap:** On startup, if `SUPER_ADMIN_USERNAME` does not exist in DB, auto-creates with `SUPER_ADMIN_PASSWORD` from `.env`. Supports creating additional Super Admins via UI.
- **Invite Codes:** Multi-use, 7-day expiry, format `INV-{8HEX}`. Generated by **Member+** (Members, Admins, Super Admins).
- **Guest Login:** Requires **invite code + captcha** (`POST /auth/guest-login/{invite_code}`). Ephemeral — Guest users exist only in Redis, not in the `users` table. Max 30 concurrent guests enforced by atomic Redis counter.
- **Guest 45-Minute Enforcement:** JWT `exp` = 45 min, Redis session TTL = 45 min, WebSocket server schedules `FORCE_LOGOUT` at 45 min. HTTP 429 returned when 30-guest limit is reached.
- **Registration Captcha:** Required. Even though the system is invite-only, captcha provides defense-in-depth against automated abuse of leaked invite codes.
- **GDPR Anonymization:** `DELETE /users/me` overwrites PII with `Deleted_User_{UUID}`, sets `is_deleted=true`, invalidates session. DB entity and FKs preserved.

---

## 6. Academic Forum

### 6.1 Post Editor UI

- **Rich Text Editor:** [Tiptap](https://tiptap.dev/) (ProseMirror-based, Vue 3 native). Extensions: bold, italic, underline, strikethrough, heading (H1–H3), bullet/ordered list, blockquote, code block, horizontal rule, link, image (via `/files/upload/editor`), table.
- Attachment upload area showing uploaded files with delete button (single file max 20 MB).
- Category selector (single select).
- Keywords/tags input (Enter key to create, up to 15 per post).
- "Allow Comments" toggle.

### 6.2 Post List & Search

- Displays: title, author (clickable → profile), category badge, publish date, comment count.
- Compound search bar: keyword input, category dropdown, date range picker, AND/OR logic toggle.
- Pagination (page-based, default 20 per page).

### 6.3 Post Detail & History

- Edit History button (visible when `version > 1`): opens modal showing past 60-day version snapshots.
- **Report button:** Modal requesting reason text. Reports are queued for **Admin/Sub-Admin manual review** — no automatic hiding. Admin sees reported posts in a review dashboard and decides whether to delete or dismiss.
- Author and admins can edit/delete posts.
- Optimistic locking: update requires current `version`; 409 Conflict on mismatch.

### 6.4 Comments Section

- Flat thread display with quote/reply via `parent_id` (indented with border).
- @username autocomplete in comment input.
- Emoji reactions: LIKE, SMILE, CRY (toggle per user, stored in JSONB).
- Attachment upload support in comments.
- Max 200 comments per post.

### 6.5 Full-Text Search

- PostgreSQL `tsvector` column with GIN index on `posts.search_vector`.
- DB trigger auto-updates on INSERT/UPDATE of `title` (weight A) and `content` (weight B).
- Search API supports compound filters: keyword, category, tag array, date range, AND/OR operator.
- Response includes `total_items`, `total_pages`, `current_page`.

---

## 7. Special Interest Groups (SIGs)

*Status: Not yet implemented.*

### 7.1 SIG Directory

- Card-based list: SIG name, description, admin info, member count.
- Admin+ sees "Create SIG" button.
- Members see "Apply to create SIG" link (directs to admin contact).

### 7.2 SIG Internal Structure

- Post feed UI mirrors Forum but without category filter.
- "Forms" tab for SIG-specific surveys/registration forms.
- "Members" tab showing admins, sub-admins, and active posters.

### 7.3 SIG Deletion Cascade

When a SIG is soft-deleted (`is_deleted = true`), the application layer hides its Posts and Forms without setting `is_deleted` on child objects, preserving restoration flexibility.

### 7.4 API Endpoints (Planned)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sigs` | None | List all SIGs (paginated) |
| POST | `/sigs` | Admin+ | Create a SIG |
| GET | `/sigs/{sig_id}` | None | Get SIG details |
| POST | `/sigs/{sig_id}/sub-admin` | Admin+ | Assign sub-admin |
| GET | `/sigs/{sig_id}/posts` | None | List SIG posts |
| GET | `/sigs/{sig_id}/members` | None | List SIG members |

---

## 8. Built-in Forms System

*Status: Not yet implemented.*

### 8.1 Form Builder UI (Admin/Sub-Admin Only)

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
      "label": "Rate your experience (1–5)",
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

- Admin clicks "Export CSV" → button enters loading state.
- Backend triggers async Celery task → returns `task_id` (HTTP 202).
- Frontend polls `GET /tasks/{task_id}/status` until `COMPLETED`.
- On completion, response includes `download_url` (presigned MinIO URL) → browser auto-downloads.

### 8.6 API Endpoints (Planned)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/sigs/{sig_id}/forms` | Admin/Sub-Admin | Create form |
| GET | `/forms/{form_id}` | None | Get form schema + `is_active` |
| PUT | `/forms/{form_id}` | Admin/Sub-Admin | Update form (title/desc/deadline only if locked) |
| POST | `/forms/{form_id}/submit` | Member+ | Submit response |
| POST | `/forms/{form_id}/export` | Admin/Sub-Admin | Trigger CSV export |
| GET | `/tasks/{task_id}/status` | Any authenticated | Poll task status |

### 8.7 Quotas

- Max 20 active (non-expired) forms per SIG.

---

## 9. Notification System

*Status: WebSocket infrastructure exists; notification DB model and UI not yet implemented.*

### 9.1 Design Philosophy

**No email service.** The platform avoids all external email/Google services. Notifications are delivered via two channels only:

1. **Real-time:** WebSocket push when the user is online (connected via WS).
2. **Persistent storage:** All notifications are saved in the `notifications` DB table. When a user logs in or opens the app, unread notifications are fetched from the database and displayed via bell icon badge.

This design is self-contained — no SMTP server, no third-party push service. Users who miss real-time notifications will see them on their next visit.

### 9.2 Notification Types

| Action Type | Trigger | Entity | Message Template |
|-------------|---------|--------|-----------------|
| MENTION | User @mentioned in a comment | Comment ID | "{user} mentioned you in a comment" |
| REPLY | Someone replies to your comment | Comment ID | "{user} replied to your comment" |
| SYSTEM | Application approved/rejected, role changed, post deleted by admin | Various | "Your application was approved" / "Your post was removed" |

### 9.3 Notification UI

- **Navbar bell icon** with red badge showing unread count (fetched on app mount via `GET /notifications?unread=true&limit=0` to get count only).
- **Dropdown list** of recent 10 notifications on bell click (lazy-loaded on first click).
- **"View All"** link → full `/notifications` page with paginated list.
- Each notification shows: trigger user's avatar, message text, relative timestamp (e.g., "5 min ago").
- Click → marks as read (style dims), Vue Router navigates to entity (e.g., scroll to specific comment).

### 9.4 Real-Time Delivery Flow

1. Backend event occurs (e.g., comment created with `@alice`).
2. Service layer inserts row into `notifications` table.
3. Service checks if target user has an active WebSocket connection (via in-memory connection registry).
4. If online: push `NEW_NOTIFICATION` message via WebSocket → frontend increments badge + shows toast.
5. If offline: notification waits in DB, user sees it on next login/page load.

### 9.5 RTBF Protection

Notification records store `trigger_user_id` only (no hardcoded display names). Frontend dynamically resolves display names from the users table. If the trigger user is deleted, the notification renders as "Deleted User" automatically.

### 9.6 API Endpoints (Planned)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | Required | List user's notifications (paginated, `?unread=true` filter) |
| PUT | `/notifications/{id}/read` | Required | Mark single notification as read |
| PUT | `/notifications/read-all` | Required | Mark all notifications as read |

---

## 10. File Upload & Storage

### 10.1 Storage Architecture

MinIO (S3-compatible), single bucket `ai3l-uploads`, private access. Files served via presigned URLs.

**Key namespaces:**
- `avatars/{user_id}/{uuid}.{ext}` — Profile avatars
- `editor/{user_id}/{uuid}.{ext}` — Rich text editor attachments

### 10.2 Avatar Upload

- Endpoint: `PUT /users/me/avatar`
- Allowed: PNG, JPEG only.
- Max size: 2 MB.
- Returns 7-day presigned URL stored in `users.avatar_url`.

### 10.3 Editor File Upload

- Endpoint: `POST /files/upload/editor`
- Allowed: PNG, JPEG, PDF, DOCX.
- Max size: 20 MB.
- **Magic number validation:** File bytes compared against expected signatures (not just Content-Type header).
- Returns presigned URL (7-day expiry).

### 10.4 File Security

| Defense | Implementation |
|---------|---------------|
| Magic number validation | Byte signature check for PNG (`\x89PNG`), JPEG (`\xFF\xD8\xFF`), PDF (`%PDF`), DOCX (`PK\x03\x04`) |
| HTML sanitization | `bleach` on backend (server-side), DOMPurify on frontend (client-side) |
| PDF sanitization | Strip JavaScript and macros from uploaded PDFs *(planned)* |
| VirusTotal integration | Celery task computes local SHA-256 hash, queries VT API with hash only (never uploads raw file) *(planned)* |
| Size limits | 2 MB (avatars), 20 MB (editor files), 25 MB (Nginx `client_max_body_size`) |

### 10.5 Per-User Storage Quota

Each user account has a total storage limit of 1 GB (all avatars + attachments). Exceeding requires admin approval to expand. *(Not yet enforced.)*

---

## 11. Full API Specification

**Base URL:** `/api/v1`
**Auth Header:** `Authorization: Bearer <token>`
**Idempotency Header:** `Idempotency-Key: <uuid>` (POST/PUT write operations, per IETF draft-ietf-httpapi-idempotency-key-header)

### 11.1 Health

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/health` | None | `{"status": "healthy", "dependencies": [{name, status, latency_ms}]}` |

### 11.2 Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/captcha` | None | Generate captcha image → `{captcha_id, image_base64}` |
| POST | `/auth/login` | None | Login → `{token, role, expires_in}` |
| POST | `/auth/guest-login/{invite_code}` | None | Guest login with invite code + captcha → Guest JWT (45 min) |
| POST | `/auth/logout` | Required | Invalidate session, blacklist JWT |
| POST | `/auth/register` | None | Create account (requires invite code + captcha) → `{token, role, expires_in}` |
| POST | `/auth/heartbeat` | Required | Refresh Redis session TTL → full role TTL reset (client calls every 30s) |
| POST | `/auth/invite-code` | Member+ | Generate multi-use invite code (7-day expiry) |
| GET | `/auth/invite-code/{code}` | None | Validate invite code |

### 11.3 Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Required | Get own profile |
| PUT | `/users/me` | Required | Update profile fields |
| PUT | `/users/me/avatar` | Required | Upload avatar (PNG/JPEG, 2 MB max) |
| DELETE | `/users/me` | Required | GDPR anonymization |
| GET | `/users` | Admin+ | List all users (paginated) |
| POST | `/users/admin/create-account` | Admin+ | Create account (only SA can create Admin) |
| PUT | `/users/{user_id}/role` | Super Admin | Change role, revoke target sessions |

### 11.4 Applications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/users/apply-member` | Guest | Submit membership application |
| GET | `/admin/applications` | Admin+ | List applications (filterable by status) |
| PUT | `/admin/applications/{app_id}/review` | Admin+ | Approve / Reject (auto-promotes on approve) |

### 11.5 Categories

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/categories` | None | List all categories |
| POST | `/categories` | Admin+ | Create category (409 if name exists) |

### 11.6 Posts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/posts` | Member+ | Create post (bleach sanitized, 50/day limit) |
| GET | `/posts` | None | List posts (paginated, optional category filter) |
| POST | `/posts/search` | None | Full-text search with compound filters |
| GET | `/posts/{post_id}` | None | Get single post |
| PUT | `/posts/{post_id}` | Member+ | Update post (optimistic locking, saves history) |
| DELETE | `/posts/{post_id}` | Member+ | Soft delete (admins can delete any, members own only) |
| GET | `/posts/{post_id}/history` | Required | Get edit history snapshots |

### 11.7 Comments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/posts/{post_id}/comments` | None | List comments (paginated) |
| POST | `/posts/{post_id}/comments` | Member+ | Create comment (200/post limit, parent_id for reply) |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | Member+ | Soft delete comment (author or admin) |
| POST | `/posts/{post_id}/comments/{comment_id}/reactions` | Member+ | Toggle reaction (LIKE/SMILE/CRY) |

### 11.8 Files

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/files/upload/editor` | Member+ | Upload PNG/JPEG/PDF/DOCX (20 MB, magic validated) |
| GET | `/files/presigned/{key}` | Member+ | Get 1-hour presigned download URL |

### 11.9 WebSocket

| Protocol | Path | Auth |
|----------|------|------|
| WS | `/ws?token={jwt}` | JWT in query param |

**Server-initiated messages:**
- `PING` (every 30s) — client must reply `PONG` within 90s
- `FORCE_LOGOUT` — forces client disconnect
- `NEW_NOTIFICATION` *(planned)* — real-time notification push

### 11.10 Planned Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/posts/{post_id}/report` | Member+ | Report post with reason (manual Admin review) |
| GET | `/admin/reports` | Admin+ | List pending post reports |
| PUT | `/admin/reports/{report_id}/review` | Admin+ | Review report (REVIEWED / DISMISSED) |
| GET/POST | `/sigs` | None / Admin+ | List / Create SIG |
| GET | `/sigs/{sig_id}` | None | SIG details |
| POST | `/sigs/{sig_id}/sub-admin` | Admin+ | Assign sub-admin |
| POST | `/sigs/{sig_id}/forms` | Admin/Sub-Admin | Create form |
| GET | `/forms/{form_id}` | None | Get form schema |
| POST | `/forms/{form_id}/submit` | Member+ | Submit form response |
| POST | `/forms/{form_id}/export` | Admin/Sub-Admin | Trigger CSV export |
| GET | `/tasks/{task_id}/status` | Required | Poll task status |
| GET | `/notifications` | Required | List notifications |
| PUT | `/notifications/{id}/read` | Required | Mark as read |
| GET | `/admin/audit-logs` | Super Admin | View audit logs |
| POST | `/admin/users/{user_id}/ban` | Super Admin | Ban/unban user |

---

## 12. Frontend Pages & Components

### 12.1 Routes

| Path | Component | Auth | Description |
|------|-----------|------|-------------|
| `/` | HomeView | None | Landing page, welcome message or login prompts |
| `/login` | LoginView | Guest-only | Username + password + captcha |
| `/register` | RegisterView | Guest-only | Account creation with password policy hints |
| `/guest` | GuestLoginView | Guest-only | Guest login with display name + captcha |
| `/profile` | ProfileView | Required | Edit profile, upload avatar |
| `/forum` | ForumView | None | Post list, search, filter, pagination |
| `/forum/create` | PostCreateView | Required | Create new post |
| `/forum/:id` | PostDetailView | None | View/edit post, comments, reactions, history |
| `/admin/users` | UsersView | Admin+ | User management, role changes, create accounts |
| `/admin/applications` | ApplicationsView | Admin+ | Review membership applications |

### 12.2 Planned Routes

| Path | Component | Auth | Description |
|------|-----------|------|-------------|
| `/sigs` | SigsDirectoryView | None | SIG listing |
| `/sigs/:id` | SigDetailView | None | SIG posts/forms/members tabs |
| `/forms/:id` | FormView | None | Form submission |
| `/forms/:id/builder` | FormBuilderView | Admin+ | Form question builder |
| `/notifications` | NotificationsView | Required | Full notification list |

### 12.3 Shared Components

| Component | Description |
|-----------|-------------|
| AppNavbar | Sticky top nav: logo, Forum link, admin links, user dropdown with role badge |
| ToastNotification | Fixed toast stack, listens to `app:toast` CustomEvent, 5s auto-dismiss |

### 12.4 Planned Components

| Component | Description |
|-----------|-------------|
| NotificationBell | Navbar bell icon with unread badge + dropdown |
| RichTextEditor | Tiptap WYSIWYG editor with toolbar (bold, italic, heading, list, image upload, table) + DOMPurify output sanitization |

### 12.5 State Management

**Pinia Auth Store:**
- State: `token`, `role`, `expiresAt` (localStorage persisted), `user` (UserProfile object)
- Computed: `isAuthenticated`, `isAdmin`, `isSuperAdmin`, `isGuest`
- Actions: `login()`, `guestLogin()`, `register()`, `logout()`, `fetchProfile()`
- 30-second heartbeat interval (auto-starts if authenticated on page load)

**Axios API Client:**
- Base URL: `/api/v1`, 15s timeout
- Request interceptor: injects `Authorization: Bearer {token}`
- Response interceptor: 401 → clear session + redirect to login; 429 → dispatch toast with Retry-After

---

## 13. Security & Threat Model

### 13.1 XSS Prevention

- **Backend:** `bleach` HTML sanitization on all post/comment content before storage. Allowed tags: `p, br, strong, em, u, s, h1-h6, ul, ol, li, blockquote, pre, code, a, img, table, thead, tbody, tr, th, td, span, div, sub, sup, hr`.
- **Frontend:** DOMPurify before rendering any user-generated HTML content. Integrated alongside Tiptap editor (sanitize on display, not on input).

### 13.2 Content Security Policy

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: minio.domain.com;
font-src 'self';
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

### 13.3 CSRF Immunity

JWT is transmitted via `Authorization` header (not cookies), providing inherent CSRF immunity.

### 13.4 CORS Policy

Strict `allow_origins` from environment variable. Wildcard (`*`) is prohibited. `allow_credentials=True` enabled.

### 13.5 File Upload Defense

| Layer | Check |
|-------|-------|
| Extension whitelist | .png, .jpg, .jpeg, .pdf, .docx |
| Magic number | Byte signature validation |
| Size limit | 2 MB (avatar), 20 MB (editor), 25 MB (Nginx) |
| Sanitization | bleach (HTML), PDF script stripping *(planned)* |
| Antivirus | VirusTotal hash-only query via Celery *(planned)* |

### 13.6 Password Security

- Argon2id hashing (via passlib)
- Policy: 8+ chars, uppercase, lowercase, digit
- No plaintext storage anywhere

### 13.7 Session Security

- JWT + Redis dual validation on every request
- JWT blacklisting on logout
- Session invalidation on role change
- No session sharing across roles

---

## 14. Resource Quotas & Rate Limiting

### 14.1 Nginx Rate Limiting

| Zone | Rate | Burst | Applied To |
|------|------|-------|------------|
| `global` | 1 req/s (60 req/min) | 10 | All `/api/` routes |
| `write` | 5 req/min | 2 | `/api/v1/(posts\|comments\|forms)` |

On 429: Nginx returns HTTP 429 Too Many Requests. Frontend interceptor shows toast: "You are performing actions too frequently. Please try again in N seconds."

### 14.2 Application-Level Quotas

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Posts per user per day | 50 | Redis counter `post_limit:{uid}:{date}` |
| Comments per post | 200 | Service-layer check on `comment_count` |
| Concurrent guests | 30 | Redis atomic counter `online_count:guest` |
| Keywords per post | 15 | Schema validation |
| Storage per user | 1 GB | *(Planned)* |
| Active forms per SIG | 20 | *(Planned)* |
| Text input max length | 500 chars | Schema validation (except Rich Text body) |

---

## 15. Engineering Guidelines

### 15.1 Transaction Consistency

All cross-table writes (e.g., create comment + increment post counter) must be wrapped in `async with conn.transaction():` for ACID atomicity.

### 15.2 Idempotency

POST/PUT operations accept `Idempotency-Key` header (UUID, no `X-` prefix per RFC 6648). Backend stores in Redis with 300s TTL. Duplicate key within window returns cached response (or 409 if still processing).

### 15.3 Database Architecture

- **SQLAlchemy** is used ONLY for model definitions and Alembic migration generation.
- **All runtime queries** use raw `asyncpg` via connection pool (`pool.acquire()` + `conn.fetchrow/fetch/execute`).
- The `server_default` parameter (not `default`) must be used for columns that need DB-level defaults (asyncpg bypasses Python-side defaults).

### 15.4 API Versioning

All routes prefixed with `/api/v1`. Semantic versioning (`vX.Y.Z`) for frontend and backend releases.

### 15.5 Database Migration Policy

- **Tool:** Alembic only. Manual `ALTER TABLE` on production is prohibited.
- **Backward compatibility:** All schema changes must be zero-downtime compatible.
- **Column rename/delete:** Three-phase deployment (Expand → Migrate Data → Contract).

### 15.6 WebSocket Reliability

- **Server-initiated ping:** Every 30s. Client auto-responds with pong. 90s timeout → disconnect.
- **Heartbeat TTL:** Full role TTL reset on each heartbeat (lighter on Redis than sliding 90s window). E.g., Guest resets to 45 min, Member to 3 hours.
- **Client reconnection:** Exponential backoff (initial 1s, max 30s).
- **Page Visibility API:** Pause polling on `document.hidden`, graceful reconnect on visible.

---

## 16. DevOps & Observability

### 16.1 CI/CD

Three GitHub Actions workflows:
- `backend-ci.yml` — lint + test on push
- `frontend-ci.yml` — lint + build on push
- `docker-build.yml` — Docker image build verification

Merge requests blocked on test failure.

### 16.2 Testing Strategy

| Type | Tool | Target |
|------|------|--------|
| Backend unit/integration | pytest + pytest-asyncio | 80% service layer coverage |
| Frontend E2E | Playwright | Core flows: login, post creation |
| Linting | flake8 + black (Python), ESLint + Prettier (Vue) | All source files |

### 16.3 Structured Logging

Loguru JSON format to stderr. Docker json-file log driver captures output.

**Required fields per log entry:**
- `timestamp`
- `level` (INFO, WARNING, ERROR)
- `trace_id` (from Nginx `X-Request-ID`)
- `user_id` (if authenticated)
- `message`

**Log level guidelines:**
- **INFO:** Core business events (login, post creation)
- **WARNING:** Tolerable anomalies (rate limit hit, wrong password, 404)
- **ERROR:** System failures (DB connection lost, 500 errors)

### 16.4 SLA & SLO

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
| SYS_409 | 409 | Version conflict / Idempotency key conflict |
| SYS_429 | 429 | Rate limit exceeded |
| FILE_001 | 400 | Invalid magic number / malware detected |
| FORM_001 | 400 | Form deadline passed |

---

## 18. Implementation Status

### Completed

| Phase | Scope | Commit |
|-------|-------|--------|
| Phase 0 | Infrastructure: Docker Compose (6 services), Nginx, CI/CD, CODEOWNERS | `62e58d4` |
| Phase 1A | DB models (User, InviteCode), JWT+Redis auth, captcha, RBAC, guest limits | `ac7b502` |
| Phase 1B | Admin APIs, membership applications, avatar upload, idempotency middleware, WebSocket, frontend auth UI (10 pages) | `1308c28` |
| Phase 2 | Forum: Categories, Posts (CRUD + optimistic locking + FTS), PostHistory, Comments (threaded + reactions), file upload with magic validation, bleach sanitization | `d65d463` |

### Remaining

| Phase | Scope | Priority |
|-------|-------|----------|
| Phase 3 | SIGs: model, CRUD, sub-admin, directory UI, internal post feed | High |
| Phase 4 | Forms: JSONB schema builder, submission, schema freeze, Celery CSV export | High |
| Phase 5 | Notifications: DB model, MENTION/REPLY/SYSTEM triggers, WebSocket push, bell icon UI | Medium |
| Phase 6 | Audit logs, user ban, structured error codes, Sentry init, privacy consent flow, CLI rescue tool | Medium |
| Phase 7 | 80% test coverage, HTTPS, database backups, Datadog, production hardening | Pre-deploy |

### Known Gaps (Spec Decisions Made, Implementation Pending)

Items below have been **decided** in the spec but are not yet implemented in code. They will be addressed in their respective phases.

| Item | Decision | Target Phase |
|------|----------|-------------|
| Guest login requires invite code | `POST /auth/guest-login/{invite_code}` | Code fix (Phase 3) |
| Guest limit returns 429 | Change from 503 to 429 | Code fix (Phase 3) |
| Member can generate invite codes | Expand from Admin+ to Member+ | Code fix (Phase 3) |
| Idempotency header `Idempotency-Key` | Rename from `X-Idempotency-Key` | Code fix (Phase 3) |
| Registration captcha | Add captcha verification to `POST /auth/register` | Code fix (Phase 3) |
| Tiptap rich text editor | Replace textarea with Tiptap WYSIWYG | Phase 3 frontend |
| DOMPurify frontend | Sanitize HTML on display | Phase 3 frontend |
| Comment delete endpoint | `DELETE /posts/{post_id}/comments/{id}` | Phase 3 |
| Post report + admin review | Manual Admin/Sub-Admin review, no auto-hide | Phase 3 |
| Privacy consent modal UI | Model exists, need frontend flow | Phase 6 |
| WS 45-min guest force logout | Schedule FORCE_LOGOUT event | Phase 3 |
| WS exponential backoff | Frontend reconnect (1s→30s) | Phase 3 |
| Page Visibility API | Pause/resume WS on tab switch | Phase 3 |
| Sentry initialization | Call `sentry_sdk.init()` in FastAPI lifespan | Phase 7 |
| Avatar URL refresh mechanism | Refresh expired 7-day presigned URLs | Phase 6 |
| CSP img-src MinIO domain | Add MinIO domain after domain confirmed | Phase 7 |
