# Security Vulnerability Audit Report

> Date: 2026-03-16 | Scope: Full-stack + Infrastructure | Total: 23 vulnerabilities

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **Critical** | 2 | S01, S02 |
| **High** | 5 | S03–S07 |
| **Medium** | 9 | S08–S16 |
| **Low** | 7 | S17–S23 |

---

## Critical Severity

### S01: Super Admin credentials in `.env`

- **Location**: `.env:74-75`
- **CWE**: CWE-798 (Hard-Coded Credentials)
- **Description**: `.env` contains a non-default super admin password (`admin@ai3l.community57289761`). While `.env` is gitignored, if it was ever committed or the filesystem is exposed, the entire application is compromised.
- **Impact**: Full system compromise — ban users, change roles, delete content, access all data.
- **PoC**: Read `.env`, log in as super admin.
- **Suggested fix**: (1) Rotate credentials immediately. (2) Use a secrets manager for production. (3) Audit git history: `git log --all --full-history -- .env`.

### S02: Default JWT Secret Key in use

- **Location**: `backend/app/core/config.py:32`, `.env:32`
- **CWE**: CWE-321 (Hard-Coded Cryptographic Key)
- **Description**: Default `JWT_SECRET_KEY` is `"changeme_jwt_secret_key"` and `.env` uses this exact value. Production startup blocks defaults, but dev/staging environments use the known secret.
- **Impact**: Forge arbitrary JWTs, impersonate any user including SUPER_ADMIN.
- **PoC**: Sign a JWT with `{"sub": "<user_id>", "role": "SUPER_ADMIN"}` using `"changeme_jwt_secret_key"`.
- **Suggested fix**: Generate a cryptographically random JWT secret on first install.

---

## High Severity

### S03: ILIKE wildcard injection in `/users/search`

