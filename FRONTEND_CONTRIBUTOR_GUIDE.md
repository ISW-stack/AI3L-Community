# AI3L Community Frontend -- Contributor Task Guide

> **Last Updated:** 2026-03-03
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

For backend tasks, see `BACKEND_CONTRIBUTOR_GUIDE.md`.

Each item includes a difficulty rating and a step-by-step implementation plan.

### Difficulty Scale

| Label | What it means |
|-------|--------------|
| **Beginner** | 1-3 files, no complex logic, mostly mechanical changes |
| **Intermediate** | 3-6 files, requires understanding state management or API calls |
| **Advanced** | Architectural decisions, multiple subsystems, or complex logic |

---

## Progress Summary

| # | Task | Status |
|---|------|--------|
| 1.1 | Guest membership application form | ✅ Done |
| 1.2 | Admin category management UI | ✅ Done |
| 1.3 | TipTap editor table support | ✅ Done |
| 1.4 | Form response viewing UI | ✅ Done |
| 1.5 | Notification deletion | ✅ Done |
| 1.6 | VirusTotal file safety indicator | ✅ Done |
| 2.1 | Post draft auto-save | ✅ Done |
| 2.2 | Form preview mode | ⬜ Pending |
| 2.3 | SIG search and filter | ✅ Done |
| 2.4 | Password visibility toggle | ✅ Done |
| 2.5 | Invite code generation for members | ✅ Done |
| 2.6 | Admin bulk operations UI | ✅ Done |
| 2.7 | Admin reports pagination | ✅ Done |
| 2.8 | Platform contributors page | ⬜ Pending |
| 3.1 | Post edit SYS_409 version conflict message | ✅ Done |
| 3.2 | FormBuilder rating min/max validation | ✅ Done |
| 4.1 | Keyboard navigation for dropdowns | ⬜ Pending |
| 4.2 | Forum search date range validation | ✅ Done |

---

## Section 1: Required Features Not Yet Implemented

These features are described in the system specification or have a
corresponding backend API endpoint, but no frontend implementation exists.

---

### 1.1 Guest Membership Application Form — ✅ DONE

**Files:** `src/api/users.ts`, `src/views/HomeView.vue`

Done. `applyForMembership()` is implemented in `users.ts` and wired up
in `HomeView.vue`. Guests see a textarea form with a submit button. After
submission, the form is hidden and a confirmation message is shown.

---

### 1.2 Admin Category Management UI — ✅ DONE

**Files:** `src/views/admin/CategoriesView.vue`, `src/api/categories.ts`,
`src/router/index.ts`, `src/components/AppNavbar.vue`

Done. Admins can create, rename, and delete forum categories from
`/admin/categories`. The navbar includes a "Categories" link in the admin
dropdown.

---

### 1.3 TipTap Editor: Table Support — ✅ DONE

**Files:** `src/components/TiptapEditor.vue`, `package.json`

Done. All four TipTap table extensions (`Table`, `TableRow`, `TableHeader`,
`TableCell`) are installed and registered. A toolbar button inserts a 3×3
table with a header row.

---

### 1.4 Form Response Viewing UI — ✅ DONE

**Files:** `src/api/forms.ts`, `src/views/sigs/SigDetailView.vue`

Done. SIG admins can open a modal to view paginated form responses. A
"Download CSV" button triggers the backend Celery export task.

---

### 1.5 Notification Deletion — ✅ DONE

**Files:** `src/api/notifications.ts`, `src/views/NotificationsView.vue`

Done. `deleteNotification()` and `bulkDeleteNotifications()` are
implemented. A trash icon on each notification row deletes it. A
"Clear All" button removes all notifications at once.

---

### 1.6 VirusTotal File Safety Indicator — ✅ DONE

**Files:** `src/api/files.ts`, `src/components/TiptapEditor.vue`,
`src/views/forum/PostDetailView.vue`

Done. Two layers of scan-status feedback are implemented:
- **TiptapEditor:** After upload, polls `getFileScanStatus()` every 5s
  and shows a banner (spinner → green check → red warning).
- **PostDetailView:** On mount, extracts file keys from all
  `/api/v1/files/content/` images in the rendered post, polls each for
  scan status, and overlays a red "Flagged as malicious" badge on any
  image flagged by VirusTotal.

---

## Section 2: Optional Enhancements

These items are not required by the system specification but would improve
the product. They are ordered roughly by impact.

---

### 2.1 Post Draft Auto-Save — ✅ DONE

**File:** `src/views/forum/PostCreateView.vue`

Done. Drafts are saved to `localStorage` with a 2-second debounce. On
mount, the user is prompted to restore any unsaved draft. The draft is
cleared on successful submission or when the user explicitly discards it.
An `onBeforeRouteLeave` guard warns when navigating away with unsaved content.

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

### 2.3 SIG Search and Filter — ✅ DONE

**File:** `src/views/sigs/SigsDirectoryView.vue`

Done. A `BaseInput` at the top of the page filters SIGs client-side by
name and description in real time.

---

### 2.4 Password Visibility Toggle — ✅ DONE

**Files:** `src/views/LoginView.vue`, `src/views/RegisterView.vue`,
`src/views/ProfileView.vue`

Done. All password fields now have a toggle button using `EyeIcon` /
`EyeOffIcon` from `lucide-vue-next`, covering login, registration, and
profile password-change fields.

