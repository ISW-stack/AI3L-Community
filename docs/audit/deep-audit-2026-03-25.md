# AI3L Community - Deep Security Audit Report (Round 2)

**Date:** 2026-03-25
**Scope:** 7-agent parallel deep audit across all ~540 source files
**Areas:** Authentication, SQL/DB, File Upload/Storage, WebSocket/DM, Frontend, Business Logic, Infrastructure
**P0/P1 Fixes:** 9 items fixed, 34 new tests

---

## Summary

| Severity | Found | Fixed (P0/P1) | Deferred (P2/P3) |
|----------|-------|---------------|------------------|
| CRITICAL | 5 | 5 | 0 |
| HIGH | 12 | 6 | 6 |
| MEDIUM | 31 | 0 | 31 |
| LOW | 49 | 0 | 49 |
| INFO | ~16 | 0 | ~16 |
| **Total** | **~113** | **11** | **~102** |

---

## P0 Fixes (CRITICAL)

### C-01: Album/DM bypass VirusTotal scanning
- **Files changed:** `app/core/file_validation.py`, `app/services/album.py`, `app/services/dm.py`
- **Fix:** Added `trigger_virus_scan()` helper; called from `upload_photo`, `upload_cover`, `upload_file_zip`, and DM `send_message` after MinIO upload. Inserts `file_scans` record + dispatches `check_virustotal.delay()`.

### C-02: DM .zip no validation
- **File changed:** `app/services/dm.py`
- **Fix:** Removed `.zip` from `_DM_ALLOWED_EXTENSIONS`. DM is for simple attachments; ZIP requires complex validation not suitable for the DM flow.

### C-03: .env on OneDrive
- **File changed:** `app/main.py`
- **Fix:** Added cloud-sync folder detection at startup (OneDrive, Dropbox, Google Drive, iCloud) with `logger.warning()`.

### C-04: Missing SERVER_DOMAIN in production template
- **File changed:** `.env.production.example`
- **Fix:** Added `SERVER_DOMAIN=yourdomain.com` with documentation comment.

### C-05: PG/Redis/MinIO missing container hardening
- **Files changed:** `docker-compose.yml`, `docker-compose.prod.yml`
- **Fix:** Added `security_opt: [no-new-privileges:true]` and `cap_drop: [ALL]` to postgres, redis, and minio services.

## P1 Fixes (HIGH)

### H-01: serve_file fail-open on DB error
- **File changed:** `app/api/v1/endpoints/files.py`
- **Fix:** Changed generic `except Exception` to raise 503 (`AppError(ErrorCode.SYS_500, 503, ...)`) instead of silently continuing.

### H-02: DOCX magic byte only checks generic ZIP signature
- **Files changed:** `app/core/file_validation.py`, `app/services/dm.py`
- **Fix:** Added `validate_docx_structure()` and `validate_ooxml_structure()` functions. Editor upload and DM now verify DOCX contains `[Content_Types].xml` + `word/` directory. XLSX/PPTX require `[Content_Types].xml`.

### H-03: Scan record inserted after upload (race window)
- **File changed:** `app/api/v1/endpoints/files.py`
- **Fix:** `serve_file` now treats `scan is None` for editor files as "pending" (returns 202). This closes the window where a file with no scan record could be served.

### H-04: DM .txt/.csv no content validation (CSV injection)
- **File changed:** `app/services/dm.py`
- **Fix:** Added `_sanitize_csv_content()` that prefixes dangerous cells (`=`, `+`, `-`, `@`, `\t`, `\r`) with single quote. Added UTF-8 validation for `.txt` and `.csv` files.

---

## Tests Added

34 new tests in `tests/test_audit_2026_03_25.py`:

| Test Class | Count | Covers |
|------------|-------|--------|
| TestDocxStructureValidation | 8 | H-02: valid/invalid DOCX, JAR masquerade, OOXML, editor integration |
| TestDmZipRemoved | 2 | C-02: .zip not in allowlist, validation rejects |
| TestDmCsvSanitization | 7 | H-04: injection prefixes, normal data, UTF-8 rejection |
| TestDmOfficeValidation | 5 | H-02: fake/real DOCX/XLSX/PPTX in DM |
| TestServeFileFailClose | 2 | H-01: DB error→503, H-03: missing scan→202 |
| TestTriggerVirusScan | 3 | C-01: insert record, failure resilience, ImportError resilience |
| TestCloudSyncWarning | 1 | C-03: OneDrive detection |
| TestEnvProductionExample | 1 | C-04: SERVER_DOMAIN present |
| TestDockerComposeSecurity | 5 | C-05: security_opt/cap_drop on PG/Redis/MinIO |

