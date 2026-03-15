# Environment Variables — AI3L Community Platform

Copy `.env.example` to `.env` and set all values. Every variable marked `changeme_*` in the example file must be replaced before running in any environment.

---

## PostgreSQL

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `ai3l` | Database user |
| `POSTGRES_PASSWORD` | — | Database password |
| `POSTGRES_DB` | `ai3l_community` | Database name |
| `POSTGRES_HOST` | `postgres` | Hostname (Docker service name in Compose) |
| `POSTGRES_PORT` | `5432` | Port |

### Optional PostgreSQL Tuning

| Variable | Description |
|---|---|
| `PG_SHARED_BUFFERS` | PostgreSQL `shared_buffers` (e.g. `256MB`) |
| `PG_EFFECTIVE_CACHE` | PostgreSQL `effective_cache_size` (e.g. `512MB`) |
| `PG_WORK_MEM` | PostgreSQL `work_mem` (e.g. `4MB`) |
| `PG_MAX_CONNECTIONS` | PostgreSQL `max_connections` |

---

## Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Hostname |
| `REDIS_PORT` | `6379` | Port |
| `REDIS_PASSWORD` | — | Redis `requirepass` value |

---

## FastAPI

| Variable | Default | Description |
|---|---|---|
| `FASTAPI_ENV` | `development` | Set to `production` in production |
| `FASTAPI_DEBUG` | `true` | Enables Swagger UI and verbose errors. Set to `false` in production |
| `FASTAPI_HOST` | `0.0.0.0` | Bind address |
| `FASTAPI_PORT` | `8000` | Internal port |
| `FASTAPI_WORKERS` | `1` | Uvicorn worker count. Set to number of CPU cores in production |
| `SECRET_KEY` | — | Application secret, minimum 32 characters |
| `LOG_LEVEL` | `DEBUG` | Set to `INFO` in production |
| `LOG_FORMAT` | `json` | Log output format (`json` for structured logging, `text` for human-readable) |
| `TRUSTED_HOSTS` | — | Comma-separated list of allowed `Host` header values (enforced by `TrustedHostMiddleware` in production) |
| `MAX_USER_STORAGE_BYTES` | `1073741824` | Per-user upload quota in bytes (default: 1 GB) |

---

## JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | — | Token signing key |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_GUEST_EXPIRE_MINUTES` | `45` | Token TTL for `GUEST` role (minutes) |
| `JWT_MEMBER_EXPIRE_MINUTES` | `180` | Token TTL for `MEMBER` role (minutes) |
| `JWT_ADMIN_EXPIRE_MINUTES` | `300` | Token TTL for `ADMIN` role (minutes) |
| `JWT_SUPER_ADMIN_EXPIRE_MINUTES` | `480` | Token TTL for `SUPER_ADMIN` role (minutes) |

---

## CORS and Cookies

| Variable | Description |
|---|---|
| `CORS_ORIGINS` | Comma-separated list of allowed origins (e.g. `https://your-domain.com`) |
| `COOKIE_SECURE` | Set to `true` in production (requires HTTPS) |
| `COOKIE_SAMESITE` | Cookie `SameSite` policy: `lax` or `strict` |
| `COOKIE_DOMAIN` | Cookie domain scope (e.g. `.example.com` for subdomain sharing) |

---

## MinIO

| Variable | Default | Description |
|---|---|---|
| `MINIO_ROOT_USER` | `minioadmin` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | — | MinIO admin password |
| `MINIO_ENDPOINT` | `minio:9000` | Internal endpoint (Docker service name) |
| `MINIO_BUCKET_NAME` | `ai3l-uploads` | Upload bucket name |
| `MINIO_USE_SSL` | `false` | Enable TLS for MinIO connection |
| `MINIO_PUBLIC_URL` | — | **Required in local dev.** Browser-accessible base URL for presigned URLs (e.g. `http://localhost:19000`). The server rewrites the internal `minio:9000` hostname in every generated presigned URL to this value so browsers can fetch files directly. |

---

## Celery

| Variable | Description |
|---|---|
| `CELERY_BROKER_URL` | Redis URL for task queue (uses DB 1, e.g. `redis://:pass@redis:6379/1`) |
| `CELERY_RESULT_BACKEND` | Redis URL for task results (uses DB 2) |

---

## Super Admin Bootstrap

| Variable | Description |
|---|---|
| `SUPER_ADMIN_USERNAME` | Username for the auto-created super admin account (created on first startup) |
| `SUPER_ADMIN_PASSWORD` | Password for the auto-created super admin account |

---

## Rate Limit Overrides (Optional)

All application-layer rate limits can be tuned per environment without a code change. Each limit is read from two environment variables using the pattern `RATE_LIMIT_{KEY}_MAX` (maximum count) and `RATE_LIMIT_{KEY}_WINDOW` (window in seconds). If unset, the compiled-in defaults are used.

| Key | Default max | Default window | Endpoint(s) |
|---|---|---|---|
| `LOGIN` | `10` | `60` | `POST /auth/login` |
| `REGISTER` | `5` | `60` | `POST /auth/register` |
| `GUEST` | `10` | `60` | `POST /auth/guest/{code}` |
| `COMMENT` | `30` | `60` | `POST /posts/{id}/comments` |
| `REPORT` | `5` | `60` | `POST /posts/{id}/report` |
| `CAPTCHA` | `20` | `60` | `GET /auth/captcha` |
| `FILE_UPLOAD` | `10` | `60` | `POST /files/upload/editor` |
| `FORM_SUBMIT` | `5` | `60` | `POST /forms/{id}/submit` |
| `FORM_EXPORT` | `1` | `300` | `POST /forms/{id}/export` |
| `FORM_STATS` | `10` | `60` | `GET /forms/{id}/stats` |
| `INVITE_GEN` | `5` | `3600` | `POST /auth/invite-code` |
| `INVITE_VERIFY` | `30` | `60` | `GET /auth/invite-code/{code}` |
| `REACTION` | `30` | `60` | `POST /posts/{id}/comments/{id}/reaction` |
| `SIG_JOIN` | `10` | `60` | `POST /sigs/{id}/join` |
| `SIG_MANAGE` | `20` | `60` | SIG member management |
| `SIG_CRUD` | `10` | `60` | SIG create/update/delete |
| `CATEGORY_CRUD` | `10` | `60` | Category create/update/delete |
| `PREFERENCES` | `10` | `60` | `PUT /users/me/preferences` |

Example:
```env
RATE_LIMIT_LOGIN_MAX=20
RATE_LIMIT_LOGIN_WINDOW=60
```

---

## VirusTotal (Optional)

| Variable | Default | Description |
|---|---|---|
| `VT_API_KEY` | — | VirusTotal API key. If empty, file scanning is silently skipped. |

---

## Observability (Optional)

| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry project DSN for error tracking |
| `SENTRY_TRACES_SAMPLE_RATE` | APM trace sampling rate (`0.0` to `1.0`) |
| `DD_AGENT_HOST` | Datadog agent hostname for ddtrace (e.g. `datadog-agent`) |
| `DD_TRACE_ENABLED` | Enable ddtrace auto-instrumentation (`true` or `false`) |
| `DD_API_KEY` | Datadog API key (set on the `datadog-agent` Docker service) |
| `DD_SITE` | Datadog ingestion site (`datadoghq.com` or `datadoghq.eu`) |