- **Location**: `backend/app/api/v1/endpoints/users.py:207-219`
- **CWE**: CWE-89 (SQL Injection — wildcard variant)
- **Description**: User query passes into ILIKE as `f"%{q}%"` without escaping `%` / `_` / `\`. Other repos use `_escape_ilike()` but this inline query does not.
- **Impact**: `q=%` enumerates all users; `q=_` matches single-char usernames.
- **Suggested fix**: Apply `_escape_ilike(q)` before building the pattern.

### S04: Album uploads — no file size limit

- **Location**: `backend/app/api/v1/endpoints/albums.py:207-228, 231-255`
- **CWE**: CWE-400 (Uncontrolled Resource Consumption)
- **Description**: `await file.read()` with no size limit. Chunked-encoded requests can bypass nginx `client_max_body_size`.
- **Impact**: Memory exhaustion DoS.
- **Suggested fix**: Read in chunks with a size limit, matching `files.py` pattern.

### S05: Album uploads — no magic number / file type validation

- **Location**: `backend/app/api/v1/endpoints/albums.py:207-228`
- **CWE**: CWE-434 (Unrestricted Upload)
- **Description**: Album photo upload trusts client-supplied Content-Type without magic number validation. Editor uploads use `validate_editor_file()` with magic number checks, but album uploads do not.
- **Impact**: Upload HTML/SVG with embedded scripts → stored XSS when served to other users.
- **Suggested fix**: Apply `validate_magic_number()` before accepting album uploads.

### S06: Missing `Secure` flag on cookies in development

- **Location**: `backend/app/core/config.py:46`, `backend/app/api/v1/endpoints/auth.py:55-76`
- **CWE**: CWE-614 (Sensitive Cookie Without Secure Attribute)
- **Description**: `COOKIE_SECURE` defaults to `False`. Any non-localhost deployment without HTTPS sends JWT cookies over HTTP.
- **Impact**: Session hijacking via network sniffing on staging/pre-production.
- **Suggested fix**: Default to `True`; only allow `False` explicitly in development.

### S07: CSP allows `ws:` (unencrypted WebSocket) in production config

- **Location**: `nginx/snippets/security-headers.conf:13`
- **CWE**: CWE-319 (Cleartext Transmission)
- **Description**: CSP `connect-src` includes `ws:` for Vite HMR in dev, but same config is used in production. Should be `wss:` only in production.
- **Impact**: WebSocket connections can be downgraded to unencrypted, enabling MITM.
- **Suggested fix**: Separate CSP configs for dev and prod.

---

## Medium Severity

### S08: Password hashes in `SELECT *` queries

- **Location**: `backend/app/repositories/user_repo.py:14-16, 35-47, 50-82, 92-100`
- **CWE**: CWE-200 (Exposure of Sensitive Information)
- **Description**: Multiple repo functions use `SELECT * FROM users` or `RETURNING *`, including `password_hash`. Converters should strip them, but carrying hashes through the app increases attack surface.
- **Suggested fix**: Use explicit column lists excluding `password_hash`; dedicated auth query for hash.

### S09: No rate limiting on `/auth/heartbeat`

- **Location**: `backend/app/api/v1/endpoints/auth.py:263-268`
- **CWE**: CWE-799 (Improper Interaction Frequency Control)
- **Description**: Heartbeat refreshes Redis session TTL with no rate limit. Tight-loop scripts create unnecessary Redis load.
- **Suggested fix**: Add rate limit (10 req/min per user).

### S10: No rate limiting on `/auth/ws-ticket`

- **Location**: `backend/app/api/v1/endpoints/auth.py:271-275`
- **CWE**: CWE-799
- **Description**: WS ticket generation stores keys in Redis (30s TTL) with no rate limit. Rapid requests fill Redis.
- **Suggested fix**: Add rate limit (10 req/min per user).

### S11: Public stats endpoint has no rate limiting

- **Location**: `backend/app/api/v1/endpoints/public.py:14-32`
- **CWE**: CWE-799
- **Description**: Unauthenticated, no app-level rate limit. 5-minute cache mitigates but distributed requests can bypass.
- **Suggested fix**: Add IP-based rate limiting.

### S12: MinIO console port exposed on all interfaces

- **Location**: `docker-compose.override.yml:78-79`
- **CWE**: CWE-668 (Exposure of Resource to Wrong Sphere)
- **Description**: MinIO console on port 19001 with default credentials, accessible from any network interface.
- **Suggested fix**: Bind to localhost: `127.0.0.1:19001:9001`.

### S13: PostgreSQL and Redis ports exposed without localhost binding

- **Location**: `docker-compose.override.yml:69-73`
- **CWE**: CWE-668
- **Description**: Ports 15432 (PG) and 16379 (Redis) on all interfaces with weak passwords.
- **Suggested fix**: Bind to `127.0.0.1`.

### S14: Docker socket mounted in Datadog agent

- **Location**: `docker-compose.yml:216`
- **CWE**: CWE-250 (Execution with Unnecessary Privileges)
- **Description**: `/var/run/docker.sock` mounted (read-only) gives visibility into all container env vars including secrets.
- **Suggested fix**: Use alternative Datadog collection methods.

### S15: Reaction helper uses string interpolation for table name

- **Location**: `backend/app/repositories/reaction_helpers.py:24-25, 52-53`
- **CWE**: CWE-89 (SQL Injection — mitigated)
- **Description**: f-string interpolation for `table` parameter, mitigated by `_ALLOWED_TABLES` frozenset allowlist. Pattern is fragile.
- **Suggested fix**: Use dictionary mapping returning full query strings.

### S16: nginx `/assets/` and `/` location blocks strip security headers

- **Location**: `nginx/conf.d/default.conf:87-92`
- **CWE**: CWE-16 (Configuration)
- **Description**: nginx doesn't inherit parent `add_header` directives in child location blocks. `/assets/` and `/` have their own `add_header` without including `security-headers.conf`, silently dropping CSP, X-Frame-Options, etc.
- **Impact**: SPA HTML and static assets served without security headers → XSS via MIME sniffing, clickjacking.
- **Suggested fix**: Include `security-headers.conf` in every location block that uses `add_header`.

---

## Low Severity

### S17: Standalone forms endpoint has no authentication

- **Location**: `backend/app/api/v1/endpoints/forms.py:133-143`
- **CWE**: CWE-306
- **Description**: `GET /forms` is intentionally public but allows unauthenticated form enumeration.

### S18: CSRF token not bound to session

- **Location**: `backend/app/core/csrf.py:66-74`
- **CWE**: CWE-352
- **Description**: Double-submit cookie pattern without cryptographic binding to user's JWT. Subdomain cookie-setting attacks could bypass. `SameSite=lax` provides baseline protection.
- **Suggested fix**: Use signed CSRF token including session JTI.

### S19: No special character requirement in password policy

- **Location**: `backend/app/core/security.py:36-45`
- **CWE**: CWE-521
- **Description**: Requires 8+ chars with upper, lower, digit — but no special characters. `Password1` passes.
- **Suggested fix**: Increase minimum to 12, or add special character requirement, or use zxcvbn.

### S20: PII in log statements

- **Location**: `backend/app/services/auth.py:41`, `backend/app/api/v1/endpoints/auth.py:206`
- **CWE**: CWE-532
- **Description**: Logs include `user_id`, `ip_address`, `display_name`, `invite_code`. If forwarded to external services, PII is exposed.

### S21: `get_optional_current_user` catches all exceptions silently

- **Location**: `backend/app/core/deps.py:66-74`
- **CWE**: CWE-390
- **Description**: Catches `(AppError, Exception)` and returns `None`. Infrastructure errors (DB down, Redis timeout) silently degrade to unauthenticated behavior.
- **Suggested fix**: Only catch `AppError`; let infrastructure exceptions propagate.

### S22: Session allows only one device per role (design consideration)

- **Location**: `backend/app/services/auth.py:31-42`
- **Description**: Same as B01. Logging in elsewhere silently kills other sessions.

### S23: `upgrade-insecure-requests` CSP in development

- **Location**: `nginx/snippets/security-headers.conf:13`
- **CWE**: CWE-16
- **Description**: Tells browsers to upgrade HTTP→HTTPS, which breaks local MinIO URLs in development.
- **Suggested fix**: Separate CSP for dev without `upgrade-insecure-requests`.
