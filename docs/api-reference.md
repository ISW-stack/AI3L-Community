# API Reference — AI3L Community Platform

All endpoints are prefixed with `/api/v1/`. Full interactive documentation (Swagger UI) is available at `/api/docs` when `FASTAPI_DEBUG=true`.

---

## Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/captcha` | None | Get CAPTCHA image (base64) and session ID |
| POST | `/auth/login` | None | Authenticate with username, password, and CAPTCHA answer |
| POST | `/auth/register` | None | Create a new member account |
| POST | `/auth/guest/{invite_code}` | None | Create a temporary guest session |
| POST | `/auth/logout` | Required | Terminate the current session |
| POST | `/auth/heartbeat` | Required | Extend the Redis session TTL |
| POST | `/auth/invite-code` | Member+ | Generate an invite code |
| GET | `/auth/invite-code/{code}` | None | Verify invite code validity |
| POST | `/auth/ws-ticket` | Required | Issue a one-time WebSocket authentication ticket (30-second TTL) |

---

## Users

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | Required | Get own profile |
| PUT | `/users/me` | Required | Update own profile |
| PUT | `/users/me/avatar` | Required | Upload avatar image |
| PUT | `/users/me/password` | Required | Change own password |
| POST | `/users/me/consent` | Required | Record privacy policy consent |
| GET | `/users/me/preferences` | Required | Get user preferences (theme, language, notifications) |
| PATCH | `/users/me/preferences` | Required | Update user preferences (partial upsert); includes `dm_friends_only` to restrict DMs to friends only |
| DELETE | `/users/me` | Required | Self-delete account (GDPR Right to Erasure) |
| POST | `/users/apply-member` | Guest | Submit membership application |
| GET | `/users/{user_id}` | Required | Get any user's public profile |
| GET | `/users/{user_id}/avatar` | Required | Get a user's avatar image |
| GET | `/users` | Admin | List all users (paginated) |
| POST | `/users/admin-create` | Admin | Create user account manually |
| PUT | `/users/bulk-role` | Super Admin | Change role for multiple users in one transaction |
| PUT | `/users/{user_id}/role` | Super Admin | Change a single user's role |
| POST | `/users/{user_id}/ban` | Admin | Ban user (terminates all active sessions immediately) |
| POST | `/users/{user_id}/unban` | Admin | Remove ban |
| DELETE | `/users/{user_id}` | Admin | Anonymize user (GDPR Right to Erasure) |

---

## Forum

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/categories` | Required | List all categories |
| GET | `/categories/{id}` | Required | Get a single category |
| POST | `/categories` | Admin | Create a category |
| PUT | `/categories/{id}` | Admin | Update a category |
| DELETE | `/categories/{id}` | Admin | Delete a category |
| GET | `/posts` | Required | List posts (filterable by category, SIG, keyword) |
| POST | `/posts` | Member+ | Create post (50 posts per user per day) |
| POST | `/posts/search` | Required | Full-text search with AND/OR logic and date range (special characters safe) |
| GET | `/posts/trending` | Required | List trending posts |
| DELETE | `/posts/bulk` | Admin | Soft-delete multiple posts in one transaction |
| GET | `/posts/{post_id}` | Required | Get a single post |
| PUT | `/posts/{post_id}` | Owner | Edit post (versioned, version conflict detected) |
| DELETE | `/posts/{post_id}` | Owner/Admin | Soft-delete a post |
| PATCH | `/posts/{post_id}/pin` | Admin | Pin or unpin a post |
| GET | `/posts/{post_id}/history` | Required | Get the post's edit history |
| POST | `/posts/{post_id}/report` | Member+ | Flag post for admin moderation |
| GET | `/posts/{post_id}/comments` | Required | List comments on a post |
| POST | `/posts/{post_id}/comments` | Required | Add a comment |
| PUT | `/posts/{post_id}/comments/{comment_id}` | Owner | Edit a comment |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | Owner/Admin | Delete a comment |
| POST | `/posts/{post_id}/comments/{comment_id}/reaction` | Required | Add or toggle a reaction |

---

## Special Interest Groups (SIGs)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/sigs` | Required | List all SIGs (filterable by name) |
| POST | `/sigs` | Member+ | Create a SIG |
| GET | `/sigs/my` | Required | List SIGs the current user belongs to |
| GET | `/sigs/{sig_id}` | Required | Get SIG detail |
| PUT | `/sigs/{sig_id}` | SIG Admin | Update SIG metadata |
| DELETE | `/sigs/{sig_id}` | Admin | Soft-delete SIG (cascades to SIG posts and forms) |
| GET | `/sigs/{sig_id}/members` | Required | List SIG members |
| POST | `/sigs/{sig_id}/join` | Required | Join a SIG |
| DELETE | `/sigs/{sig_id}/members/me` | Required | Leave a SIG |
| DELETE | `/sigs/{sig_id}/members/{user_id}` | SIG Admin/Admin | Remove a member from a SIG |
| POST | `/sigs/{sig_id}/sub-admin` | SIG Admin | Promote member to sub-admin |
| GET | `/sigs/{sig_id}/posts` | Required | Posts in this SIG |
| GET | `/sigs/{sig_id}/forms` | Required | Forms in this SIG |
| POST | `/sigs/{sig_id}/forms` | SIG Admin | Create a form in this SIG |

---