---

## P2/P3 Fixes (same session)

25 additional fixes applied with 25 new tests in `tests/test_audit_2026_03_25_p2p3.py`.

### Auth Layer
| Fix | File | Change |
|-----|------|--------|
| JWT role cross-check | `deps.py` | DB role compared to JWT claim; mismatch → 401 |
| Per-account lockout | `endpoints/auth.py` | `rl:login:user:{username}` 20/5min |
| Password same check | `services/user.py` | Reject identical old/new password |
| Guest display_name | `schemas/auth.py` | Strip HTML tags, reject empty after strip |
| CSRF path specificity | `csrf.py` | Exact `/api/v1/ws` match (not prefix) |
| Session refresh atomic | `services/auth.py` | Single `EXPIRE` (no `EXISTS`+`EXPIRE` TOCTOU) |
| Blacklist TTL | `services/auth.py` | 12h min (was hardcoded 8h) |
| Pipeline transactional | `services/auth.py` | `transaction=True` for revoke_user_sessions |

### DM/WebSocket Layer
| Fix | File | Change |
|-----|------|--------|
| Filter deleted/banned | `dm_repo.py` | `is_deleted=false AND is_banned=false` in find_conversations |
| Remove attachment_key | `dm_converter.py` | Internal MinIO path no longer in API response |
| Admin audit logging | `endpoints/dm.py` | `DM_ADMIN_VIEW` event emitted |
| WS atomic limit | `ws.py` | accept() + register inside single lock |
| WS ping close | `ws.py` | Close WebSocket on ping send failure |
| PONG rate exempt | `ws.py` | PONG messages don't consume rate limit |

### Business Logic
| Fix | File | Change |
|-----|------|--------|
| Self-report prevention | `services/report.py` | Check post owner before insert |
| Report status validation | `services/report.py` | Reject non-RESOLVED/DISMISSED |
| Report reason max length | `services/report.py` | 2000 char limit |
| Comment edit rate limit | `endpoints/comments.py` | 30/min per user |

### File/Storage
| Fix | File | Change |
|-----|------|--------|
| PDF extended sanitize | `file_validation.py` | +/Launch, /URI, /SubmitForm, /GoToR, /EmbeddedFiles |
| Thumbnail safer limit | `thumbnail.py` | 10MP (was 20MP) — ~100MB peak vs 256MB limit |
| Album presigned 15min | `album_converter.py` | 900s (was 3600s) + Content-Disposition filename |
| File ownership strict | `services/form.py` | Check user_id at fixed position, not "anywhere" |

### Infrastructure
| Fix | File | Change |
|-----|------|--------|
| Redis disable commands | `redis-prod.conf` | FLUSHALL/FLUSHDB/DEBUG/KEYS renamed/disabled |
| nginx DM rate limit | `default.conf` | `dm` added to write-heavy regex zone |
| DB SSL documented | `.env.production.example` | DATABASE_SSL + REDIS_SSL vars added |
| DB connection lifetime | `database.py` | `max_inactive_connection_lifetime=300` |
| Celery Beat singleton | `docker-compose.prod.yml` | `deploy: replicas: 1` |

### Frontend
| Fix | File | Change |
|-----|------|--------|
| Edit draft user-scoped | `usePostDetail.ts` | Key includes `auth.user?.id` |
| Toast display_name safe | `useWebSocket.ts` | Truncate to 50 chars |
| Error msg filter | `error.ts` | Filter SQL patterns + cap 200 chars |
| MinIO URL env-aware | `useFormExport.ts` | Read `VITE_MINIO_PUBLIC_URL` |
| onSuccess order | `useFormExport.ts` | URL validation before onSuccess callback |

---

## Remaining Unfixed Items
- DM `attachment_key` leaked in API responses
- Admin DM moderation endpoint lacks audit logging
- `RETURNING *` / `SELECT *` in multiple repos
- PDF sanitizer doesn't strip `/Launch`/`/URI`/`/EmbeddedFiles`
- Redis dangerous commands not disabled (`FLUSHALL` etc.)

**P3 (Defense-in-depth LOW):**
- ~49 LOW findings across auth, business logic, DB, WS, frontend, infra
- Mostly TOCTOU races with small windows, missing repo-level validation, and configuration hardening
