# Authentication & Authorization — AI3L Community Platform

---

## Roles

| Role | Capabilities |
|---|---|
| `GUEST` | Read forum, submit forms, apply for membership. Session limited to 45 minutes. Blocked from member-only pages (e.g. About). |
| `MEMBER` | Post to forum, create SIGs, generate invite codes. |
| `ADMIN` | Moderate reports, manage applications, ban users, view dashboard. |
| `SUPER_ADMIN` | All of the above plus role assignment, category management, and audit log access. |

Role hierarchy: `GUEST` < `MEMBER` < `ADMIN` < `SUPER_ADMIN`.

---

## Session Flow

1. Client calls `GET /auth/captcha` — receives a base64-encoded CAPTCHA image and a session ID.
2. Client submits credentials and CAPTCHA answer to `POST /auth/login`.
3. Server validates the CAPTCHA, authenticates the user, creates a JWT, stores the token's `jti` (JWT ID) in Redis, and sets two cookies:
   - `access_token` — HttpOnly cookie containing the JWT
   - `csrf_token` — readable cookie the frontend uses to populate `X-CSRF-Token` headers
4. The browser automatically sends `access_token` on all subsequent same-origin requests. The `Authorization: Bearer <token>` header is also accepted as a fallback for non-browser API clients.
5. **Dual validation** — the server validates every request against both the JWT signature *and* the existence of the `jti` in Redis. A valid signature alone is not sufficient if the session has been revoked.
6. Client calls `POST /auth/heartbeat` periodically to extend the Redis session TTL.
7. On logout, the `jti` is added to a Redis blacklist and removed from the active session store. Revocation takes effect immediately.

---

## Token TTLs

| Role | Session Duration |
|---|---|
| `GUEST` | 45 minutes |
| `MEMBER` | 3 hours |
| `ADMIN` | 5 hours |
| `SUPER_ADMIN` | 8 hours |

---

## Guest Sessions

Guest accounts are created via `POST /auth/guest/{invite_code}`. The platform enforces:

- **Concurrent capacity limit**: 30 simultaneous guests by default
- **Per-IP limit**: 3 simultaneous guest sessions per IP per hour

Guests may apply for full membership through `POST /users/apply-member`.

---

## Password Policy

- Minimum 8 characters
- At least one uppercase letter, one lowercase letter, and one digit
- Hashed with **Argon2id** via passlib

---

## CSRF Protection

All state-mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) require a valid CSRF token.

**How it works:**

1. On authentication (login or guest session creation), the server generates a CSRF token and sets it as an `HttpOnly=False` cookie named `csrf_token`.
2. The frontend reads `csrf_token` from the cookie and includes it in the `X-CSRF-Token` request header on every mutating request.
3. The CSRF middleware reads both the cookie value and the header value and rejects the request if they do not match.
4. Safe methods (`GET`, `HEAD`, `OPTIONS`) bypass CSRF checks.

---

## Invite Codes

Members, Admins, and Super Admins can generate single-use invite codes via `POST /auth/invite-code`.

- Each code expires after **7 days**
- Each code can be used **once**: for guest access (`POST /auth/guest/{code}`) or new member registration (`POST /auth/register`)
- Members are limited to **5 active codes** at a time
- Admins can list, soft-revoke, or hard-delete codes via the Admin API
- All revoke and delete actions are written to the audit log

---

## Audit Events

The following actions are written to the `audit_logs` table with actor user ID, IP address, timestamp, and target entity:

`LOGIN` · `LOGOUT` · `PASSWORD_CHANGE` · `ACCOUNT_DELETE` · `ROLE_CHANGE` · `BAN` · `UNBAN` · `INVITE_CODE_REVOKE` · `INVITE_CODE_DELETE`

Accessible only to Super Admins at `GET /admin/audit-logs`.
