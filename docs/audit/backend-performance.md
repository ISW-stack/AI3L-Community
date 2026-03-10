# Backend Performance Audit

Date: 2026-03-07

## HIGH Priority

### 1. S3 LIST on Every File Upload (Quota Check)
- **File:** `backend/app/core/async_storage.py:17-33`
- **Issue:** Every file upload triggers a `list_objects_v2` call to MinIO to calculate the user's total storage usage. This is O(n) where n is the number of objects the user has uploaded. For users with hundreds of files, this adds seconds to every upload.
- **Fix:** Track storage usage in the database (increment on upload, decrement on delete) and query the DB instead of scanning S3.

### 2. Synchronous HTTP in Avatar Proxy
- **File:** `backend/app/api/v1/endpoints/about.py:78-82`
- **Issue:** Avatar fetching from GitHub uses `requests.get()` via `run_in_executor()`. While this doesn't block the event loop, it ties up a thread pool thread for up to 10 seconds per request.
- **Fix:** Use `httpx.AsyncClient` instead of `requests` to make truly async HTTP calls without consuming thread pool resources.

### 3. No Request Timeout on FastAPI
- **Issue:** FastAPI/Uvicorn has no per-request timeout configured. A slow database query or external API call can hold a worker indefinitely.
- **Fix:** Configure `--timeout-keep-alive` in Uvicorn and add per-endpoint timeouts using `asyncio.wait_for()` for external calls.

## MEDIUM Priority

### 4. Celery Task Retry Without Backoff
- **Issue:** Celery tasks that fail (e.g., VirusTotal scanning) retry immediately without exponential backoff, potentially hammering external APIs.
- **Fix:** Configure `retry_backoff=True` and `retry_backoff_max=600` on task definitions.

### 5. Event Bus Retry in Request Context
- **File:** `backend/app/core/event_bus.py`
- **Issue:** Event bus retries (MAX_RETRIES=2) happen in the request context. If an event handler is slow, it delays the API response.
- **Fix:** Consider offloading event handling to background tasks or Celery for non-critical events.

### 6. WebSocket Connection Leak Potential
- **Issue:** WebSocket disconnection handling may not properly clean up Redis Pub/Sub subscriptions in all error paths (e.g., unexpected disconnection during message processing).
- **Fix:** Use `try/finally` blocks around the WebSocket receive loop to ensure Redis subscription cleanup.

### 7. No Response Compression for API
- **Issue:** While nginx has gzip enabled for proxied content, the `gzip_proxied any` setting may not compress all API responses depending on upstream headers.
- **Fix:** Verify that API JSON responses are being gzip-compressed by nginx. Add `gzip_min_length 256` to avoid compressing tiny responses.

## LOW Priority

### 8. Health Endpoint Hits Database
- **Issue:** The `/health` endpoint may query the database to verify connectivity, adding load during health check intervals (every 30s from Docker + any load balancer).
- **Fix:** Use a lightweight health check that only verifies the process is running. Add a separate `/health/ready` endpoint for deep checks.

### 9. Structured Logging — ✅ Resolved
- **Status:** Loguru is configured as the logging backend. `LOG_FORMAT=json` (the current default) produces structured JSON output. `LOG_FORMAT=text` is available for local development readability. No further action needed.

### 10. Missing Cache Headers on Static Content
- **Issue:** API responses for rarely-changing data (categories, SIG list) don't include cache headers. Browsers refetch this data on every navigation.
- **Fix:** Add `Cache-Control` headers for stable data, or implement ETags for conditional requests.
