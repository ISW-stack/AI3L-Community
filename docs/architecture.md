# AI3L Community — System Architecture

A comprehensive architecture reference for the AI3L Community platform: an academic exchange community for *AI in Language Learning and Literacy* (research, posts, SIGs, events, forms, Q&A, albums, direct messaging).

> Last refreshed: 2026-05-08. Diagrams use [Mermaid](https://mermaid.js.org/) — they render natively on GitHub, VS Code, and most modern Markdown viewers.

---

## Table of Contents

1. [High-level system context (C4 — Level 1)](#1-high-level-system-context-c4--level-1)
2. [Container view (C4 — Level 2)](#2-container-view-c4--level-2)
3. [Tier & network topology](#3-tier--network-topology)
4. [Backend layered architecture](#4-backend-layered-architecture)
5. [Backend module map](#5-backend-module-map)
6. [Frontend architecture](#6-frontend-architecture)
7. [Database / persistence model](#7-database--persistence-model)
8. [Redis topology](#8-redis-topology)
9. [Object storage layout (MinIO / R2)](#9-object-storage-layout-minio--r2)
10. [Async / background work (Celery + Beat)](#10-async--background-work-celery--beat)
11. [Real-time pipeline (WebSocket + event bus)](#11-real-time-pipeline-websocket--event-bus)
12. [Request lifecycles (sequence diagrams)](#12-request-lifecycles-sequence-diagrams)
13. [Security architecture](#13-security-architecture)
14. [Deployment view](#14-deployment-view)
15. [Cross-cutting concerns](#15-cross-cutting-concerns)

---

## 1. High-level system context (C4 — Level 1)

The platform is a single web application reachable through a Cloudflare-fronted edge. Users (Guest, Member, Admin, Super-Admin) interact via browsers; the platform consumes a small set of third-party services for storage, malware scanning, and observability.

```mermaid
flowchart LR
    subgraph Users
        U1[Guest<br/>invite-code only]
        U2[Member]
        U3[Admin]
        U4[Super-Admin]
    end

    subgraph CF[Cloudflare Edge]
        CFD[Cloudflare CDN +<br/>Tunnel + WAF]
    end

    AI3L[(AI3L Community<br/>web platform)]

    subgraph ThirdParty[Third-party services]
        VT[VirusTotal API<br/>file scanning]
        SEN[Sentry<br/>error tracking]
        DD[Datadog APM<br/>tracing — optional]
        R2[Cloudflare R2<br/>object storage — prod]
    end

    U1 -->|HTTPS / WSS| CFD
    U2 -->|HTTPS / WSS| CFD
    U3 -->|HTTPS / WSS| CFD
    U4 -->|HTTPS / WSS| CFD
    CFD -->|cloudflared<br/>outbound tunnel| AI3L

    AI3L -->|file scan| VT
    AI3L -->|crashes / traces| SEN
    AI3L -->|spans| DD
    AI3L -->|S3 API| R2
```

---

## 2. Container view (C4 — Level 2)

Inside the platform boundary, containers are split across two logical Docker networks (`frontend-net` and `backend-net`) plus an edge tunnel.

```mermaid
flowchart TB
    classDef edge fill:#fde68a,stroke:#b45309,color:#111
    classDef fe fill:#bae6fd,stroke:#0369a1,color:#111
    classDef api fill:#bbf7d0,stroke:#15803d,color:#111
    classDef worker fill:#fbcfe8,stroke:#9d174d,color:#111
    classDef data fill:#e9d5ff,stroke:#6b21a8,color:#111

    Browser([Browser SPA])

    subgraph Edge[Edge — frontend-net]
        CFTun[cloudflared<br/>Cloudflare Tunnel]:::edge
        NGX[nginx 1.27<br/>TLS / rate-limit / static]:::edge
        VITE[Vite dev server<br/>build-frontend volume<br/>dev only]:::fe
    end

    subgraph App[Application — frontend-net + backend-net]
        FAPI[FastAPI<br/>uvicorn / gunicorn<br/>2-4 workers]:::api
    end

    subgraph Workers[Workers — backend-net]
        CEL[Celery worker<br/>2 concurrency]:::worker
        BEAT[Celery Beat<br/>scheduler]:::worker
        MIG[Alembic migrate<br/>one-shot]:::worker
    end

    subgraph DataPlane[Data plane — backend-net]
        PG[(PostgreSQL 15<br/>asyncpg pool 10-30)]:::data
        RED[(Redis 7<br/>allkeys-lru, AOF)]:::data
        OBJ[(MinIO dev /<br/>Cloudflare R2 prod)]:::data
    end

    Browser -->|HTTPS / WSS| CFTun --> NGX
    NGX -->|/| VITE
    NGX -->|/api/* + /ws| FAPI
    NGX -. assets .-> NGX

    FAPI -->|asyncpg SQL| PG
    FAPI -->|asyncio-redis| RED
    FAPI -->|S3 SDK + presign| OBJ
    FAPI -->|enqueue| RED

    CEL -->|broker / backend| RED
    CEL -->|SQL| PG
    CEL -->|S3| OBJ
    BEAT -->|enqueue| RED
    MIG -->|alembic upgrade head| PG

    FAPI <-.pub/sub.-> RED
    CEL <-.pub/sub.-> RED
```

---

## 3. Tier & network topology

`docker-compose.prod.yml` enforces network tier isolation: nginx and the API live on `frontend-net`, while databases, cache, object storage, and workers live on `backend-net`. Only the API container bridges both networks.

```mermaid
flowchart LR
    subgraph internet[Public Internet]
        user[User]
    end

    subgraph cf[Cloudflare Edge]
        cftun[cloudflared tunnel]
    end

    subgraph fenet[frontend-net]
        nginx[nginx]
        fastapi[FastAPI]
    end

    subgraph benet[backend-net]
        fastapi2[FastAPI - bridge]
        pg[(Postgres)]
        redis[(Redis)]
        minio[(MinIO / R2)]
        celery[Celery + Beat]
        migrate[migrate]
    end

    user --> cftun --> nginx --> fastapi
    fastapi -.same container.- fastapi2
    fastapi2 --> pg
    fastapi2 --> redis
    fastapi2 --> minio
    celery --> redis
    celery --> pg
    celery --> minio
    migrate --> pg
```

**Key invariants**

- nginx never talks to the database or Redis directly — only to FastAPI.
- The database is **never** exposed beyond `backend-net`.
- Cloudflared makes only outbound connections; no public ports are opened on the host in prod.
- nginx restores the real client IP from `CF-Connecting-IP` (Cloudflare-trusted ranges only).

---

## 4. Backend layered architecture

The FastAPI codebase follows a strict 4-layer pattern with no cross-layer imports:

```
HTTP request
   ↓ Endpoint  (app/api/v1/endpoints/*.py)        — routing, schema validation, deps
   ↓ Service   (app/services/*.py)                — business rules, transactions, events
   ↓ Repository (app/repositories/*.py)           — raw SQL + asyncpg
   ↓ Database  (PostgreSQL 15)
```

```mermaid
flowchart TB
    classDef http fill:#fef3c7,stroke:#92400e
    classDef ep fill:#bbf7d0,stroke:#15803d
    classDef svc fill:#bae6fd,stroke:#075985
    classDef repo fill:#fbcfe8,stroke:#9d174d
    classDef infra fill:#e9d5ff,stroke:#6b21a8

    HTTP[HTTP / WS request]:::http

    subgraph MW[Middleware stack]
        direction TB
        UPL[limit_upload_concurrency]:::ep
        BODY[limit_request_body_size]:::ep
        IPB[check_ip_ban]:::ep
        CORS[CORS]:::ep
        CSRF[CSRF double-submit]:::ep
        IDM[Idempotency-Key cache]:::ep
    end

    subgraph DEPS[FastAPI dependencies]
        AUTH[get_current_user<br/>JWT + Redis session]:::ep
        ROLE[require_sig_admin<br/>role guards]:::ep
    end

    subgraph LAYERS[Layered code]
        direction TB
        EP[Endpoints<br/>27 routers]:::ep
        SVC[Services<br/>34 modules]:::svc
        CONV[Converters<br/>row → DTO]:::svc
        REPO[Repositories<br/>36 modules — raw SQL]:::repo
    end

    subgraph CORE[Core infrastructure]
        DB[(PostgreSQL pool)]:::infra
        RED[(Redis)]:::infra
        S3[(S3 / R2)]:::infra
        BUS[event_bus.py]:::infra
        WS[WebSocket pub/sub]:::infra
    end

    HTTP --> MW --> DEPS --> EP
    EP --> SVC
    SVC --> CONV
    SVC --> REPO
    SVC --> BUS
    REPO --> DB
    SVC --> RED
    SVC --> S3
    BUS --> WS
    WS --> RED
```

**Layering rules enforced by convention**

| Layer | May call | Must NOT call |
|---|---|---|
| Endpoint | Service, schemas, deps | Repository, raw SQL, Redis |
| Service | Repository, core (Redis/S3/event_bus), other services | FastAPI primitives, request objects |
| Repository | `asyncpg.Pool`, parameterized SQL | Services, business rules, HTTP types |
| Converter | Pure functions on rows / records | I/O, async DB |

---

## 5. Backend module map

### 5.1 API endpoints (mounted under `/api/v1`)

| Router | Prefix | Domain |
|---|---|---|
| `auth.py` | `/auth` | Login, register, guest tokens, CSRF, WS ticket |
| `users.py` | `/users` | Profiles, avatar, search, soft-delete |
| `posts.py` | `/posts` | CRUD, FTS, history, pin, reactions |
| `comments.py` | `/posts/{id}/comments` | Threaded comments, mentions, reactions |
| `sigs.py` | `/sigs` | SIG CRUD, members, roles |
| `forms.py` | `/forms`, `/sigs/{id}/forms` | Form builder, responses, exports |
| `albums.py` | `/albums` | Albums, photos, lightbox |
| `events.py` | `/events` | Calendar events, RSVP |
| `dm.py` | `/dm` | 1:1 messaging, recall, edit, admin moderation |
| `qa.py` | `/qa` | Questions, answers, votes, best answer |
| `social.py` | `/social` | Friends, follows, blocks |
| `notifications.py` | `/notifications` | List, read, deduplication |
| `recommendations.py` | `/recommendations` | Friend suggestions |
| `categories.py` | `/categories` | Tags / categories |
| `citations.py` | `/citations` | Cross-post academic refs |
| `co_authors.py` | `/co-authors` | Co-author invites |
| `applications.py` | `/applications` | SIG join requests |
| `reports.py` | `/posts/{id}/reports` | Content moderation |
| `files.py` | `/files` | Upload, scan-aware download |
| `tasks.py` | `/tasks` | Async task status |
| `preferences.py` | `/users/me/preferences` | Per-user toggles, language |
| `public.py` | `/public` | Anonymous-readable content |
| `about.py` | `/about` | Member-only contributors, org chart |
| `admin.py` + `export.py` | `/admin` | Dashboard, invites, IP bans, exports |
| `health.py` | `/health`, `/health/live` | Liveness & readiness |
| `ws.py` | `/ws` | WebSocket (ticket-authenticated) |

### 5.2 Services, repositories & converters

```mermaid
flowchart LR
    subgraph SVC[services/]
        S_auth[auth]
        S_user[user]
        S_post[post]
        S_comment[comment]
        S_sig[sig]
        S_form[form]
        S_dm[dm]
        S_album[album]
        S_event[event]
        S_qa[qa]
        S_social[social]
        S_notif[notification]
        S_recommend[recommendation]
        S_audit[audit]
        S_report[report]
        S_app[application]
        S_invite[invite_code]
        S_ipban[ip_ban]
        S_dash[dashboard]
        S_settings[site_settings]
        S_cap[captcha + captcha_math]
        S_more[+ contributor / citation /<br/>co_author / category /<br/>profile_view / org_chart /<br/>privacy_consent /<br/>member_classification /<br/>preferences]
    end

    subgraph REPO[repositories/]
        R_user[user_repo]
        R_post[post_repo]
        R_comment[comment_repo]
        R_sig[sig_repo]
        R_form[form_repo]
        R_dm[dm_repo]
        R_album[album_repo]
        R_event[event_repo]
        R_notif[notification_repo]
        R_audit[audit_repo]
        R_more[+ 27 more repos]
    end

    subgraph CONV[converters/]
        C_user[user_converter]
        C_post[post_converter]
        C_dm[dm_converter]
        C_more[+ 10 more]
    end

    SVC --> REPO
    SVC --> CONV
    CONV -. avatar URL .-> CORE_S3[(S3 presign)]
```

### 5.3 Core infrastructure (`app/core/`)

| File | Responsibility |
|---|---|
| `config.py` | Pydantic settings, env validation, derived URLs |
| `database.py` | asyncpg pool (min=10, max=30), `get_pool_stats()` |
| `redis.py` | Redis asyncio client, retry, keepalive |
| `storage.py` / `async_storage.py` | S3 client, presign with `MINIO_PUBLIC_URL` rewrite |
| `security.py` | JWT (HS256), Argon2, password policy |
| `csrf.py` | Double-submit cookie middleware |
| `rate_limit.py` | Redis Lua script per zone |
| `event_bus.py` | In-process pub/sub, retry, Redis failure log |
| `errors.py` | `ErrorCode` enum, `AppError` exception |
| `file_validation.py` | Magic numbers, OOXML/DOCX validation, sanitisation, VT trigger |
| `zip_validation.py` | Zip-slip & decompression-bomb guards |
| `blacklist.py` | User-block cache (warmed at startup) |
| `logging.py` / `logging_utils.py` | Loguru JSON, PII masking |
| `constants.py` | Pagination, rate-limit, field-length, cache TTLs |

### 5.4 Middleware order (matters)

```mermaid
flowchart LR
    A[Request] --> B[limit_upload_concurrency<br/>semaphore=3] --> C[limit_request_body_size<br/>10MB / 50MB album / 10MB DM]
    C --> D[check_ip_ban<br/>Redis lookup] --> E[CORSMiddleware] --> F[CSRFMiddleware<br/>double-submit] --> G[IdempotencyMiddleware<br/>5-min Redis cache]
    G --> H[Router]
```

---

## 6. Frontend architecture

Single-page app: Vue 3 + TypeScript + Vite + Tailwind v4 + Pinia + vue-i18n.

```mermaid
flowchart TB
    classDef shell fill:#fde68a,stroke:#b45309
    classDef view fill:#bae6fd,stroke:#0369a1
    classDef store fill:#bbf7d0,stroke:#15803d
    classDef api fill:#fbcfe8,stroke:#9d174d
    classDef comp fill:#e9d5ff,stroke:#6b21a8

    MAIN[main.ts<br/>Pinia + i18n + Router]:::shell --> APP[App.vue<br/>Navbar + RouterView + Footer<br/>Toast + Consent modal]:::shell

    APP --> ROUTER[Vue Router<br/>~45 routes<br/>guards: requiresAuth /<br/>requiresMember /<br/>requiresAdmin /<br/>requiresSuperAdmin /<br/>fullWidth]:::shell

    ROUTER --> VIEWS[Views — 54 files<br/>Home / Login / Forum /<br/>Sigs / Forms / Albums /<br/>Events / Q&A / DM /<br/>Admin / Profile / About]:::view

    VIEWS --> COMPOS[Composables — 19<br/>api / useWebSocket /<br/>usePagination /<br/>useFetchPaginated /<br/>usePostDetail /<br/>useFormBuilder /<br/>useDraft / useLocale]:::comp

    VIEWS --> STORES[Pinia stores]:::store
    STORES --> S_AUTH[auth<br/>role + heartbeat 30s]:::store
    STORES --> S_DM[dm<br/>conversations / unread]:::store
    STORES --> S_NOTIF[notifications]:::store
    STORES --> S_TOAST[toast]:::store

    COMPOS --> API[API modules — 22<br/>auth / users / posts /<br/>comments / sigs / forms /<br/>albums / events / qa /<br/>dm / notifications /<br/>admin / social / about]:::api

    API -->|axios + CSRF + cookies| BE[/api/v1 backend/]

    COMPOS --> WS[useWebSocket<br/>ticket → /ws<br/>exp. backoff 1-30s]:::comp
    WS -->|NEW_DM / DM_EDITED /<br/>DM_RECALLED / DM_READ /<br/>NOTIFICATION / FORCE_LOGOUT /<br/>ROLE_CHANGED| STORES

    VIEWS --> COMPONENTS[Components — 59<br/>base/ shared/ post/<br/>forms/ albums/ profile/<br/>qa/ social/ dm/ guide/<br/>+ TiptapEditor /<br/>NotificationBell /<br/>LanguageSwitcher]:::comp
```

### Layout & route guards

- `route.meta.fullWidth` toggles `App.vue` `<main>` between `max-w-7xl` and full-bleed.
- `requiresAuth` → must be logged in (any role).
- `requiresMember` → blocks `isGuest`.
- `requiresAdmin` → ADMIN or SUPER_ADMIN.
- `requiresSuperAdmin` → SUPER_ADMIN only.

### Key shared abstractions

| File | Purpose |
|---|---|
| `composables/api.ts` | axios instance: `withCredentials`, CSRF header injector, 401/AUTH-code handler |
| `composables/useWebSocket.ts` | Connection lifecycle, exponential backoff, visibility pause/resume, PONG rate-limit |
| `composables/usePagination.ts` | `{page, total, totalPages, setPage, resetPage, updateFromResponse}` |
| `composables/useFetchPaginated.ts` | Paginated GET with `fetchId` stale-response guard |
| `composables/usePostDetail.ts` | Extracts PostDetailView business logic |
| `utils/error.ts` | `getErrorMessage(e, fallback)` — single API error extractor |
| `utils/sanitize.ts` | DOMPurify wrapper for user HTML |
| `utils/apiValidation.ts` | `assertShape()` runtime shape check (dev warnings) |
| `locales/` | 17 languages, lazy-loaded except English |

---

## 7. Database / persistence model

PostgreSQL 15, all migrations in `backend/alembic/versions/`. The model breaks into clear bounded contexts:

```mermaid
erDiagram
    USERS ||--o{ POSTS : authors
    USERS ||--o{ COMMENTS : writes
    USERS ||--o{ SIG_MEMBERS : joins
    USERS ||--o{ FRIENDSHIPS : "requester|recipient"
    USERS ||--o{ FOLLOWS : follows
    USERS ||--o{ BLOCKS : blocks
    USERS ||--o{ FORM_RESPONSES : submits
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ AUDIT_LOGS : "subject of"
    USERS ||--|| USER_PREFERENCES : has

    POSTS ||--o{ COMMENTS : has
    POSTS ||--o{ POST_HISTORY : versioned
    POSTS ||--o{ POST_CO_AUTHORS : "co-authored by"
    POSTS ||--o{ POST_CITATIONS : cites
    POSTS ||--o{ POST_REPORTS : flagged
    POSTS }o--|| CATEGORIES : "categorised by"
    POSTS }o--|| SIGS : "scoped to"

    SIGS ||--o{ SIG_MEMBERS : has
    SIGS ||--o{ MEMBERSHIP_APPLICATIONS : receives
    SIGS ||--o{ FORMS : owns
    SIGS ||--o{ POSTS : contains

    FORMS ||--o{ FORM_RESPONSES : collects

    CONVERSATIONS ||--o{ DM_MESSAGES : contains
    USERS ||--o{ CONVERSATIONS : "participant_a|b"

    ALBUMS ||--o{ ALBUM_PHOTOS : contains
    ALBUMS ||--o{ ALBUM_MEMBERS : has
    ALBUMS ||--o{ ALBUM_COMMENTS : has

    FILES ||--|| FILE_SCANS : scanned

    USERS {
        uuid id PK
        string username UK
        string password_hash
        enum role
        string display_name
        string avatar_url
        bool is_deleted
        bool is_banned
        string preferred_language
        bigint storage_used_bytes
    }
    POSTS {
        uuid id PK
        uuid user_id FK
        uuid sig_id FK
        uuid category_id FK
        string title
        text content
        text[] keywords
        int version
        int comment_count
        int like_count
        bool is_deleted
        tsvector search_vector
    }
    CONVERSATIONS {
        uuid id PK
        uuid participant_a
        uuid participant_b
        bigint total_chars
    }
    DM_MESSAGES {
        uuid id PK
        uuid conversation_id FK
        uuid sender_id
        text content
        string attachment_key
        timestamp attachment_expires_at
        bool is_recalled
        bool is_edited
        timestamp read_at
    }
```

### Bounded contexts

| Context | Tables |
|---|---|
| **Identity** | `users`, `user_preferences`, `invite_codes`, `ip_bans` |
| **Forum** | `posts`, `post_history`, `comments`, `comment_votes`, `post_co_authors`, `post_citations`, `post_views`, `post_reports`, `categories` |
| **SIG** | `sigs`, `sig_members`, `membership_applications`, `contributors`, `org_chart_overrides`, `member_classifications` |
| **Forms** | `forms`, `form_responses` |
| **Notifications** | `notifications` |
| **Direct messaging** | `conversations`, `dm_messages` |
| **Social graph** | `friendships`, `follows`, `blocks`, `profile_views`, `friend_recommendations`, `dismissed_recommendations` |
| **Files & scanning** | `files`, `file_scans` |
| **Albums** | `albums`, `album_members`, `album_photos`, `album_comments` |
| **Q&A** | `questions`, `answers`, `votes` |
| **Events** | `events`, RSVP records |
| **Moderation & audit** | `post_reports`, `audit_logs` |
| **Configuration** | `site_settings` |

### Notable indexes

- GIN index on `posts.search_vector` for `websearch_to_tsquery` FTS.
- Partial index on `dm_messages(conversation_id) WHERE read_at IS NULL` (unread count perf).
- Composite index on `posts(category_id, created_at DESC)` and `comments(post_id, created_at)`.
- `conversations` enforces `participant_a < participant_b` so each pair has one row.
- Unique constraints: `users.username`, `invite_codes.code`, `sigs.name`, `friendships(requester, recipient)`, `follows(follower, following)`, `blocks(blocker, blocked)`.

---

## 8. Redis topology

Redis 7, `allkeys-lru`, `maxmemory 256mb`, AOF `everysec` in production. It is the **only** mutable shared state outside Postgres.

```mermaid
flowchart LR
    subgraph Redis[Redis 7 — allkeys-lru, AOF]
        SES[Sessions<br/>session:{jti} → user_id<br/>TTL = role-based]
        WST[WS tickets<br/>ws_ticket:{token}<br/>TTL = 30s]
        GST[Guest tokens<br/>guest:{id} TTL=45m]
        CAP[Captchas<br/>captcha:{user} TTL=5m]
        AVA[Avatars cache<br/>avatar:{user} TTL=1h]
        RL[Rate-limit counters<br/>rate_limit:{zone}:{ip}]
        IPB[IP ban set]
        BLK[Block list cache<br/>warmed on startup]
        EVT[Event bus failures<br/>event_bus:failed list]
        DDP[Dedup<br/>event_bus:dedup:{id} TTL=10m<br/>view_dedup:* TTL=24h]
        IDM[Idempotency<br/>idempotency:{user}:{key} TTL=5m]
        PUB[Pub/Sub channels<br/>ws:notify, dm broadcast]
        BRK[Celery broker<br/>+ result backend<br/>db=0]
        STA[Public stats<br/>public:stats TTL=300s]
        CNT[Guest counter<br/>Lua atomic SETNX]
    end
```

### Key namespaces

| Pattern | TTL | Purpose |
|---|---|---|
| `session:{jti}` | role-based (45m–8h) | JWT-paired session record |
| `ws_ticket:{token}` | 30s | WebSocket auth handshake |
| `guest:{id}` | 45 min | Guest user session |
| `captcha:{user}` | 5 min | Math captcha challenge |
| `avatar:{user}` | 1h | LRU cache, max 50 entries |
| `rate_limit:{zone}:{ip}` | window | Lua script counter |
| `event_bus:failed` | — | List of permanently failed events |
| `event_bus:dedup:{event_id}` | 10 min | Idempotent event processing |
| `idempotency:{user}:{key}` | 5 min | Replay-safe POST/PUT |
| `view_dedup:post:*`, `view_dedup:profile:*` | 24h | View-count dedup |
| `public:stats` | 300s | Cached homepage stats |
| `guest_counter` | — | Atomic SETNX/INCR Lua script |
| `ws:notify` (channel) | — | Pub/Sub fan-out across workers |

---

## 9. Object storage layout (MinIO / R2)

`storage.py` rewrites internal `http://minio:9000` URLs to `MINIO_PUBLIC_URL` in presigned links so browsers can fetch. In production this points at Cloudflare R2.

```
ai3l-uploads/
├── avatars/{user_id}/{filename}              ← 2 MB cap
├── posts/{post_id}/{filename}
├── posts/{post_id}/thumbnails/{filename}
├── albums/{album_id}/cover/{filename}        ← 5 MB cap
├── albums/{album_id}/{filename}              ← 10 MB cap per photo
├── dm/{sender_id}/{uuid}_{filename}          ← 10 MB cap, 3-day TTL
├── exports/user/{user_id}/site-export-*.zip  ← 7-day TTL
├── exports/form/{form_id}/form-export-*.csv  ← 7-day TTL
└── tmp/                                      ← scratch, manual cleanup
```

**Cleanup tasks** (Celery Beat) — see §10.

**File scanning pipeline**

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as FastAPI
    participant S3 as MinIO/R2
    participant DB as Postgres
    participant CEL as Celery
    participant VT as VirusTotal

    U->>API: POST /files (multipart)
    API->>API: validate magic bytes,<br/>OOXML structure,<br/>CSV sanitise
    API->>S3: PUT object
    API->>DB: INSERT files (status=pending)
    API->>CEL: enqueue scan_file_virustotal
    API-->>U: 202 Accepted

    CEL->>VT: upload + poll
    CEL->>DB: UPDATE file_scans (CLEAN/INFECTED)
    Note over API,DB: subsequent GET /files/{id}<br/>returns 202 if pending,<br/>403 if INFECTED, 200 if CLEAN
```

---

## 10. Async / background work (Celery + Beat)

Celery is configured with **late ack**, **prefetch=1**, and `--max-memory-per-child=256000` to bound memory. Single Beat replica (replicas:1 in compose) prevents duplicate scheduling.

```mermaid
flowchart LR
    subgraph Scheduler[Celery Beat]
        B[Beat scheduler<br/>1 replica]
    end

    subgraph Broker[Redis]
        Q[(broker queue)]
    end

    subgraph Workers[Celery worker pool]
        W1[Worker 1<br/>concurrency 2]
        W2[Worker 2<br/>concurrency 2]
    end

    subgraph Sinks
        PG[(Postgres)]
        S3[(S3/R2)]
        VT[VirusTotal]
    end

    B -->|periodic| Q
    API[FastAPI] -->|on-demand| Q
    Q --> W1
    Q --> W2
    W1 --> PG
    W1 --> S3
    W1 --> VT
    W2 --> PG
    W2 --> S3
```

### Scheduled jobs (Beat)

| Task | Schedule | Purpose |
|---|---|---|
| `retry_failed_events` | every 5 min | Drain `event_bus:failed` |
| `sync_guest_counter` | every 5 min | Reconcile guest_counter |
| `auto_close_expired_forms` | every 5 min | Close past-deadline forms |
| `reconcile_counters` | every 6h | Heal denormalised counts |
| `cleanup_dm_expired_files` | hourly | Purge DM attachments past TTL |
| `cleanup_dm_expired_text` | hourly | 7-day text retention |
| `cleanup_old_file_scans` | daily | Drop scan rows > 30d |
| `cleanup_old_audit_logs` | daily | Archive audit > 1y |
| `cleanup_old_site_exports` | daily | Drop exports > 7d |
| `cleanup_dm_orphan_files` | daily | DM orphan FS cleanup |
| `compute_friend_recommendations` | daily | Score graph |
| `cleanup_orphan_files` | weekly | Drop S3 with no DB ref |
| `cleanup_old_read_notifications` | weekly | Drop read > 90d |
| `cleanup_dm_orphan_quotas` | weekly | Stale DM quota rows |
| `cleanup_empty_dm_conversations` | weekly | Drop zero-message convos |
| `cleanup_dismissed_recommendations` | weekly | Drop dismissed > 90d |

### On-demand jobs

| Task | Trigger |
|---|---|
| `export_form_csv` | User export request |
| `site_export` | User data export request (GDPR) |
| `generate_thumbnail` | Album/photo upload |
| `scan_file_virustotal` | File upload (when `VT_API_KEY` set) |

---

## 11. Real-time pipeline (WebSocket + event bus)

Two complementary mechanisms:

1. **In-process event bus** (`app/core/event_bus.py`) — synchronous-looking async pub/sub for cross-service notifications inside one worker. Handlers retry up to `MAX_RETRIES=2`, then push to `event_bus:failed` for Celery retry.
2. **Redis Pub/Sub** — fan-outs WebSocket events across multiple FastAPI workers so users connected to *any* worker receive their messages.

```mermaid
sequenceDiagram
    autonumber
    participant U as User-A (browser)
    participant WS as FastAPI worker N<br/>(WS endpoint)
    participant EB as event_bus
    participant SVC as service<br/>(comment.py)
    participant REPO as repository
    participant PG as Postgres
    participant RED as Redis Pub/Sub
    participant U2 as User-B (browser)<br/>connected to worker M

    U->>SVC: POST /posts/{id}/comments
    SVC->>REPO: INSERT comment
    REPO->>PG: SQL
    SVC->>EB: emit comment.created
    EB-->>SVC: handler runs (mention notify)
    EB->>RED: publish ws:notify {target_user, payload}
    RED-->>WS: subscriber on worker M
    WS-->>U2: NEW_NOTIFICATION / NEW_DM / DM_EDITED ...
    SVC-->>U: 201 Created
```

### WebSocket auth handshake (ticket-based)

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant API as FastAPI HTTP
    participant RED as Redis
    participant WSEP as FastAPI /ws

    FE->>API: POST /auth/ws-ticket (cookie auth)
    API->>RED: SET ws_ticket:{token} user_id EX 30
    API-->>FE: { ticket }
    FE->>WSEP: WSS upgrade ?ticket={token}
    WSEP->>RED: GETDEL ws_ticket:{token}
    WSEP-->>FE: 101 Switching Protocols
    loop heartbeat
        WSEP-->>FE: ping
        FE-->>WSEP: pong (max 1/5s)
    end
```

### Event types pushed over WS

| Event | Source | Target |
|---|---|---|
| `NEW_NOTIFICATION` | notification service | recipient |
| `NEW_DM` / `DM_EDITED` / `DM_RECALLED` / `DM_READ` | dm service | both participants |
| `ROLE_CHANGED` | user/auth service | the user (forces UI re-evaluation) |
| `FORCE_LOGOUT` | auth/admin | the user (ban or session revoke) |

---

## 12. Request lifecycles (sequence diagrams)

### 12.1 Login (member)

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant N as nginx
    participant A as FastAPI
    participant RED as Redis
    participant DB as Postgres

    U->>N: POST /api/v1/auth/login (creds + captcha)
    N->>A: forward (rate-limit "auth" 5/min)
    A->>A: captcha check
    A->>DB: lookup user (Argon2 verify)
    Note right of A: dummy hash on miss<br/>to defeat timing oracle
    A->>RED: SET session:{jti} user_id EX role-based
    A-->>U: Set-Cookie access_token (HttpOnly)<br/>+ csrf_token (readable)<br/>+ {role, expires_at}
    U->>U: store role + expiresAt in localStorage
    U->>A: GET /auth/ws-ticket
    A->>RED: SET ws_ticket TTL 30s
    A-->>U: { ticket }
    U->>A: WSS /ws?ticket=...
```

### 12.2 Create post with mention

```mermaid
sequenceDiagram
    autonumber
    participant U as Author
    participant API as FastAPI
    participant SVC as post service
    participant REPO as post_repo
    participant DB as Postgres
    participant EB as event_bus
    participant NOTIF as notification svc
    participant RED as Redis
    participant V as Mentioned user

    U->>API: POST /posts {title, content, mentions}
    API->>SVC: create_post()
    SVC->>SVC: nh3 sanitise + length check
    SVC->>REPO: INSERT (returns id)
    REPO->>DB: SQL with TSVECTOR update
    SVC->>EB: emit post.created
    EB->>NOTIF: handler.notify_mentions
    NOTIF->>DB: INSERT notifications
    NOTIF->>RED: PUBLISH ws:notify {target=V}
    RED-->>V: NEW_NOTIFICATION
    SVC-->>API: PostResponse
    API-->>U: 201
```

### 12.3 DM send with attachment

```mermaid
sequenceDiagram
    autonumber
    participant A as Sender
    participant API as FastAPI
    participant DB as Postgres
    participant S3 as MinIO/R2
    participant CEL as Celery
    participant RED as Redis
    participant B as Recipient

    A->>API: POST /dm/upload (file ≤10MB)
    API->>API: magic-byte + extension + CSV/UTF8 check
    API->>S3: PUT dm/{sender}/{uuid}_{name}
    API->>DB: INSERT files + file_scans(pending)
    API->>CEL: scan_file_virustotal
    API-->>A: { attachment_key, expires_at }

    A->>API: POST /dm/messages {to, text, attachment_key}
    API->>API: check block + dm_friends_only
    API->>DB: pg_advisory_xact_lock + INSERT dm_messages<br/>UPDATE conversations.total_chars
    API->>RED: PUBLISH ws:dm {a,b, payload}
    RED-->>B: NEW_DM
    RED-->>A: NEW_DM (echo)
    API-->>A: 201
```

### 12.4 Form submission with quota

```mermaid
sequenceDiagram
    autonumber
    participant U as Respondent
    participant API as FastAPI
    participant DB as Postgres

    U->>API: POST /forms/{id}/responses with answers
    API->>API: validate question schema [server-side]
    API->>DB: BEGIN then pg_advisory_xact_lock on hashtext of form_id
    API->>DB: SELECT count + max_respondents [in tx]
    alt under quota
        API->>DB: INSERT form_responses
        API->>DB: COMMIT
        API-->>U: 201
    else quota reached
        API->>DB: ROLLBACK
        API-->>U: 409 FORM_FULL
    end
```

---

## 13. Security architecture

```mermaid
flowchart LR
    subgraph Edge
        CF[Cloudflare WAF +<br/>DDoS + bot]
        NGX[nginx<br/>rate-limit zones<br/>HSTS / CSP / TLS]
    end

    subgraph App
        IPBAN[IP-ban middleware]
        BODY[Body-size + concurrency]
        CSRF[CSRF double-submit]
        IDM[Idempotency]
        AUTH[JWT + Redis session<br/>cross-validated]
        ROLE[Role guards<br/>requires_member / admin /<br/>sig_admin]
        RL[App-level rate-limit<br/>Lua script per zone]
        SAN[Input sanitisation<br/>nh3 / DOMPurify /<br/>magic bytes / CSV / OOXML]
        LOG[Audit log]
    end

    subgraph Data
        ARGON[Argon2 password]
        BLACK[User block cache]
        VT[VirusTotal scan]
        PII[PII masking in logs]
    end

    CF --> NGX --> IPBAN --> BODY --> CSRF --> IDM --> AUTH --> ROLE --> RL --> SAN
    AUTH --> ARGON
    ROLE --> BLACK
    SAN --> VT
    SAN --> LOG
    LOG --> PII
```

### Highlights

- **Auth**: `access_token` is HttpOnly + Secure + SameSite. CSRF via readable `csrf_token` cookie + `X-CSRF-Token` header (double-submit).
- **JWT–Session cross-check**: every authed request validates the JWT *and* looks up `session:{jti}` in Redis — revocation is one DEL away.
- **Timing oracle**: `_DUMMY_HASH` Argon2 in `services/auth.py` is hashed for non-existent / deleted / banned users to keep login wall-clock constant.
- **CSP**: nginx hardcodes `http://localhost:19000` in dev; in prod `STORAGE_CSP_ORIGIN` substitutes the R2 origin via `docker-entrypoint.sh` envsubst.
- **Rate-limit zones (nginx)**: `auth` 5/m, `write` 5/m, `dm_write` 30/m, `global` 20/s, `ws_conn` 5 concurrent/IP.
- **VirusTotal**: every uploaded file is scanned async; pending → 202, infected → 403, clean → 200.
- **Audit log**: every privileged mutation (role change, ban, delete, IP ban) writes to `audit_logs` with masked IP.
- **Container hardening**: `security_opt: no-new-privileges`, `cap_drop: ALL` on PG/Redis/MinIO; nginx runs `server_tokens off`; Redis password via env (not visible in `docker inspect`).

---

## 14. Deployment view

```mermaid
flowchart TB
    classDef host fill:#fef3c7,stroke:#b45309
    classDef ctn fill:#bae6fd,stroke:#0369a1

    subgraph Host[Production host — Linux VM]
        direction TB
        subgraph Stack[docker compose -f prod.yml]
            CFD[cloudflared]:::ctn
            NG[nginx]:::ctn
            FA[fastapi<br/>gunicorn 4 workers]:::ctn
            CE[celery]:::ctn
            CB[celery-beat<br/>replicas: 1]:::ctn
            MG[migrate one-shot]:::ctn
            PG[(postgres 15)]:::ctn
            RE[(redis 7)]:::ctn
        end
    end

    subgraph CFExt[Cloudflare]
        TUN[Cloudflare Tunnel]
        CDN[CDN / WAF]
        R2[(R2 bucket)]
    end

    USER([User]) -->|HTTPS| CDN --> TUN --> CFD --> NG
    NG --> FA
    FA --> PG
    FA --> RE
    FA --> R2
    CE --> RE
    CE --> PG
    CE --> R2
    CB --> RE
    MG --> PG
```

### Build & release

| Step | Command |
|---|---|
| Build images | `docker compose -f docker-compose.prod.yml build` |
| Start migrate first | `docker compose ... up migrate` |
| Bring up stack | `docker compose ... up -d` |
| Tail logs | `docker compose ... logs -f fastapi nginx celery` |
| Apply env change | `docker compose ... up -d <svc>` (NOT `restart`) |

### Dev workflow

- `docker compose up` (or `--build` after package change) starts everything.
- `build-frontend` one-shot writes Vite dist into `nginx-html` volume — nginx always serves the latest static build.
- nginx dev config uses `resolver 127.0.0.11 valid=5s` + `set $var` so service IP changes don't 502.
- `MINIO_PUBLIC_URL=http://localhost:19000` **must** be set in `.env` for browser-accessible presigned URLs.

---

## 15. Cross-cutting concerns

### Observability

- **Logging**: Loguru JSON to stdout; nginx JSON access logs; Docker `json-file` driver with 50 MB × 5 rotation.
- **Tracing**: Optional Datadog APM via `DD_AGENT_HOST` / `DD_TRACE_ENABLED`.
- **Errors**: Sentry SDK with `SENTRY_TRACES_SAMPLE_RATE=0.1`.
- **Health**: `GET /health/live` (public), `GET /health` (super-admin only — exposes pool stats).

### Configuration

`app/core/config.py` is the single source of truth. Production rejects:

- `S3_ACCESS_KEY_ID=minioadmin`
- CORS origins containing `localhost`
- `FASTAPI_DEBUG=true`
- Empty `COOKIE_DOMAIN` (warns)
- Cloud-synced project folder (warns at startup)

### i18n

- 17 languages in `src/locales/` (English bundled, others lazy).
- `users.preferred_language` stored in DB, applied on login.
- `document.documentElement.lang` updated by `useLocale()` for accessibility.
- Dates formatted via `utils/date.ts:formatDate(date, locale)` — never raw `.toLocaleDateString()`.

### Pagination convention

`COUNT(*) OVER()` single-query pattern in repositories returns `(rows, total)`. Frontend `usePagination` and `useFetchPaginated` consume `{items, total}` shape.

### Idempotency

POST/PUT supporting `Idempotency-Key` header are cached in Redis at `idempotency:{user}:{key}` for 5 minutes; same key returns the original response body.

---

## Appendix A — File counts (current snapshot)

| Layer | Files |
|---|---|
| Backend endpoints | 27 routers |
| Backend services | 34 modules |
| Backend repositories | 36 modules |
| Backend converters | 13 modules |
| Backend schemas | 24 modules |
| Backend tasks | 11 modules / ~16 scheduled jobs |
| Backend core infra | 18 modules |
| Frontend views | 54 |
| Frontend components | 59 |
| Frontend composables | 19 |
| Frontend API modules | 22 |
| Frontend stores | 4 |
| Frontend types | 18 |
| Frontend locales | 17 languages |
| Backend unit tests | ~3,693 |
| Frontend Vitest tests | ~3,066 |

## Appendix B — Where to look

| Question | File |
|---|---|
| HTTP entrypoint, middleware order, lifespan | `backend/app/main.py` |
| Settings & env validation | `backend/app/core/config.py` |
| Celery schedule | `backend/app/celery_app.py` |
| Event bus contract | `backend/app/core/event_bus.py` + `event_handlers.py` |
| Migration history | `backend/alembic/versions/` |
| Frontend bootstrap | `frontend/src/main.ts` + `App.vue` |
| Router map & guards | `frontend/src/router/index.ts` |
| WS lifecycle | `frontend/src/composables/useWebSocket.ts` |
| Compose topology | `docker-compose.yml` / `.override.yml` / `.prod.yml` |
| Edge config | `nginx/nginx.conf`, `nginx/conf.d*/default.conf`, `nginx/snippets/security-headers.conf` |
