# Admin User Guide

> **Role:** Admin — a platform administrator with access to the Admin Panel and content moderation tools.
>
> Admins have all Member capabilities plus the ability to manage users, review applications and reports, configure categories and invite codes, create SIGs and albums, and moderate content. This guide covers only the **additional** features beyond what Members have. Read the [Member Guide](member-guide.md) first.

---

## Table of Contents

- [Admin Panel Overview](#admin-panel-overview)
- [Dashboard](#dashboard)
- [User Management](#user-management)
- [Membership Applications](#membership-applications)
- [Post Reports](#post-reports)
- [Category Management](#category-management)
- [Invite Code Management](#invite-code-management)
- [Content Moderation](#content-moderation)
- [Creating SIGs](#creating-sigs)
- [Creating Albums](#creating-albums)
- [SIG Administration (Cross-SIG)](#sig-administration-cross-sig)
- [Form Administration (Cross-Form)](#form-administration-cross-form)

---

## Admin Panel Overview

Access the Admin Panel from the **Admin** dropdown in the navbar. The admin area uses a dedicated sidebar layout with links to all admin sub-pages.

Admin pages available to the **Admin** role:

| Page | Path | Purpose |
|---|---|---|
| Dashboard | `/admin` | Overview statistics and quick navigation |
| Users | `/admin/users` | Manage all user accounts |
| Applications | `/admin/applications` | Review guest-to-member applications |
| Reports | `/admin/reports` | Review reported posts |
| Categories | `/admin/categories` | Manage post/question categories |
| Invite Codes | `/admin/invite-codes` | Manage invite codes |

> **Note:** Additional pages (Audit Logs, IP Bans, Site Settings, Contributors) are visible only to Super Admins. See the [Super Admin Guide](super-admin-guide.md).

---

## Dashboard

The dashboard (`/admin`) provides an at-a-glance overview:

**Stat Cards:**
- Total Users
- Total Posts
- Total SIGs
- Total Forms
- Pending Applications (requires attention)
- Pending Reports (requires attention)

**Quick Navigation:** Buttons to jump directly to Users, Applications, Reports, Categories, and Invite Codes.

**Recent Applications:** A preview list of the latest membership applications.

---

## User Management

Navigate to **Admin > Users** (`/admin/users`).

### Browsing Users

- **Search** by username or display name (debounced).
- **Paginated table** with columns: Username, Display Name, Role (color-coded badge), Status (Active/Banned), Join Date, Actions.

### Creating a User Account

1. Click **Create Account**.
2. In the modal, fill in:
   - **Username** (required)
   - **Password** (must meet strength requirements)
   - **Display Name** (required)
   - **Role** — select Member or Guest.
3. Submit.

> **Restriction:** Admins can only create accounts with the Member or Guest role. Only Super Admins can create Admin accounts.

### Bulk Operations

1. Use the **checkboxes** to select multiple users (or "Select All" on the current page).
2. Click **Bulk Change Role**.
3. Select the target role (Member, Admin, or Guest).
4. Confirm. All selected users' roles are updated.

> **Note:** Bulk role changes to Admin require Super Admin privileges.

### Per-User Actions

Each user row has an actions menu:

| Action | Description | Restriction |
|---|---|---|
| **Change Role** | Change the user's platform role | Super Admin only for role changes |
| **Ban** | Suspend the user's account; they cannot log in | Super Admin only |
| **Unban** | Restore a banned user's access | Super Admin only |
| **Delete** | Permanently remove the user account | Super Admin only |

> As an Admin, you can view all users but role changes, bans, and deletions require Super Admin privileges.

---

## Membership Applications

Navigate to **Admin > Applications** (`/admin/applications`).

### Viewing Applications

- **Filter** by status: Pending, Approved, Rejected.
- Each application card shows:
  - Applicant's display name and requested username.
  - Reason for joining (up to 500 characters).
  - Submission date.
  - Current status badge.

### Reviewing Applications

For **Pending** applications:

1. Read the applicant's reason.
2. Click **Approve** to convert the guest session into a full Member account.
3. Or click **Reject** to deny the application.

The applicant sees the updated status on their home dashboard.

---

## Post Reports

Navigate to **Admin > Reports** (`/admin/reports`).

### Viewing Reports

- **Filter** by status (Pending, Reviewed, Dismissed).
- Each report shows:
  - The reporter's name.
  - A link to the reported post.
  - The reason provided by the reporter.
  - Submission date.
  - Status badge.

### Reviewing Reports

1. Click the report to expand details.
2. Click **Review** to open the review interface.
3. You can:
   - Mark as **Reviewed** (take action on the post, such as editing or deleting it).
   - Mark as **Dismissed** (no action needed) with optional notes.
4. To moderate the post itself, navigate to the post and use the Edit or Delete actions (Admins can edit/delete any post).

---

## Category Management

Navigate to **Admin > Categories** (`/admin/categories`).

Categories are used to organize forum posts and Q&A questions.

### Viewing Categories

- A list of all categories with their names and descriptions.

### Creating a Category

1. Click **Create Category**.
2. Enter a **Name** and **Description**.
3. Save.

### Editing a Category

1. Click **Edit** on an existing category.
2. Modify the name or description in the inline modal.
3. Save.

### Deleting a Category

1. Click **Delete** on a category.
2. Confirm in the modal.
3. Posts in this category may need to be reassigned.

---

## Invite Code Management

Navigate to **Admin > Invite Codes** (`/admin/invite-codes`).

### Viewing Invite Codes

- **Filter** by status: Active, Used, Revoked.
- **Paginated table** (50 per page) with columns: Code, Status (badge), Created Date, Used By, Expiry Date, Actions.

### Generating a New Code

1. Click **Generate Code**.
2. A new invite code is created and displayed.
3. Click **Copy** to copy it to your clipboard for sharing.

> Members can also generate invite codes from their Profile > Security tab. The admin view provides oversight of all codes across the platform.

### Managing Codes

| Action | Description |
|---|---|
| **Copy** | Copy the code to clipboard (with visual feedback) |
| **Revoke** | Invalidate the code so it can no longer be used |
| **Delete** | Permanently remove the code record |

---

## Content Moderation

As an Admin, you have elevated permissions across all content:

### Posts

- **Edit any post** — not just your own. Open a post and click Edit.
- **Delete any post** — open a post and click Delete. Confirm in the modal.
- **Pin / Unpin posts** — on the post detail page, click **Pin** to pin the post to the top of the forum, or **Unpin** to remove the pin.
- **Bulk delete posts** — on the forum page (Admin view), select multiple posts and use the bulk delete action.

### Comments

- **Delete any comment** — on a post, click Delete on any comment (not just your own). You cannot edit other users' comments.

### Post Edit History

- **View edit history** of any post, not just your own.

### Files

- **Delete any file** — you can remove files uploaded by other users if needed.
- **View file scan status** — check the virus scanning status of any file.

---

## Creating SIGs

Admins can create new Special Interest Groups.

1. Navigate to **SIGs** and click **Create SIG** (or go directly to `/sigs/create`).
2. Fill in:
   - **Name** (required)
   - **Description** — describe the SIG's purpose.
3. Submit. You become the SIG Admin by default.

### Deleting a SIG

1. Open the SIG detail page.
2. Click **Delete** and confirm.
3. The SIG and all its associations are removed.

---

## Creating Albums

Admins can create new photo albums.

1. Navigate to **Albums** and click **Create Album** (or go directly to `/albums/create`).
2. Fill in:
   - **Album Name** (required)
   - **Description**
   - **Cover Photo** — upload an optional cover image.
3. Submit.

### Managing Albums

As an Admin, you can:
- Edit any album's settings (name, description, cover photo).
- Manage album members (add, approve, remove).
- Delete photos from any album.
- Delete the album entirely.

---

## SIG Administration (Cross-SIG)

Platform Admins automatically have **SIG Admin-level permissions** in all SIGs, regardless of SIG membership. This means you can:

- Edit any SIG's name and description.
- Create forms within any SIG.
- Remove members from any SIG.
- Assign or demote Sub-Admins in any SIG.
- Delete any SIG.

You do not need to join a SIG to manage it.

---

## Form Administration (Cross-Form)

Platform Admins can manage any form on the platform:

- **Edit** any form (questions, metadata, settings).
- **View responses** and **statistics** for any form.
- **Export CSV** from any form.
- **Delete** any form.

This applies to both standalone forms and SIG-scoped forms.
