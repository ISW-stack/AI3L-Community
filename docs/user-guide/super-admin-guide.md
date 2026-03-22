# Super Admin User Guide

> **Role:** Super Admin — the highest privilege level with full platform control.
>
> Super Admins have all Admin capabilities plus exclusive access to audit logs, IP ban management, site configuration, contributor management, user role changes, and system health monitoring. This guide covers only the **additional** features beyond what Admins have. Read the [Admin Guide](admin-guide.md) first.

---

## Table of Contents

- [Additional Admin Panel Pages](#additional-admin-panel-pages)
- [Audit Logs](#audit-logs)
- [IP Ban Management](#ip-ban-management)
- [Site Settings](#site-settings)
- [Contributor Management](#contributor-management)
- [User Role Management](#user-role-management)
- [User Ban and Deletion](#user-ban-and-deletion)
- [Org Chart Overrides](#org-chart-overrides)
- [System Health Monitoring](#system-health-monitoring)
- [Additional Capabilities Summary](#additional-capabilities-summary)

---

## Additional Admin Panel Pages

The following Admin Panel pages are exclusively available to Super Admins:

| Page | Path | Purpose |
|---|---|---|
| Audit Logs | `/admin/audit-logs` | Track all administrative actions |
| IP Bans | `/admin/ip-bans` | Block malicious IP addresses |
| Site Settings | `/admin/site-settings` | Configure the About page content |
| Contributors | `/admin/contributors` | Manage the contributor list |

These appear in the Admin sidebar alongside the standard Admin pages.

---

## Audit Logs

Navigate to **Admin > Audit Logs** (`/admin/audit-logs`).

The audit log records all significant administrative actions performed on the platform.

### Viewing Logs

- **Filterable** by:
  - **User ID** — see actions by a specific administrator.
  - **Date from / Date to** — narrow to a specific time range.
- Toggle the filter panel with the filter icon.
- **Paginated table** with columns:
  - **Timestamp** — when the action occurred.
  - **User** — who performed the action.
  - **Action Type** — the category of action (e.g., role change, ban, delete).
  - **Details** — specifics of the action (e.g., which user was affected, what changed).

### What Gets Logged

Audit logs capture events including:
- User role changes
- User bans and unbans
- Account deletions (both self-delete and admin-delete)
- Application approvals and rejections
- IP ban creation and removal
- Invite code generation and revocation
- SIG creation and deletion
- Other administrative actions

---

## IP Ban Management

Navigate to **Admin > IP Bans** (`/admin/ip-bans`).

IP bans prevent specific IP addresses from accessing the platform entirely.

### Viewing Bans

- **Paginated table** with columns: IP Address, Reason, Created Date, Expiry Date, Actions.
- Bans without an expiry date are permanent until manually removed.

### Creating an IP Ban

1. Click **Add IP Ban**.
2. In the modal, fill in:
   - **IP Address** (required) — the IPv4 or IPv6 address to block.
   - **Reason** — why this IP is being banned (for record-keeping).
   - **Expiry Date/Time** (optional) — when the ban should automatically expire. Leave blank for a permanent ban.
3. Submit.

### Removing an IP Ban

1. Click **Delete** on the ban entry.
2. Confirm in the modal.
3. The IP is immediately unblocked.

---

## Site Settings

Navigate to **Admin > Site Settings** (`/admin/site-settings`).

This page controls the content displayed on the **About > Introduction** page visible to all Members.

### Updating the Introduction Photo

1. Click the photo upload area.
2. Select an image file from your device.
3. The photo is uploaded and immediately displayed on the About page.

### Updating the Introduction Text

1. Edit the bio/description text in the text area.
2. Save. The text is displayed below the photo on the About page.

> The introduction photo and bio are saved independently — you can update one without affecting the other.

---

## Contributor Management

Navigate to **Admin > Contributors** (`/admin/contributors`).

Contributors are displayed on the **About > Introduction** page as a grid of cards. This page manages the list.

### Viewing Contributors

- A table showing: GitHub Username, Display Name, Role, Display Order, Actions.
- Unlike the public-facing contributor cards (which hide GitHub usernames), this admin view shows the full GitHub usernames for reference.

### Adding a Contributor

1. Click **Add Contributor**.
2. Fill in:
   - **GitHub Username** — used to fetch the contributor's avatar from GitHub (proxied through the backend for privacy).
   - **Display Name** — the public-facing name shown on the About page.
   - **Role** — their role or title (displayed on the card).
   - **Display Order** — numeric value controlling the sort order on the About page.
3. Save.

### Editing a Contributor

1. Click **Edit** on an existing contributor.
2. Modify any fields in the modal.
3. Save.

### Deleting a Contributor

1. Click **Delete** on a contributor.
2. Confirm in the modal.
3. The contributor is removed from the About page immediately.

---

## User Role Management

Super Admins have exclusive authority to change user roles.

### Changing a Single User's Role

1. Go to **Admin > Users** (`/admin/users`).
2. Find the user and click **Change Role** in their actions menu.
3. Select the new role:
   - **Guest** — temporary, read-only access.
   - **Member** — standard user with full community features.
   - **Admin** — platform administrator (can access Admin Panel).
4. Confirm. The change takes effect immediately.

**Restrictions:**
- You cannot change your own role.
- Only Super Admins can promote users to the Admin role.

### Bulk Role Change

1. On the Users page, select multiple users with checkboxes.
2. Click **Bulk Change Role**.
3. Select the target role.
4. Confirm. All selected users are updated.

### Creating Admin Accounts

When creating a new user account (Admin > Users > Create Account), Super Admins can set the role to **Admin**, which regular Admins cannot do.

---

## User Ban and Deletion

### Banning a User

1. Go to **Admin > Users**.
2. Find the user and click **Ban** in their actions menu.
3. The user's account is immediately suspended:
   - They are logged out of all active sessions.
   - They cannot log back in.
   - Their content remains on the platform but they cannot create new content.

**Restrictions:**
- You cannot ban yourself.
- You cannot ban other Super Admin accounts.

### Unbanning a User

1. Find the banned user (filter by Status = Banned if needed).
2. Click **Unban** in their actions menu.
3. The user can log in again immediately.

### Deleting a User Account

1. Find the user and click **Delete**.
2. Confirm in the modal.
3. The user's account and associated data are permanently removed.

**Restrictions:**
- You cannot delete Super Admin accounts.
- If the user is the sole Admin of any SIG, the deletion is blocked. The SIG admin role must be transferred first.

---

## Org Chart Overrides

Super Admins have additional controls on the **About > Org Chart** page that are not visible to other roles.

### Visibility Control

- Toggle the visibility of SIGs or individual members in the org chart.
- Hidden entries are only visible to Super Admins (shown with a visual indicator).
- Use this to exclude inactive SIGs or members from the public org chart without deleting them.

### Display Order

- Set custom display order values for SIGs and members.
- Controls the sequence in which SIGs and their members appear in the org chart.

### Editing SIG Descriptions

- Super Admins can edit any SIG's description in the org chart, regardless of SIG membership or role.

### Editing Member Bios

- Super Admins can edit any member's bio within the org chart context.

---

## System Health Monitoring

### Full Health Check

- **Endpoint:** `GET /health` (requires Super Admin authentication).
- This is an API endpoint, not a UI page — access it via a browser or API tool (e.g., `curl`) with your session cookie.
- Returns comprehensive system health information including:
  - Database connection status and pool statistics.
  - Redis connection status.
  - MinIO (object storage) status.
  - Celery worker status.
  - Overall system health.

> The public endpoint `GET /health/live` returns only a basic liveness check and requires no authentication.

### Database Pool Statistics

- Available via the health endpoint, showing:
  - Pool size (total connections).
  - Free connections.
  - Connections in use.

---

## Additional Capabilities Summary

Here is a complete list of what Super Admins can do that Admins cannot:

| Capability | Details |
|---|---|
| **View audit logs** | Full history of all administrative actions |
| **Manage IP bans** | Create, view, and remove IP-based access blocks |
| **Edit site settings** | Update the About page introduction photo and text |
| **Manage contributors** | Add, edit, and remove contributor entries on the About page |
| **Change user roles** | Promote/demote users between Guest, Member, and Admin |
| **Ban / unban users** | Suspend and restore user accounts |
| **Delete user accounts** | Permanently remove user accounts |
| **Create Admin accounts** | Set the Admin role when creating new accounts |
| **Org chart overrides** | Control visibility and display order of SIGs/members |
| **Full health endpoint** | Access comprehensive system health diagnostics |
| **View hidden org chart entries** | See entries hidden from other users |
| **Bulk role changes** | Change roles for multiple users at once |

### What Super Admins Cannot Do

Even Super Admins have restrictions to prevent accidental damage:

- Cannot change their own role.
- Cannot ban themselves.
- Cannot delete Super Admin accounts (including their own).
- Cannot bypass file upload size limits or storage quotas.
