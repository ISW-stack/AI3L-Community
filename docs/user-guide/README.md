# AI3L Community Platform — User Guide

Welcome to the AI3L Community platform, an academic exchange hub for AI in Language Learning and Literacy. This guide explains how to use every feature of the platform, organized by user role.

## Role Hierarchy

The platform has four user roles, each inheriting all permissions from the role below it:

| Role | How to Obtain | Summary |
|---|---|---|
| **Guest** | Enter an invite code on the Guest Login page | Temporary read-only session. Can browse content and submit forms. |
| **Member** | Register with an invite code, or apply from a Guest account | Full access to posting, messaging, social features, and collaboration tools. |
| **Admin** | Promoted by a Super Admin | Member privileges plus the Admin Panel for managing users, content, and platform settings. |
| **Super Admin** | Assigned at the system level | Full platform control including audit logs, IP bans, site configuration, and user role management. |

Additionally, **SIG-level roles** (Admin, Sub-Admin, Member) control permissions within individual Special Interest Groups. See the [Member Guide](member-guide.md#sig-roles) for details.

## Guides by Role

Each guide covers the features available to that role. Higher roles should read the guides for all lower roles first.

1. **[Guest Guide](guest-guide.md)** — Browsing, form submission, applying for membership
2. **[Member Guide](member-guide.md)** — Posting, comments, DMs, social features, forms, albums, Q&A, SIG participation, About page
3. **[Admin Guide](admin-guide.md)** — Admin Panel, user management, content moderation, SIG/album creation
4. **[Super Admin Guide](super-admin-guide.md)** — Audit logs, IP bans, site settings, contributor management, role changes

## Quick Reference: Feature Access Matrix

| Feature | Guest | Member | Admin | Super Admin |
|---|---|---|---|---|
| Browse forum / Q&A / SIGs / albums | Yes | Yes | Yes | Yes |
| Submit forms | Yes | Yes | Yes | Yes |
| View notifications | Yes | Yes | Yes | Yes |
| Create posts / comments | — | Yes | Yes | Yes |
| Reactions (emoji) | — | Yes | Yes | Yes |
| Direct messages | — | Yes | Yes | Yes |
| Social (friends / follow / block) | — | Yes | Yes | Yes |
| Create / edit forms | — | Yes | Yes | Yes |
| Upload photos to albums | — | Yes | Yes | Yes |
| Q&A: ask / answer / vote | — | Yes | Yes | Yes |
| About page (intro / org chart / members) | — | Yes | Yes | Yes |
| Generate invite codes | — | Yes | Yes | Yes |
| Create SIGs / albums | — | — | Yes | Yes |
| Admin Panel (dashboard, users, reports) | — | — | Yes | Yes |
| Pin posts | — | — | Yes | Yes |
| Bulk-delete posts | — | — | Yes | Yes |
| Manage categories / invite codes | — | — | Yes | Yes |
| Audit logs | — | — | — | Yes |
| IP ban management | — | — | — | Yes |
| Site settings / contributors | — | — | — | Yes |
| Change user roles / ban users | — | — | — | Yes |

## Platform-Wide Concepts

### Authentication
- The platform uses **HttpOnly cookie-based authentication** with CSRF protection.
- Sessions are maintained automatically; no tokens are visible in the browser.
- Guest sessions are temporary and stored in Redis with an inactivity timeout.

### Real-Time Features (WebSocket)
- **Notifications** update in real time via the bell icon in the navbar.
- **Direct messages** are delivered instantly with read receipts.
- WebSocket connections use a ticket-based system (a short-lived ticket is obtained via REST, then used to open the WebSocket).

### File Uploads and Storage
- Each user has a **1 GB storage quota** for uploaded files.
- Individual file uploads are limited to **50 MB**.
- Uploaded files may undergo **virus scanning** (VirusTotal integration); files pending scan return a 202 status and cannot be downloaded until cleared.
- DM file attachments expire after **3 days**; DM text messages expire after **7 days**.

### Language Support
- The platform supports **17 languages** via the language switcher in the navbar.
- Your language preference is saved to your account and persists across sessions.

### Navigation Bar
The top navigation bar adapts based on your role:

| Element | Visibility |
|---|---|
| Logo (AI3L) → Home | Everyone |
| Forum | Everyone (authenticated) |
| Q&A | Everyone (authenticated) |
| SIGs | Everyone (authenticated) |
| Albums | Everyone (authenticated) |
| Forms | Everyone (authenticated) |
| About (dropdown) | Members and above |
| Admin (dropdown) | Admins and above |
| Messages icon + unread badge | Members and above |
| Notification bell + count | Everyone (authenticated) |
| User menu (profile, friends, logout) | Everyone (authenticated) |
| Language switcher | Everyone |
