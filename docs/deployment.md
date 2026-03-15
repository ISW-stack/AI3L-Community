# Production Deployment — AI3L Community Platform

---

## Step-by-Step Deployment

### 1. Configure environment

In `.env`, set:

```bash
FASTAPI_ENV=production
FASTAPI_DEBUG=false
FASTAPI_WORKERS=4          # match to available CPU cores
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://your-domain.com
COOKIE_SECURE=true
```

Replace every `changeme_*` value with a strong, randomly generated secret. See [`environment.md`](environment.md) for the full variable reference.

### 2. Issue TLS certificates

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

Certificates are written to `./nginx/ssl/`. Run this once before enabling the HTTPS server block in Nginx.

### 3. Enable HTTPS in Nginx

In `nginx/conf.d/default.conf`, uncomment the HTTPS server block and the HTTP-to-HTTPS redirect. Replace `YOUR_DOMAIN` with your domain name.

### 4. Start services

```bash
docker compose up -d
```

Alembic migrations run automatically via the `migrate` service before FastAPI starts. No manual migration step is required.

### 5. Initialize MinIO (first time only)

```bash
./scripts/init-minio.sh
```

### 6. Enable Datadog monitoring (optional)

```bash
DD_API_KEY=your_key docker compose --profile monitoring up -d
```

### 7. Schedule automated tasks

Add to crontab on the host machine:

```bash
0 3 * * *     /path/to/ai3l-community/scripts/backup-db.sh
0 3 */60 * *  /path/to/ai3l-community/scripts/renew-certs.sh
```

---

## Production Checklist

- [ ] All `changeme_*` values replaced with strong random secrets
- [ ] `FASTAPI_ENV=production` and `FASTAPI_DEBUG=false`
- [ ] `CORS_ORIGINS` set to the production domain
- [ ] `COOKIE_SECURE=true`
- [ ] TLS certificates issued and HTTPS server block enabled in Nginx
- [ ] `FASTAPI_WORKERS` set to match available CPU cores
- [ ] `SENTRY_DSN` configured for error tracking
- [ ] Database backups scheduled via cron
- [ ] Certificate renewal scheduled via cron
- [ ] `MINIO_PUBLIC_URL` set to the browser-accessible MinIO URL

---

## Operational Scripts

All scripts are in `scripts/`. Make them executable with `chmod +x scripts/*.sh`.

### `init-minio.sh`

Creates the MinIO bucket and applies access policies. Run once after the first `docker compose up`.

```bash
./scripts/init-minio.sh
```

### `build-frontend.sh`

Builds the frontend for production and copies the output to `nginx/html/`. Use this to update static files without a full Docker rebuild.

```bash
./scripts/build-frontend.sh            # build and copy
./scripts/build-frontend.sh --restart  # build, copy, and restart nginx
```

In local development, you do not need this script — the Vite dev server handles HMR automatically.

### `backup-db.sh`

Creates a compressed PostgreSQL dump in `./backups/`. Retains the last 30 backups automatically.

```bash
./scripts/backup-db.sh
# Output: ./backups/ai3l_community_YYYYMMDD_HHMMSS.sql.gz
```

### `restore-db.sh`

Restores the database from a backup file.

```bash
./scripts/restore-db.sh ./backups/ai3l_community_20260101_030000.sql.gz
```

### `init-letsencrypt.sh`

Issues a TLS certificate from Let's Encrypt for a domain.

```bash
./scripts/init-letsencrypt.sh your-domain.com
```

### `renew-certs.sh`

Renews Let's Encrypt certificates and reloads Nginx. Schedule with cron every 60 days.

```bash
./scripts/renew-certs.sh
```

---

## Database Migrations

Migrations are managed with Alembic. The `migrate` service in `docker-compose.yml` runs `alembic upgrade head` automatically before FastAPI starts.

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
| `g7h8i9j0k1l2` | Invite code consumption tracking |
| `h8i9j0k1l2m3` | Composite indexes for query performance |
| `i9j0k1l2m3n4` | Remove unused sub_admin_ids from categories |
| `j0k1l2m3n4o5` | Add allow_non_members flag to forms |
| `k1l2m3n4o5p6` | Add file_scans table (VirusTotal integration) |
| `l2m3n4o5p6q7` | Forum experience overhaul |
| `m3n4o5p6q7r8` | Add missing status indexes |
| `n4o5p6q7r8s9` | Add contributors table |
| `o5p6q7r8s9t0` | Fix SIG name unique constraint |
| `p6q7r8s9t0u1` | Add form_response unique constraint and index |
| `q7r8s9t0u1v2` | Add indexes on notifications and post_history |
| `r9s0t1u2v3w4` | Add preferred_language to users (i18n support) |
| `s0t1u2v3w4x5` | Add reactions (like/smile/cry) to posts |
| `t1u2v3w4x5y6` | Clear legacy form descriptions |
| `u2v3w4x5y6z7` | Add indexes on form_responses and comments |
| `v3w4x5y6z7a8` | Add storage_used_bytes column to users |
| `w4x5y6z7a8b9` | Add user_preferences table |
| `x5y6z7a8b9c0` | Add like_count column to posts |

---

## Rate Limiting Reference

### Nginx Layer

| Zone | Limit | Applies To |
|---|---|---|
| `global` | 20 requests/second per IP | All `/api/` endpoints |
| `write` | 5 requests/minute per IP | POST, PUT, PATCH, DELETE |

GET and HEAD requests bypass the write zone. Both zones allow short bursts with `nodelay`. Clients exceeding the limit receive `429 Too Many Requests`.

### Application Layer (Redis-backed)

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

Post creation is additionally limited to **50 posts per user per day**. The endpoint returns error code `SYS_429` when this limit is reached.
