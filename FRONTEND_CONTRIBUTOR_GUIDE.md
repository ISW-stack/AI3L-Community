# AI3L Community Frontend -- Contributor Task Guide

> **Last Updated:** 2026-03-02
> **Applies to:** Frontend codebase (`frontend/src/`)
> **Audience:** Collaborators who are new to the project or learning Vue/TypeScript

---

## Introduction

This document catalogues the current state of the AI3L Community frontend
and provides actionable tasks for contributors. It is organized into five
sections:

1. **Required Features** -- Functionality specified in the system design or
   backed by an existing backend API that has no frontend implementation yet.
2. **Optional Enhancements** -- Improvements that are not required by the
   specification but would benefit users.
3. **Known Bugs** -- Confirmed defects that need to be corrected.
4. **UI/UX Improvements** -- Refinements to existing user interface behavior
   and accessibility.
5. **Planned Backend Work** -- Backend tasks that are planned or in progress.
   Frontend contributors should be aware of these as they may affect or
   unblock frontend work.

Each item includes a difficulty rating and a step-by-step implementation plan.

### Difficulty Scale

| Label | What it means |
|-------|--------------|
| **Beginner** | 1-3 files, no complex logic, mostly mechanical changes |
| **Intermediate** | 3-6 files, requires understanding state management or API calls |
| **Advanced** | Architectural decisions, multiple subsystems, or complex logic |

### How to Read This Document

Every item follows this structure:

- **Difficulty** rating
- **Affected files** -- which files to open first
- **Problem/Background** -- why this matters
- **Implementation Plan** -- numbered steps you can follow directly

---

## Section 1: Required Features Not Yet Implemented

These features are described in the system specification or have a
corresponding backend API endpoint, but no frontend implementation exists.

---

### 1.1 Guest Membership Application Form

**Difficulty: Intermediate**

**Affected files:**
- `src/api/users.ts` (add one function)
- `src/views/HomeView.vue` (add UI for guests)

**Background:**
The backend exposes `POST /api/v1/users/apply-member`, which lets a guest
user submit a membership application with a written description. The
`ApplicationsView` admin page already handles reviewing these applications.
However, guests currently have no way to initiate an application from the
frontend. This breaks the core onboarding flow for new users.

**Implementation Plan:**

1. Open `src/api/users.ts`. Add a new exported function at the bottom:
   ```typescript
   export const applyForMembership = (description: string) =>
     api.post('/users/apply-member', { description })
   ```

2. Open `src/views/HomeView.vue`. Locate the block that renders when
   `auth.isGuest` is true. Add a new card or section below the existing
   guest warning message.