---

### 2.5 Invite Code Generation for Members — ✅ DONE

**File:** `src/views/ProfileView.vue`

Done. An "Invite Codes" section is visible to all non-guest users in their
profile. A "Generate Invite Code" button calls `createInviteCode()` and
displays the result in a read-only field with a "Copy to Clipboard" button.

---

### 2.6 Admin Bulk Operations UI — ✅ DONE

**Files:** `src/views/admin/UsersView.vue`, `src/views/forum/ForumView.vue`,
`src/api/posts.ts`, `src/api/users.ts`

Done. Admins can select multiple users (with checkbox column) and apply
a bulk role change. Admins can also select multiple forum posts and bulk-
delete them. Both actions include a confirmation modal before executing.

---

### 2.7 Admin Reports Pagination — ✅ DONE

**File:** `src/views/admin/ReportsView.vue`

Done. The reports view uses `currentPage` state, passes `page` and
`page_size` to the API, and displays a `BasePagination` component. Total
report count is shown at the bottom.

---

### 2.8 Platform Contributors Page

**Difficulty: Beginner**

**Affected files:** `src/views/AboutView.vue` (new file), `src/router/index.ts`
(add one route), `src/components/AppNavbar.vue` (add one link)

**Background:**
There is currently no page that acknowledges the people who designed and
built the AI3L Community platform.

**Implementation Plan:**

1. Create `src/views/AboutView.vue`. The page should contain:
   - A heading ("Platform Contributors") and a short paragraph about the project.
   - A contributor list rendered from a local static array.

2. Define the contributor array in the `<script setup>` block:
   ```typescript
   interface Contributor {
     name: string
     role: string
     github?: string
   }
   const contributors: Contributor[] = [
     { name: 'Alice Chen', role: 'Project Lead & Backend', github: 'alicecodes' },
     // Add more contributors here
   ]
   ```

3. In the template, render a responsive grid of cards using CSS variable
   classes (`bg-surface`, `text-foreground`, `border-border`).

4. In `src/router/index.ts`, add:
   ```typescript
   { path: '/about', component: () => import('../views/AboutView.vue') }
   ```

5. In `src/components/AppNavbar.vue`, add an "About" link visible to all
   users (including guests).

---

## Section 3: Known Bugs

---

### 3.1 Post Edit: Version Conflict Error (SYS_409) — ✅ DONE

**File:** `src/views/forum/PostDetailView.vue`

Fixed. The save handler checks for `SYS_409` in the error response and
shows a specific toast: "This post was edited by someone else. Please
reload to see the latest version." A reload option is also available.

---

### 3.2 FormBuilder: Rating Question Allows Invalid Min/Max Values — ✅ DONE

**File:** `src/views/forms/FormBuilderView.vue`

Fixed. An inline error message is shown when `min >= max`, and form
submission is blocked until the values are corrected.

---

## Section 4: UI/UX Improvements

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
   - `ArrowDown`: move focus to the next menu item.
   - `ArrowUp`: move focus to the previous item.
   - `Enter`/`Space`: activate the focused item.
   - `Escape`: close the dropdown and return focus to the trigger button.
4. Add `tabindex="-1"` to each menu item so they can receive programmatic
   focus without appearing in the natural tab order.

---

### 4.2 Forum Search: Date Range Validation — ✅ DONE

**File:** `src/views/forum/ForumView.vue`

Fixed. An inline error message is shown when "Date From" is later than
"Date To", and the search button is disabled until the range is valid.

---

## Backend Dependencies

All previous backend blockers have been resolved. No frontend tasks are
currently blocked by backend work.

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
    ├── admin/     Admin-only views (Categories, Users, Reports, etc.)
    ├── forms/     FormBuilderView, FormView
    ├── forum/     ForumView, PostDetailView, PostCreateView
    └── sigs/      SigDetailView, SigCreateView, SigsDirectoryView
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

Use only CSS variable–based Tailwind classes (`bg-surface`, `text-foreground`,
`border-border`, `text-muted`) instead of hardcoded gray/white classes.
The site uses a fixed light theme (dark mode is not active).

### Running Tests

```bash
# Frontend unit tests (105 tests across 6 files)
cd frontend && npx vitest run

# TypeScript type checking
cd frontend && npx vue-tsc --noEmit

# Prettier check
cd frontend && npx prettier --check src/
```

### Recommended Order for First-Time Contributors

1. Read `src/types/index.ts` and the files it exports. Understanding the
   data models makes everything else easier.
2. Open `src/router/index.ts` to see all pages and their access rules.
3. Pick a **Beginner** item. Open the relevant files and read them fully
   before writing any code.
4. Check your changes work for different user roles (Guest, Member, Admin,
   Super Admin) by logging in with each role type.
5. Run `npx prettier --write src/` and `npx vue-tsc --noEmit` before
   submitting.

### Common Patterns

**Calling the API and handling errors:**
```typescript
const isLoading = ref(false)

const fetchData = async () => {
  isLoading.value = true
  try {
    const res = await someApiFunction()
    data.value = res.data
  } catch {
    toast.show('Failed to load data.', 'error')
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
// Always use BaseModal for destructive action confirmations.
const showDeleteConfirm = ref(false)

const handleDelete = async () => {
  showDeleteConfirm.value = false
  // ... perform delete
}
```