## Forms

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/forms/{form_id}` | Required | Get form definition and response count |
| PUT | `/forms/{form_id}` | Owner/SIG Admin | Edit form (locked after first response is submitted) |
| DELETE | `/forms/{form_id}` | Owner/SIG Admin | Soft-delete form |
| POST | `/forms/{form_id}/submit` | Required | Submit a response |
| GET | `/forms/{form_id}/responses` | SIG Admin | View all responses (paginated) |
| POST | `/forms/{form_id}/export` | SIG Admin | Start async CSV export (returns a Celery task ID) |
| GET | `/forms/{form_id}/stats` | Owner/SIG Admin | Get form statistics (response count, completion rate, per-question breakdown) |

---

## Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/notifications` | Required | Paginated notification feed |
| PUT | `/notifications/{notif_id}/read` | Required | Mark one notification as read |
| PUT | `/notifications/read-all` | Required | Mark all notifications as read |
| DELETE | `/notifications/{notif_id}` | Required | Delete a single notification |
| DELETE | `/notifications` | Required | Bulk-delete notifications (body: list of IDs; omit to delete all) |

---

## Direct Messages

All DM endpoints require **Member** role or higher. Guests cannot use DMs.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dm/unread-count` | Member+ | Total unread DM count across all conversations |
| GET | `/dm/conversations` | Member+ | List conversations (paginated, ordered by latest message) |
| GET | `/dm/conversations/{user_id}/messages` | Member+ | List messages in the conversation with `user_id` (cursor-paginated) |
| POST | `/dm/conversations/{user_id}/messages` | Member+ | Send a message to `user_id` (multipart/form-data: `content` text + optional `file`) |
| PUT | `/dm/messages/{message_id}` | Member+ | Edit a sent message (within 12-hour window, sender only) |
| DELETE | `/dm/messages/{message_id}` | Member+ | Recall a sent message (within 12-hour window; both parties see "Message recalled") |
| PUT | `/dm/conversations/{user_id}/read` | Member+ | Mark all unread messages in the conversation as read |

### Constraints

- **Self-messaging** is not allowed (`DM_003`).
- **Blocked users** cannot message each other (`DM_001`).
- If the recipient has `dm_friends_only = true`, only friends may send messages (`DM_001`).
- Edit and recall are only available within **12 hours** of sending (`DM_002`).
- Each conversation has a **50,000-character cap**; oldest messages are deleted automatically when the cap is exceeded.
- File attachments: max **1 file per message**, max **50 MB**, counts toward the sender's **1 GB** per-user storage quota. Files expire after **3 days**.
- Message text is retained for **30 days**.
- The `dm_friends_only` preference is toggled via `PATCH /users/me/preferences`.

---

## Files

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/files/upload/editor` | Required | Upload file (PNG, JPEG, PDF, DOCX · max 20 MB) |
| GET | `/files/content/{key}` | Required | Stream file content via backend proxy (stable URL, used for editor-embedded images) |
| GET | `/files/presigned/{key}` | Required | Generate a 7-day presigned download URL (for attachment downloads) |
| GET | `/files/scan-status/{key}` | Required | Poll VirusTotal scan status for an uploaded file (`pending` / `clean` / `malicious`) |

---

## Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/dashboard` | Admin | Platform statistics |
| GET | `/admin/reports` | Admin | Pending post reports |
| PUT | `/admin/reports/{report_id}/review` | Admin | Resolve or dismiss a report |
| GET | `/admin/applications` | Admin | Membership applications |
| PUT | `/admin/applications/{app_id}/review` | Admin | Approve or reject an application |
| GET | `/admin/invite-codes` | Admin | List invite codes (filterable by status) |
| PATCH | `/admin/invite-codes/{id}/revoke` | Admin | Soft-revoke an active invite code |
| DELETE | `/admin/invite-codes/{id}` | Admin | Hard-delete an invite code |
| GET | `/admin/audit-logs` | Super Admin | Paginated audit log |

---

## About

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/about/contributors` | Member+ | List platform contributors (GitHub avatars proxied through the server — no GitHub usernames exposed to the client) |
| GET | `/about/contributors/{id}/avatar` | Member+ | Proxy a contributor's GitHub avatar (1-hour server-side cache) |
| GET | `/about/admin/contributors` | Super Admin | List all contributors with full details (including github_username) |
| POST | `/about/admin/contributors` | Super Admin | Add a new contributor |
| PUT | `/about/admin/contributors/{id}` | Super Admin | Update contributor details |
| DELETE | `/about/admin/contributors/{id}` | Super Admin | Remove a contributor |

---

## Public

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/public/stats` | None | Platform statistics: member count, post count, SIG count (5-minute in-memory cache) |

---

## System

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | PostgreSQL and Redis connectivity check |
| GET | `/tasks/{task_id}/status` | Required | Celery task status (`PENDING`, `SUCCESS`, `FAILURE`) and result |
| WS | `/ws?ticket={ticket}` | Required | Real-time notification stream — see [`websocket.md`](websocket.md) |

---

## Error Response Format

All application errors return a consistent JSON body:

```json
{
  "code": "AUTH_003",
  "message": "Invalid credentials.",
  "status": 401
}
```

The `code` field is a stable string identifier the frontend uses for display logic. Common prefixes: `AUTH_`, `POST_`, `SIG_`, `FORM_`, `FILE_`, `SYS_`.