3. Inside this new section, add:
   - A short explanation ("Apply for a full membership to access all
     features.")
   - A `BaseTextarea` for the applicant to write their motivation (at least
     50 characters is a reasonable minimum to enforce client-side).
   - A `BaseButton` labelled "Submit Application".

4. Implement the submit handler:
   ```typescript
   const submitApplication = async () => {
     if (description.value.trim().length < 50) {
       // show inline error
       return
     }
     try {
       await applyForMembership(description.value)
       toast.show('Your application has been submitted.', 'success')
       hasApplied.value = true
     } catch (err) {
       toast.show('Failed to submit application. You may have already applied.', 'error')
     }
   }
   ```

5. When `hasApplied` is true, hide the form and show a confirmation message
   so the user cannot submit twice.

---

### 1.2 Admin Category Management UI

**Difficulty: Intermediate**

**Affected files:**
- `src/api/categories.ts` (add three functions)
- `src/views/admin/CategoriesView.vue` (new file)
- `src/router/index.ts` (add one route)
- `src/components/AppNavbar.vue` (add one link)

**Background:**
The backend provides full CRUD for forum categories:
`POST /categories`, `PUT /categories/{id}`, `DELETE /categories/{id}`.
The `GET /categories` endpoint is already used in the forum to populate the
category filter. However, admins have no way to create, rename, or delete
categories from the frontend. This means category management must be done
directly in the database, which is error-prone.

**Implementation Plan:**

1. Open `src/api/categories.ts`. Add three new functions:
   ```typescript
   export const createCategory = (name: string, description: string) =>
     api.post('/categories', { name, description })

   export const updateCategory = (
     id: string,
     payload: { name?: string; description?: string }
   ) => api.put(`/categories/${id}`, payload)

   export const deleteCategory = (id: string) =>
     api.delete(`/categories/${id}`)
   ```

2. Create `src/views/admin/CategoriesView.vue`. This page should:
   - On mount, call the existing `listCategories()` function and display
     results in a `BaseTable` (columns: Name, Description, Actions).
   - Have a "Create Category" `BaseButton` that opens a `BaseModal`
     containing two `BaseInput` fields (Name and Description).
   - Each table row has an "Edit" button (opens the same modal pre-filled)
     and a "Delete" button (shows a confirmation modal).

3. In `src/router/index.ts`, add the route inside the admin routes block:
   ```typescript
   {
     path: '/admin/categories',
     component: () => import('../views/admin/CategoriesView.vue'),
     meta: { requiresAdmin: true }
   }
   ```

4. In `src/components/AppNavbar.vue`, add "Categories" to the admin
   dropdown link list, pointing to `/admin/categories`.

---

### 1.3 TipTap Editor: Table Support

**Difficulty: Intermediate**

**Affected files:**
- `package.json`
- `src/components/TiptapEditor.vue`

**Background:**
The system specification (Section 12.2) lists "table" as a required TipTap
toolbar feature. The current implementation has no table support. TipTap
provides official packages for this.

**Implementation Plan:**

1. Install the required packages (run from the `frontend/` directory):
   ```bash
   npm install @tiptap/extension-table @tiptap/extension-table-row \
               @tiptap/extension-table-header @tiptap/extension-table-cell
   ```

2. In `TiptapEditor.vue`, add imports at the top of the `<script setup>` block:
   ```typescript
   import Table from '@tiptap/extension-table'
   import TableRow from '@tiptap/extension-table-row'
   import TableHeader from '@tiptap/extension-table-header'
   import TableCell from '@tiptap/extension-table-cell'
   ```

3. Register the extensions inside the `useEditor({ extensions: [...] })`
   call:
   ```typescript
   Table.configure({ resizable: true }),
   TableRow,
   TableHeader,
   TableCell,
   ```

4. Add a "Table" button to the toolbar. On click, run:
   ```typescript
   editor.value?.chain().focus()
     .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
     .run()
   ```

5. Optionally add secondary buttons (Add Row, Add Column, Delete Table)
   that appear only when `editor.value?.isActive('table')` is true.

---

### 1.4 Form Response Viewing UI

**Difficulty: Intermediate**

**Affected files:**
- `src/api/forms.ts` (add one function)
- `src/views/sigs/SigDetailView.vue` (add response viewer)

**Background:**
The backend exposes `GET /api/v1/forms/{form_id}/responses` (added in
Phase 13), which returns paginated form submissions. SIG admins need to see
who submitted responses and what they answered. Currently there is no
frontend function calling this endpoint, so admins cannot view form
responses at all.

**Implementation Plan:**

1. Open `src/api/forms.ts`. Add:
   ```typescript
   export const listFormResponses = (
     formId: string,
     page = 1,
     pageSize = 20
   ) =>
     api.get(`/forms/${formId}/responses`, {
       params: { page, page_size: pageSize },
     })
   ```

2. In `SigDetailView.vue`, add a "View Responses" button next to each form
   in the SIG forms section. Show it only when `userIsSigAdmin` is true.

3. When clicked, open a `BaseModal` (size `xl`) that:
   - Fetches responses via `listFormResponses(formId)`.
   - Displays results in a `BaseTable` with columns: Respondent, Submitted
     At, and a summary of their answers.
   - Includes `BasePagination` at the bottom.

4. Optionally add a "Download CSV" button that calls
   `POST /forms/{form_id}/export` (the backend Celery export task).

---

### 1.5 Notification Deletion

**Difficulty: Beginner**

**Affected files:**
- `src/api/notifications.ts` (add one function)
- `src/views/NotificationsView.vue` (add delete button)

**Background:**
The backend exposes `DELETE /api/v1/notifications/{notification_id}`, but
the frontend has no API function for it. Users can mark notifications as
read but cannot delete them. Over time, the notification list grows
unbounded.

**Implementation Plan:**

1. Open `src/api/notifications.ts`. Add:
   ```typescript
   export const deleteNotification = (notificationId: string) =>
     api.delete(`/notifications/${notificationId}`)
   ```

2. In `NotificationsView.vue`, add a delete button (use `TrashIcon` from
   `lucide-vue-next`) on each notification row.

3. Wire the click handler:
   ```typescript
   const handleDelete = async (id: string) => {
     try {
       await deleteNotification(id)
       notifications.value = notifications.value.filter(n => n.id !== id)
     } catch {
       toast.show('Failed to delete notification.', 'error')
     }
   }
   ```

4. The delete button should stop event propagation so it does not trigger
   the row's click-to-navigate behavior.

---

### 1.6 VirusTotal File Safety Indicator

**Difficulty: Advanced**

**Affected files:**
- `src/views/forum/PostDetailView.vue` (show indicator on embedded images)
- `src/components/TiptapEditor.vue` (show upload scan status)

**Background:**
The backend has a VirusTotal integration (`app/tasks/virustotal.py`) that
scans uploaded files asynchronously. However, scan results are currently
fire-and-forget -- they are not stored in the database and there is no way
for the frontend to query whether a file is safe or still being scanned.

> **Note:** This task requires backend changes first. The backend must:
> (1) store scan results in a `file_scans` database table, (2) expose a
> `GET /files/{key}/scan-status` endpoint, (3) block presigned URL
> generation for files flagged as malicious. Once the backend is ready,
> the frontend work can begin.

**Implementation Plan (frontend portion):**

1. Add an API function in `src/api/files.ts`:
   ```typescript
   export const getFileScanStatus = (fileKey: string) =>
     api.get<{ status: 'pending' | 'clean' | 'malicious' }>(`/files/${fileKey}/scan-status`)
   ```

2. In `TiptapEditor.vue`, after a successful upload, show a small badge or
   icon next to the inserted image indicating scan status (spinner for
   pending, green check for clean, red warning for malicious).

3. In `PostDetailView.vue`, for each image in the rendered content, query
   the scan status and overlay an indicator if malicious.

4. Consider polling the scan status every 5 seconds until it resolves
   (pending -> clean/malicious), then stop.

---

## Section 2: Optional Enhancements

These items are not required by the system specification but would improve
the product. They are ordered roughly by impact.

---

### 2.1 Post Draft Auto-Save

**Difficulty: Advanced**

**Affected files:** `src/views/forum/PostCreateView.vue`

When writing a long post, users risk losing their content if the browser
crashes or they accidentally navigate away.

**Implementation Plan:**
1. In `PostCreateView.vue`, use `localStorage` to save the draft. Choose a
   key such as `draft:new-post`.
2. Set up a `watch` on the title, content, category, and keywords. On any
   change (debounced by 2 seconds), save the current form state to
   `localStorage` as a JSON string.
3. On component mount, check if a saved draft exists. If so, prompt the
   user with a modal: "You have an unsaved draft. Restore it?"
4. On successful post submission, delete the draft key from `localStorage`.
5. Add an `onBeforeRouteLeave` guard that warns the user if they try to
   navigate away with unsaved, non-empty content.

---

### 2.2 Form Preview Mode

**Difficulty: Intermediate**

**Affected files:** `src/views/forms/FormBuilderView.vue`

Form builders have no way to preview what respondents will see before
publishing.

**Implementation Plan:**
1. Add a "Preview" `BaseButton` in the form builder toolbar.
2. When clicked, open a `BaseModal` in large (`xl`) size.
3. Inside the modal, render all the current form questions using the same
   question-rendering logic found in `FormView.vue` (the respondent view).
4. The preview should be fully read-only (disable all inputs, hide the
   submit button, or show a "Preview Mode" banner).
5. No API call is needed; all data comes from the component's existing
   reactive state.

---

### 2.3 SIG Search and Filter

**Difficulty: Beginner**

**Affected files:** `src/views/SigsDirectoryView.vue`

`SigsDirectoryView.vue` shows all SIGs in a grid with no search capability.
As the number of SIGs grows, this list becomes hard to navigate.

**Implementation Plan:**
1. Add a `BaseInput` with placeholder "Search SIGs..." at the top of the
   page.
2. Bind its value to a `searchQuery` reactive variable.
3. Add a computed property that filters the SIG list:
   ```typescript
   const filteredSigs = computed(() =>
     sigs.value.filter(sig =>
       sig.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
       sig.description.toLowerCase().includes(searchQuery.value.toLowerCase())
     )
   )
   ```
4. Replace `sigs.value` with `filteredSigs` in the template `v-for`.
5. No backend changes are needed; this is entirely client-side filtering.

---

### 2.4 Password Visibility Toggle

**Difficulty: Beginner**

**Affected files:** `src/views/LoginView.vue`, `src/views/RegisterView.vue`

Password fields have no option to reveal the entered text, which is a
standard UX pattern that reduces login errors.

**Implementation Plan:**
1. For each password field, import `EyeIcon` and `EyeOffIcon` from
   `lucide-vue-next`.
2. Add a `showPassword` boolean `ref` for each field.
3. Change each `<input type="password">` to use a dynamic type binding:
   ```html
   :type="showPassword ? 'text' : 'password'"
   ```
4. Add a button inside the input wrapper that toggles `showPassword`. Use
   the eye icons to indicate the current state.
5. Apply this pattern to all password fields: current password, new
   password, and confirm password.

---

### 2.5 Invite Code Generation for Members

**Difficulty: Beginner**

**Affected files:** `src/views/ProfileView.vue`

The specification states that Members (not just Admins) can generate invite
codes. Currently the only invite code UI is in the Admin panel.

**Implementation Plan:**
1. Add a "Invite Codes" section to `ProfileView.vue`, visible to all
   non-guest authenticated users (`v-if="!auth.isGuest"`).
2. Add a "Generate Invite Code" `BaseButton`.
3. On click, call `createInviteCode()` from `src/api/admin.ts`. This
   function already exists.
4. Display the returned code in a read-only `BaseInput` with a "Copy to
   Clipboard" button that calls `navigator.clipboard.writeText(code)`.
5. Show a success toast when the code is generated.

---

### 2.6 Admin Bulk Operations UI

**Difficulty: Advanced**

**Affected files:**
- `src/api/posts.ts` (add bulk delete function)
- `src/api/users.ts` (add bulk role change function)
- `src/views/admin/UsersView.vue` (add multi-select + bulk actions)
- `src/views/forum/ForumView.vue` (add admin multi-select + bulk delete)

**Background:**
Admins managing a growing platform need to handle policy-violating posts
and role changes efficiently. Currently every action must be done one at a
time, which is impractical at scale.

> **Note:** This task requires backend endpoints to be created first:
> `DELETE /posts/bulk` and `PUT /users/bulk-role`.

**Implementation Plan:**

1. In `UsersView.vue`, add a checkbox column to the user table. Track
   selected user IDs in a `Set<string>`.
2. When one or more users are selected, show a floating action bar with:
   - A role dropdown (MEMBER, ADMIN) and a "Change Role" button.
   - The action calls `bulkChangeRole(userIds, newRole)`.
3. In `ForumView.vue`, add a similar checkbox pattern for admin users.
   Show a "Delete Selected" button when posts are selected.
4. Both actions should show a confirmation modal before executing.

---

### 2.7 Admin Reports Pagination

**Difficulty: Beginner**

**Affected files:** `src/views/admin/ReportsView.vue`

**Background:**
The reports admin view currently loads all reports without pagination. As
the platform grows, this will cause performance issues and potentially
incomplete data if the backend adds a default limit.

**Implementation Plan:**
1. Add `currentPage` reactive state (starts at 1) and use a page size
   constant (e.g., 20).
2. Pass `page` and `page_size` parameters to the reports API call.
3. Store the total count from the response.
4. Add a `BasePagination` component below the reports table.
5. When `currentPage` changes, re-fetch reports.

---

## Section 3: Known Bugs

These are confirmed defects in the current code that must be fixed.

---

### 3.1 BaseInput and BaseTextarea: maxlength Prop Not Applied

**Difficulty: Beginner**
**Files:** `src/components/base/BaseInput.vue`, `src/components/base/BaseTextarea.vue`

**Problem:**
Both components define a `maxlength` prop, but the prop is not bound to the
actual `<input>` or `<textarea>` HTML element. This means that even when a
parent passes `:maxlength="100"`, the user can type unlimited characters.
The prop is silently ignored.

**Fix:**
1. Open `src/components/base/BaseInput.vue`.
2. Find the `<input>` element and add `:maxlength="maxlength"` to its
   attribute list.
3. Repeat for the `<textarea>` in `src/components/base/BaseTextarea.vue`.
4. To verify: add `:maxlength="5"` to any `BaseInput` in the app and
   confirm you cannot type more than 5 characters.

---

### 3.2 relativeTime() Utility Function Is Duplicated

**Difficulty: Beginner**
**Files:** `src/utils/datetime.ts`, `src/views/NotificationsView.vue`

**Problem:**
A `relativeTime()` function is defined in `src/utils/datetime.ts` but is
not used anywhere. Instead, `NotificationsView.vue` contains a local copy of
the same logic (lines 73-84). If the time formatting logic needs to change,
both copies must be updated separately, which is error-prone.

**Fix:**
1. Open `src/views/NotificationsView.vue`.
2. Remove the locally defined `relativeTime` function from the `<script setup>` block.
3. Add the following import at the top of the script block:
   ```typescript
   import { relativeTime } from '../utils/datetime'
   ```
4. Verify that notification timestamps still display correctly in the browser.

---

### 3.3 Forum Post Preview Uses Inconsistent HTML Handling

**Difficulty: Beginner**
**Files:** `src/views/forum/ForumView.vue`

**Problem:**
`PostDetailView.vue` uses DOMPurify to sanitize HTML before rendering post
content, which is the correct approach. However, `ForumView.vue` generates
the post preview text using `stripHtml()` (line 126), which creates a
temporary DOM element and reads `textContent`. While this strips tags, it
does not use DOMPurify and is inconsistent with the rest of the app.

**Fix:**
1. Open `src/views/ForumView.vue`. Find `stripHtml()` (line 126).
2. Import DOMPurify at the top of the script block:
   ```typescript
   import DOMPurify from 'dompurify'
   ```
3. Replace the existing function with:
   ```typescript
   const stripHtml = (html: string): string =>
     DOMPurify.sanitize(html, { ALLOWED_TAGS: [] }).slice(0, 200)
   ```
   This strips all HTML tags (leaving plain text) via the sanitizer and
   then trims to a preview length.

---

### 3.4 Post Edit: Version Conflict Error (SYS_409) Not Explained to the User

**Difficulty: Intermediate**
**Files:** `src/views/forum/PostDetailView.vue`

**Problem:**
The backend uses optimistic locking on post edits. If two users edit the
same post at the same time, the second save will be rejected with error code
`SYS_409`. The frontend currently catches this as a generic error and shows
no specific guidance. The user does not know why the save failed or what to
do next.

**Fix:**
1. In `PostDetailView.vue`'s save handler, check if the error response
   contains the error code `SYS_409`:
   ```typescript
   } catch (err: unknown) {
     const apiError = err as { response?: { data?: { detail?: { code?: string } } } }
     if (apiError.response?.data?.detail?.code === 'SYS_409') {
       toast.show(
         'Someone else edited this post while you were writing. Please reload to see the latest version.',
         'warning'
       )
     } else {
       toast.show('Failed to save post.', 'error')
     }
   }
   ```
2. Optionally, add a "Reload Post" button that fetches the latest version
   of the post from the API and updates the editor content.

---

### 3.5 FormBuilder: Rating Question Allows Invalid Min/Max Values

**Difficulty: Beginner**
**Files:** `src/views/forms/FormBuilderView.vue`

**Problem:**
When building a Rating question, the builder shows numeric inputs for Min
and Max. There is no validation preventing `min >= max` (e.g., min=5, max=1).
This creates a logically broken question that could confuse respondents or
cause backend errors.

**Fix:**
1. Find the rating question edit section in `FormBuilderView.vue`.
2. After either the min or max input changes, add a check:
   ```typescript
   const ratingError = computed(() =>
     question.min >= question.max
       ? 'Minimum must be less than maximum.'
       : ''
   )
   ```
3. Display `ratingError` as an inline error message below the inputs.
4. Prevent form submission if any question has a rating error (add a check
   in the existing `validateForm()` or `serializeForm()` function).

---

### 3.6 Forum Search: Pagination State Not Reset on Mode Change

**Difficulty: Beginner**
**Files:** `src/views/forum/ForumView.vue`

**Problem:**
If the user is browsing page 3 of posts and then submits a search, the
`doSearch()` function (line 77) does not reset `currentPage` to 1. The
search results are requested with the current page number, which may return
an empty page. Note: `clearSearch()` (line 112) correctly resets the page,
and the `watch` handlers for `categoryFilter` and `sortBy` also reset it,
but `doSearch()` does not.

**Fix:**
1. Open `ForumView.vue`.
2. At the top of the `doSearch()` function (line 77), add:
   ```typescript
   currentPage.value = 1
   ```
3. Test by navigating to page 2+, submitting a search, and verifying that
   results start from page 1.

---

## Section 4: UI/UX Improvements

These are refinements to existing behavior.

---

### 4.1 Keyboard Navigation for Dropdown Menus

**Difficulty: Intermediate**
**Files:** `src/components/AppNavbar.vue`, `src/components/NotificationBell.vue`

**Problem:**
The user dropdown and notification bell dropdown cannot be operated by
keyboard. This is a barrier for users who navigate without a mouse.

**Implementation Plan:**
1. On each dropdown trigger button, add a `@keydown` listener.
2. When `ArrowDown` is pressed and the dropdown is closed, open it and
   focus the first menu item.
3. When the dropdown is open:
   - `ArrowDown`: move focus to the next menu item (use `querySelectorAll`
     to find focusable items and track an index).
   - `ArrowUp`: move focus to the previous item.
   - `Enter`/`Space`: activate the focused item.
   - `Escape`: close the dropdown and return focus to the trigger button.
4. Add `tabindex="-1"` to each menu item so they can receive programmatic
   focus without appearing in the natural tab order.

---

### 4.2 Forum Search: Date Range Validation

**Difficulty: Beginner**
**Files:** `src/views/forum/ForumView.vue`

**Problem:**
The forum search form has "Date From" and "Date To" fields. There is no
validation preventing "Date From" from being later than "Date To", which
would produce zero results and confuse users.

**Implementation Plan:**
1. Add a computed property or a watcher:
   ```typescript
   const dateRangeError = computed(() =>
     searchDateFrom.value && searchDateTo.value && searchDateFrom.value > searchDateTo.value
       ? '"Date From" must be before "Date To".'
       : ''
   )
   ```
2. Display `dateRangeError` as an inline error message below the date
   fields.
3. Disable the search button when `dateRangeError` is non-empty.

---

### 4.3 Dark Mode: Hardcoded Colors in Some Views

**Difficulty: Beginner**
**Files:** `src/views/HomeView.vue`, `src/views/forms/FormBuilderView.vue`,
and others

**Problem:**
Phase 13 added CSS custom properties (`--color-foreground`,
`--color-surface`, etc.) and a `dark` class on `<html>` for dark mode
support. However, several views still use hardcoded Tailwind color classes
(e.g., `bg-gradient-to-br from-brand-900 to-brand-700` in HomeView,
hardcoded gray borders in FormBuilderView) that do not respond to the dark
mode toggle.

**Fix:**
1. Search the codebase for hardcoded color classes: `text-gray-`,
   `bg-gray-`, `border-gray-`, `bg-white`, `text-black`, etc.
2. Replace them with the CSS variable equivalents:
   - `text-gray-900` -> `text-foreground`
   - `bg-white` -> `bg-surface`
   - `border-gray-200` -> `border-border`
   - `text-gray-500` -> `text-muted`
3. For gradient backgrounds, use CSS variables inside a custom class or
   switch to a surface-based card design.
4. Test by toggling dark mode and verifying all views look correct.

---

## Section 5: Planned Backend Work

These are backend tasks that are planned or in progress. Frontend
contributors should be aware of them as some will unblock or affect
frontend work. Items marked with **(blocks frontend)** must be completed
before the corresponding frontend task can begin.

---

### 5.1 VirusTotal Integration Completion **(blocks 1.6)**

Store scan results in a database table, expose a
`GET /files/{key}/scan-status` endpoint, and block presigned URL generation
for files flagged as malicious.

### 5.2 Bulk Operations Endpoints **(blocks 2.6)**

Create `DELETE /api/v1/posts/bulk` and `PUT /api/v1/users/bulk-role`
endpoints for admin batch processing.

### 5.3 Reports Endpoint Pagination **(blocks 2.7)**

Add `page` and `page_size` query parameters to `GET /api/v1/reports`.

### 5.4 Cross-Platform Celery Task Compatibility

The `form_export.py` Celery task uses `asyncio.run()` inside a sync worker,
which may fail on Windows or with nested event loops. Will be refactored to
use a proper async/sync bridge that works on all platforms.

### 5.5 Rate Limits via Environment Variables

All rate limit constants (`RATE_LIMIT_COMMENT`, `RATE_LIMIT_CAPTCHA`,
`RATE_LIMIT_FILE_UPLOAD`, `RATE_LIMIT_FORM_SUBMIT`, etc.) will be moved
from hardcoded values in `constants.py` to environment variables with
fallback defaults. This allows different limits per deployment environment.

### 5.6 Event Bus Retry Mechanism

Failed events currently persist in Redis but are never retried. A bounded
retry mechanism will be added (e.g., max 3 retries with exponential
backoff), with failed events logged and eventually discarded to prevent
unbounded resource usage.

### 5.7 Data Integrity Improvements

- SIG deletion will cascade to associated forms and posts (soft-delete or
  nullify `sig_id`).
- Category deletion will nullify `category_id` on associated posts.
- SIG leave will validate at least one non-deleted admin remains.

### 5.8 Schema Validation Hardening

- Add `max_length` constraints to `placeholder`, `bio`, `affiliation`,
  `orcid` fields in Pydantic schemas.
- Add per-item length validation to post `keywords` array.
- Fix `notification page_size` to require `ge=1` instead of `ge=0`.

### 5.9 Error Handling Fixes

- Fix `create_post()` ValueError being mapped to HTTP 429 (should be 400).
- Replace generic `except Exception` catches in `sigs.py` join and
  `files.py` VirusTotal with specific exception types.
- Replace `assert file.content_type` in avatar upload with proper
  validation.

### 5.10 Audit Log Date Filtering

Add `date_from` and `date_to` optional parameters to the audit log listing
endpoint so admins can query logs for specific time periods.

### 5.11 WebSocket Resilience

- Reset guest WebSocket timeout on activity (currently absolute 45 min).
- Add error recovery with exponential backoff reconnection to the Redis
  Pub/Sub subscriber.

---

## Appendix: Getting Started

### Key Directories

```
frontend/src/
├── api/           HTTP request functions (one file per domain area)
├── components/    Reusable Vue components; base/ is the design system
│   └── __tests__/ Component unit tests (Vitest + @vue/test-utils)
├── composables/   Vue composables (api.ts, useWebSocket.ts)
│   └── __tests__/ Composable unit tests
├── router/        Route definitions and navigation guards (index.ts)
├── stores/        Pinia global state (auth.ts, notifications.ts, toast.ts)
│   └── __tests__/ Store unit tests
├── types/         TypeScript interfaces for all data models
├── utils/         Utility functions (datetime, html including renderMentions)
└── views/         One file per page/route
    └── sigs/      Includes SigCreateView.vue (added Phase 13)
```

### Design System Rules

Always use the base components in `src/components/base/` instead of raw
HTML elements:

| Do not use | Use instead |
|-----------|------------|
| `<button>` | `<BaseButton>` |
| `<input>` | `<BaseInput>` |
| `<textarea>` | `<BaseTextarea>` |
| `<select>` | `<BaseSelect>` |
| `<dialog>` / custom overlay | `<BaseModal>` |
| `<table>` | `<BaseTable>` |

### Running Tests

```bash
# Frontend unit tests (105 tests across 6 files)
cd frontend && npx vitest run

# TypeScript type checking
cd frontend && npx tsc --noEmit

# Lint
cd frontend && npm run lint
```

### Recommended Order for First-Time Contributors

1. Read `src/types/index.ts` and the files it exports. Understanding the
   data models makes everything else easier.
2. Open `src/router/index.ts` to see all pages and their access rules.
3. Pick a **Beginner** item. Open the relevant files and read them fully
   before writing any code.
4. Check your changes work for different user roles (Guest, Member, Admin,
   Super Admin) by logging in with each role type.
5. Run the linter before submitting: `npm run lint` inside `frontend/`.

### Common Patterns

**Calling the API and handling errors:**
```typescript
const isLoading = ref(false)
const error = ref('')

const fetchData = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const res = await someApiFunction()
    data.value = res.data
  } catch (err: unknown) {
    error.value = (err as Error).message || 'Failed to load data.'
  } finally {
    isLoading.value = false
  }
}
```

**Showing a toast notification:**
```typescript
import { useToastStore } from '../stores/toast'
const toast = useToastStore()
toast.show('Action completed.', 'success') // types: success, error, warning, info
```

**Checking the current user's role:**
```typescript
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()

auth.isAuthenticated // boolean
auth.isAdmin        // boolean (true for ADMIN and SUPER_ADMIN)
auth.isSuperAdmin   // boolean
auth.isGuest        // boolean
auth.user           // UserProfile object or null
```

**Using confirmation modals (not browser confirm()):**
```typescript
// Phase 13 replaced all confirm() calls with BaseModal dialogs.
// Always use BaseModal for destructive action confirmations.
const showDeleteConfirm = ref(false)

const handleDelete = async () => {
  showDeleteConfirm.value = false
  // ... perform delete
}
```
