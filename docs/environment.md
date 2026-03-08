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
| `LOG_FORMAT` | `text` | Set to `json` in production for structured logging |

---

## JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | — | Token signing key |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Default token TTL (per-role TTLs override this at runtime) |

---

## CORS and Cookies

| Variable | Description |
|---|---|
| `CORS_ORIGINS` | Comma-separated list of allowed origins (e.g. `https://your-domain.com`) |
| `COOKIE_SECURE` | Set to `true` in production (requires HTTPS) |
| `COOKIE_SAMESITE` | Cookie `SameSite` policy: `lax` or `strict` |

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

## Observability (Optional)

| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry project DSN for error tracking |
| `SENTRY_TRACES_SAMPLE_RATE` | APM trace sampling rate (`0.0` to `1.0`) |
| `DD_API_KEY` | Datadog API key |
| `DD_SITE` | Datadog site (`datadoghq.com` or `datadoghq.eu`) |
| `DD_TRACE_ENABLED` | Enable ddtrace auto-instrumentation (`true` or `false`) |
