# Backend Performance Audit

Date: 2026-03-07 (updated 2026-03-11)

## HIGH Priority

### 1. S3 LIST on Every File Upload (Quota Check)
- **File:** `backend/app/core/async_storage.py:17-33`
- **Issue:** Every file upload triggers a `list_objects_v2` call to MinIO to calculate the user's total storage usage. O(n) where n is number of user's objects.
- **Fix:** Track storage usage in the database (increment on upload, decrement on delete). Architectural change for future consideration.

### 2. Synchronous HTTP in Avatar Proxy — Acceptable
- **File:** `backend/app/api/v1/endpoints/about.py`
- **Status:** Uses `requests.get()` via `run_in_executor()` with LRU cache (max 50 entries, 1h TTL). Thread executor prevents event loop blocking. Acceptable for GitHub avatar fetches.

### 3. No Request Timeout on FastAPI — ✅ Resolved (2026-03-11)
- **Status:** Added `--timeout-keep-alive 30` to uvicorn CMD in Dockerfile. Per-endpoint timeouts via `asyncio.wait_for()` can be added as needed.

## MEDIUM Priority

### 4. Celery Task Retry Without Backoff — ✅ Resolved (2026-03-11)
- **Status:** `check_virustotal` already had `default_retry_delay=60`. Added `max_retries=2, default_retry_delay=60` to `export_form_csv`.

### 5. Event Bus Retry in Request Context — ✅ Resolved
- **Status:** Proper backoff (`RETRY_DELAY=1.0`), Redis persistence for failed events, and bounded periodic retry via Celery task.

### 6. WebSocket Connection Leak Potential — ✅ Resolved
- **Status:** Proper `try/except/finally` cleanup in both WebSocket endpoint and Redis subscriber. `CancelledError` handled correctly.

### 7. No Response Compression for API — ✅ Resolved (2026-03-11)
- **Status:** nginx has `gzip on`, `gzip_proxied any`, and proper `gzip_types`. Added `gzip_min_length 1024` to avoid compressing tiny responses.

## LOW Priority

### 8. Health Endpoint Hits Database — ✅ Resolved (2026-03-11)
- **Status:** Added lightweight `/health/live` endpoint (no DB/Redis/MinIO checks). Docker healthcheck updated to use `/health/live`. Deep check remains at `/health` for readiness probes.

### 9. Structured Logging — ✅ Resolved
- **Status:** Loguru configured with `LOG_FORMAT=json` for structured output.

### 10. Missing Cache Headers on Static Content — ✅ Resolved (2026-03-11)
- **Status:** Added `Cache-Control: private, max-age=60` to GET `/categories` and GET `/sigs`. Nginx serves `/assets/` with `expires 1y` + `Cache-Control: public, immutable` for hashed static files. SPA `index.html` served with `Cache-Control: no-cache`.
