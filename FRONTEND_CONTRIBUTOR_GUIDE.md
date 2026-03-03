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
| 1.6 | VirusTotal file safety indicator | 🔴 Blocked (backend 4.1) |
| 2.1 | Post draft auto-save | ✅ Done |
| 2.2 | Form preview mode | ⬜ Pending |
| 2.3 | SIG search and filter | ⬜ Pending |
| 2.4 | Password visibility toggle | ⬜ Pending |
| 2.5 | Invite code generation for members | ⬜ Pending |
| 2.6 | Admin bulk operations UI | ✅ Done |
| 2.7 | Admin reports pagination | ✅ Done |
| 2.8 | Platform contributors page | ⬜ Pending |
| 3.1 | Post edit SYS_409 version conflict message | ✅ Done |
| 3.2 | FormBuilder rating min/max validation | ⬜ Pending |
| 4.1 | Keyboard navigation for dropdowns | ⬜ Pending |
| 4.2 | Forum search date range validation | ⬜ Pending |

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

### 1.6 VirusTotal File Safety Indicator

**Difficulty: Advanced**

**Affected files:**
- `src/views/forum/PostDetailView.vue` (show indicator on embedded images)
- `src/components/TiptapEditor.vue` (show upload scan status)

**Status:** 🔴 Blocked — waiting for backend task 4.1 (VirusTotal database
integration and `GET /files/{key}/scan-status` endpoint).

**Implementation Plan (frontend portion — implement after backend is ready):**

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

4. Poll the scan status every 5 seconds until it resolves, then stop.

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

### 2.3 SIG Search and Filter

**Difficulty: Beginner**

**Affected files:** `src/views/sigs/SigsDirectoryView.vue`

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
1. Add an "Invite Codes" section to `ProfileView.vue`, visible to all
   non-guest authenticated users (`v-if="!auth.isGuest"`).
2. Add a "Generate Invite Code" `BaseButton`.
3. On click, call `createInviteCode()` from `src/api/admin.ts`. This
   function already exists.
4. Display the returned code in a read-only `BaseInput` with a "Copy to
   Clipboard" button that calls `navigator.clipboard.writeText(code)`.
5. Show a success toast when the code is generated.

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

### 3.2 FormBuilder: Rating Question Allows Invalid Min/Max Values

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
4. Prevent form submission if any question has a rating error.

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

## Backend Dependencies

Some frontend tasks above are blocked by backend work that has not been
completed yet. See `BACKEND_CONTRIBUTOR_GUIDE.md` for the full list.

| Frontend task | Blocked by (backend) |
|---------------|---------------------|
| 1.6 VirusTotal File Safety Indicator | Backend 4.1 — VirusTotal database integration |

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
