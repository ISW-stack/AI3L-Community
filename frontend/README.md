# Frontend — AI3L Community Platform

This document covers the frontend application architecture, design system, development workflow, and conventions for the AI3L Community Platform. The frontend is a Vue 3 single-page application built with TypeScript and Vite.

---

## Table of Contents

- [Technology Stack](#technology-stack)
- [Directory Structure](#directory-structure)
- [Development Setup](#development-setup)
- [Available Scripts](#available-scripts)
- [Design System](#design-system)
  - [Color Tokens](#color-tokens)
  - [Typography](#typography)
  - [Base Component Library](#base-component-library)
- [Application Architecture](#application-architecture)
  - [Routing](#routing)
  - [State Management](#state-management)
  - [API Layer](#api-layer)
  - [Composables](#composables)
  - [Types](#types)
  - [Utilities](#utilities)
- [Views Reference](#views-reference)
- [Real-Time WebSocket](#real-time-websocket)
- [Code Style](#code-style)
- [Adding a New Page](#adding-a-new-page)
- [Adding a New API Module](#adding-a-new-api-module)
- [Environment Variables](#environment-variables)

---

## Technology Stack

| Purpose           | Technology                                       |
| ----------------- | ------------------------------------------------ |
| Framework         | Vue 3 (Composition API with `<script setup>`)    |
| Language          | TypeScript 5.7                                   |
| Build tool        | Vite 6                                           |
| CSS framework     | Tailwind CSS v4 (via `@tailwindcss/vite` plugin) |
| State management  | Pinia 2                                          |
| Routing           | Vue Router 4                                     |
| HTTP client       | Axios                                            |
| Rich text editor  | TipTap 3                                         |
| HTML sanitization | DOMPurify                                        |
| Icon library      | Lucide Vue Next                                  |
| Font              | Inter Variable (`@fontsource-variable/inter`)    |
| Internationalization | vue-i18n 11 (17 languages)                    |
| Unit tests        | Vitest 4                                         |
| End-to-end tests  | Playwright                                       |
| Formatter         | Prettier 3                                       |
| Linter            | ESLint 9 (flat config)                           |
| Type checker      | vue-tsc                                          |

---

## Directory Structure

```
frontend/src/
├── api/                 Axios API call modules (one file per domain)
│   ├── index.ts         Axios instance and interceptors
│   ├── auth.ts
│   ├── users.ts
│   ├── posts.ts
│   ├── comments.ts
│   ├── categories.ts
│   ├── contributors.ts
│   ├── sigs.ts
│   ├── forms.ts
│   ├── files.ts
│   ├── notifications.ts
│   ├── reports.ts
│   ├── tasks.ts
│   └── admin.ts
├── components/
│   ├── base/            Design system base components
│   │   ├── BaseAlert.vue
│   │   ├── BaseAvatar.vue
│   │   ├── BaseBadge.vue
│   │   ├── BaseBreadcrumb.vue
│   │   ├── BaseButton.vue
│   │   ├── BaseCard.vue
│   │   ├── BaseInput.vue
│   │   ├── BaseModal.vue
│   │   ├── BasePagination.vue
│   │   ├── BaseSelect.vue
│   │   ├── BaseTable.vue
│   │   └── BaseTextarea.vue
│   ├── AppNavbar.vue    Top navigation bar
│   ├── NotificationBell.vue
│   ├── ToastNotification.vue
│   ├── TiptapEditor.vue Rich text editor wrapper
│   ├── SkeletonLoader.vue
│   ├── EmptyState.vue
│   └── PrivacyConsentModal.vue
├── composables/
│   ├── api.ts              Axios instance factory
│   ├── useWebSocket.ts     WebSocket connection composable
│   ├── usePagination.ts    Shared pagination state composable
│   ├── usePostDetail.ts    Post detail business logic composable
│   └── useLocale.ts        Language preference composable
├── constants.ts         Application-wide constants
├── main.ts              App entry point
├── App.vue              Root component (layout, transitions)
├── router/              Vue Router configuration and guards
├── stores/
│   ├── auth.ts          Authentication state (Pinia)
│   ├── notifications.ts Notification state (Pinia)
│   └── toast.ts         Toast message queue (Pinia)
├── style.css            Global styles and design tokens (@theme)
├── types/               TypeScript type definitions
│   ├── index.ts         Re-exports all types
│   ├── user.ts
│   ├── post.ts
│   ├── comment.ts
│   ├── sig.ts
│   ├── form.ts
│   ├── notification.ts
│   └── common.ts
├── locales/             vue-i18n translation files (one per language)
│   ├── en.ts
│   ├── zhCN.ts
│   ├── zhTW.ts
│   ├── ar.ts
│   ├── de.ts
│   ├── es.ts
│   ├── fr.ts
│   ├── hi.ts
│   ├── id.ts
│   ├── it.ts
│   ├── ja.ts
│   ├── ko.ts
│   ├── pt.ts
│   ├── ru.ts
│   ├── tr.ts
│   ├── vi.ts
│   ├── nan.ts           Taiwanese Hokkien (Hàn-lô mixed script)
│   └── index.ts         vue-i18n instance configuration
├── utils/
│   ├── datetime.ts      Date formatting helpers
│   ├── error.ts         getErrorMessage() — typed API error extraction
│   └── html.ts          HTML sanitization helpers
└── views/
    ├── HomeView.vue
    ├── LoginView.vue
    ├── RegisterView.vue
    ├── GuestLoginView.vue
    ├── NotFoundView.vue
    ├── NotificationsView.vue
    ├── ProfileView.vue
    ├── UserProfileView.vue
    ├── AboutView.vue
    ├── forum/
    │   ├── ForumView.vue
    │   ├── PostDetailView.vue
    │   └── PostCreateView.vue
    ├── sigs/
    │   ├── SigsDirectoryView.vue
    │   ├── SigLayout.vue         Parent layout — provides sig + userSigRole via inject
    │   ├── SigPostsView.vue      Nested route: SIG discussion feed
    │   ├── SigMembersView.vue    Nested route: SIG member roster
    │   ├── SigFormsView.vue      Nested route: SIG forms list
    │   └── SigCreateView.vue
    ├── forms/
    │   ├── FormView.vue
    │   └── FormBuilderView.vue
    └── admin/
        ├── AdminDashboardView.vue
        ├── UsersView.vue
        ├── ApplicationsView.vue
        ├── ReportsView.vue
        ├── AuditLogsView.vue
        └── InviteCodesView.vue
```

---

## Development Setup

### Prerequisites

- Node.js 22 or later
- npm 10 or later

### Install dependencies

```bash
cd frontend
npm install
```

### Start development server

The recommended workflow runs everything — including the Vite dev server — inside Docker via `docker-compose.override.yml`. A single command from the repository root starts all services:

```bash
# From the repository root
docker compose up --build   # first time (builds images)
docker compose up           # subsequent runs
```

The Vite dev server runs on internal port 3210 and is exposed through Nginx at **http://localhost:3000**. Edits to `frontend/src/` trigger Hot Module Replacement (HMR) instantly — no rebuild needed. All `/api` requests are proxied to FastAPI.

To run the frontend dev server outside Docker (e.g. for a faster iteration cycle on host):

```bash
# Start infrastructure services first
docker compose up -d postgres redis minio fastapi

# Then in a separate terminal
cd frontend
npm install
npm run dev   # accessible at http://localhost:15173
```

---

## Available Scripts

| Command                     | Description                                                                                  |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| `npm run dev`               | Start Vite development server with HMR on port 15173 (host-only; normally handled by Docker) |
| `npm run build`             | Type-check and produce a production build in `dist/`                                         |
| `npm run preview`           | Serve the `dist/` build locally                                                              |
| `npm run test:unit`         | Run Vitest unit tests                                                                        |
| `npm run test:e2e`          | Run Playwright end-to-end tests                                                              |
| `npm run lint`              | Run ESLint with auto-fix                                                                     |
| `npm run format`            | Run Prettier with auto-fix on `src/`                                                         |
| `npx vue-tsc --noEmit`      | Type-check without emitting output                                                           |
| `npx prettier --check src/` | Check Prettier formatting without writing                                                    |
| `npx eslint .`              | Run ESLint without auto-fix                                                                  |

---

## Design System

The design system is defined entirely in `src/style.css` using Tailwind CSS v4's `@theme` block. This generates CSS custom properties and Tailwind utility classes from a single source of truth.

### Color Tokens

All colors are defined as semantic tokens. Never use raw Tailwind color utilities (`text-blue-600`, `bg-gray-100`) in application code. Use semantic tokens instead.

#### Brand (Oxford Blue)

| Token                           | Value     | Usage                               |
| ------------------------------- | --------- | ----------------------------------- |
| `brand-50`                      | `#e6eef8` | Light backgrounds, hover states     |
| `brand-100`                     | `#ccddf1` | Active states, badges               |
| `brand-200`                     | `#99bbe3` | Borders, secondary accents          |
| `brand-300` through `brand-500` | —         | Intermediate shades                 |
| `brand-600`                     | `#004a8c` | Primary interactive elements, links |
| `brand-700`                     | `#003d75` | Hover on primary elements           |
| `brand-900`                     | `#002147` | Hero backgrounds, brand identity    |

#### Semantic Status Colors

| Prefix      | Use case                      |
| ----------- | ----------------------------- |
| `success-*` | Positive outcomes, approvals  |
| `warning-*` | Caution states, pending items |
| `danger-*`  | Errors, destructive actions   |
| `info-*`    | Neutral information           |

Each status color has a `50` (light background) and `600` (text/icon) variant.

#### Surface and Text Tokens

| Token         | Description                                    |
| ------------- | ---------------------------------------------- |
| `surface`     | Card and panel backgrounds (`#ffffff`)         |
| `surface-alt` | Page backgrounds, table headers (`#f9fafb`)    |
| `border`      | All borders and dividers (`#e5e7eb`)           |
| `muted`       | Subdued text, labels, placeholders (`#6b7280`) |
| `foreground`  | Primary body text (`#111827`)                  |

#### Usage examples

```html
<!-- Correct -->
<p class="text-foreground">Primary text</p>
<p class="text-muted">Secondary label</p>
<div class="bg-surface border border-border rounded-lg">Card</div>
<span class="text-brand-600 hover:text-brand-700">Link</span>

<!-- Incorrect — do not use raw Tailwind colors -->
<p class="text-gray-900">Primary text</p>
<div class="bg-white border border-gray-200">Card</div>
<span class="text-blue-600">Link</span>
```

### Typography

The application uses Inter Variable, loaded locally via `@fontsource-variable/inter`. This avoids external network requests, which is important for users in regions where Google Fonts may be unreliable.

The font is imported once in `src/main.ts`:

```typescript
import '@fontsource-variable/inter'
```

It is then set as the default sans-serif font in `src/style.css`:

```css
@theme {
  --font-sans: 'Inter Variable', ui-sans-serif, system-ui, sans-serif;
}
```

No serif fonts are used in this project.

### Base Component Library

Twelve reusable base components are defined in `src/components/base/`. All application views and feature components should be built exclusively from these primitives rather than writing one-off Tailwind class combinations.

---

#### BaseButton

**Props:**

| Prop       | Type                                                                                              | Default     | Description                       |
| ---------- | ------------------------------------------------------------------------------------------------- | ----------- | --------------------------------- |
| `variant`  | `'primary' \| 'secondary' \| 'danger' \| 'success' \| 'ghost' \| 'soft-danger' \| 'soft-success'` | `'primary'` | Visual style                      |
| `size`     | `'sm' \| 'md' \| 'lg' \| 'full'`                                                                  | `'md'`      | Button size                       |
| `loading`  | `boolean`                                                                                         | `false`     | Shows spinner and disables button |
| `disabled` | `boolean`                                                                                         | `false`     | Disables button                   |
| `type`     | `'button' \| 'submit' \| 'reset'`                                                                 | `'button'`  | HTML button type                  |

```html
<BaseButton variant="primary" @click="save">Save</BaseButton>
<BaseButton variant="danger" :loading="deleting" @click="delete">Delete</BaseButton>
<BaseButton variant="secondary" size="sm">Cancel</BaseButton>
```

---

#### BaseInput

**Props:**

| Prop          | Type      | Default  | Description              |
| ------------- | --------- | -------- | ------------------------ |
| `modelValue`  | `string`  | —        | `v-model` binding        |
| `label`       | `string`  | —        | Field label              |
| `type`        | `string`  | `'text'` | Input type               |
| `placeholder` | `string`  | —        | Placeholder text         |
| `error`       | `string`  | —        | Validation error message |
| `disabled`    | `boolean` | `false`  | Disables the input       |

```html
<BaseInput v-model="username" label="Username" placeholder="your_username" />
<BaseInput v-model="email" label="Email" type="email" :error="emailError" />
```

---

#### BaseTextarea

**Props:**

| Prop          | Type     | Default | Description              |
| ------------- | -------- | ------- | ------------------------ |
| `modelValue`  | `string` | —       | `v-model` binding        |
| `label`       | `string` | —       | Field label              |
| `rows`        | `number` | `4`     | Number of visible rows   |
| `placeholder` | `string` | —       | Placeholder text         |
| `error`       | `string` | —       | Validation error message |

---

#### BaseSelect

**Props:**

| Prop          | Type                                                | Default | Description             |
| ------------- | --------------------------------------------------- | ------- | ----------------------- |
| `modelValue`  | `string \| number \| null`                          | —       | `v-model` binding       |
| `label`       | `string`                                            | —       | Field label             |
| `options`     | `Array<{ value: string \| number, label: string }>` | `[]`    | Select options          |
| `placeholder` | `string`                                            | —       | Placeholder option text |

---

#### BaseCard

**Props:**

| Prop        | Type                             | Default | Description                        |
| ----------- | -------------------------------- | ------- | ---------------------------------- |
| `padding`   | `'none' \| 'sm' \| 'md' \| 'lg'` | `'md'`  | Internal padding size              |
| `hoverable` | `boolean`                        | `false` | Adds hover shadow and scale effect |

```html
<BaseCard padding="lg">
  <h2>Title</h2>
  <p>Content</p>
</BaseCard>

<BaseCard hoverable>
  <router-link to="/post/123">Clickable card</router-link>
</BaseCard>
```

---

#### BaseAlert

**Props:**

| Prop          | Type                                          | Default  | Description            |
| ------------- | --------------------------------------------- | -------- | ---------------------- |
| `type`        | `'error' \| 'success' \| 'warning' \| 'info'` | `'info'` | Alert severity         |
| `dismissible` | `boolean`                                     | `false`  | Shows a dismiss button |

Renders with `role="alert"` for screen reader accessibility.

```html
<BaseAlert v-if="error" type="error">{{ error }}</BaseAlert>
<BaseAlert v-if="success" type="success" dismissible>Saved successfully.</BaseAlert>
```

---

#### BaseBadge

**Props:**

| Prop      | Type                                                                                 | Default   | Description   |
| --------- | ------------------------------------------------------------------------------------ | --------- | ------------- |
| `variant` | `'brand' \| 'success' \| 'warning' \| 'danger' \| 'neutral' \| 'orange' \| 'purple'` | `'brand'` | Color variant |
| `size`    | `'sm' \| 'md'`                                                                       | `'sm'`    | Badge size    |

```html
<BaseBadge variant="success">Active</BaseBadge>
<BaseBadge variant="danger">Closed</BaseBadge>
<BaseBadge variant="warning">Pending</BaseBadge>
```

---

#### BaseModal

**Props:**

| Prop         | Type                           | Default | Description                               |
| ------------ | ------------------------------ | ------- | ----------------------------------------- |
| `modelValue` | `boolean`                      | —       | `v-model` open/closed state               |
| `title`      | `string`                       | —       | Modal header title                        |
| `size`       | `'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'`  | Modal width                               |
| `persistent` | `boolean`                      | `false` | Prevents closing by clicking the backdrop |

**Slots:** `default` (body content), `footer` (action buttons)

Uses `<Teleport to="body">`. Includes focus trapping, Escape key close, and body scroll lock. Sets `role="dialog"` and `aria-modal="true"`.

```html
<BaseModal v-model="showModal" title="Confirm Delete" size="sm">
  <p>Are you sure you want to delete this item?</p>
  <template #footer>
    <BaseButton variant="secondary" @click="showModal = false">Cancel</BaseButton>
    <BaseButton variant="danger" @click="confirmDelete">Delete</BaseButton>
  </template>
</BaseModal>
```

---

#### BaseTable

**Props:**

| Prop      | Type                                    | Default | Description         |
| --------- | --------------------------------------- | ------- | ------------------- |
| `columns` | `Array<{ key: string, label: string }>` | —       | Column definitions  |
| `rows`    | `Array<Record<string, unknown>>`        | —       | Row data            |
| `loading` | `boolean`                               | `false` | Shows loading state |

Wraps in `overflow-x-auto` with `min-w-[600px]` on the table for mobile compatibility. Supports scoped slot `#[key]="{ row }"` for custom cell rendering.

---

#### BasePagination

**Props:**

| Prop          | Type     | Default | Description                            |
| ------------- | -------- | ------- | -------------------------------------- |
| `currentPage` | `number` | —       | Active page number (1-based)           |
| `totalPages`  | `number` | —       | Total number of pages                  |
| `maxVisible`  | `number` | `7`     | Maximum number of page buttons to show |

**Emits:** `update:currentPage` (number)

```html
<BasePagination
  :current-page="page"
  :total-pages="totalPages"
  @update:current-page="(p) => { page = p; fetchData() }"
/>
```

---

## Application Architecture

### Routing

Routes are defined in `src/router/`. Navigation guards enforce authentication and role requirements before allowing access to protected routes. The router uses `createWebHistory`.

All page components are lazy-loaded with dynamic imports to split the bundle per-route.

### State Management

Pinia stores are in `src/stores/`. There are three stores.

#### `useAuthStore` (`stores/auth.ts`)

Manages authentication state for the current session.

| State             | Type           | Description                           |
| ----------------- | -------------- | ------------------------------------- |
| `user`            | `User \| null` | Current user profile                  |
| `isAuthenticated` | `boolean`      | Derived: user is non-null             |
| `isGuest`         | `boolean`      | Derived: user role is GUEST           |
| `isAdmin`         | `boolean`      | Derived: role is ADMIN or SUPER_ADMIN |
| `isSuperAdmin`    | `boolean`      | Derived: role is SUPER_ADMIN          |

The JWT itself is stored in an HttpOnly cookie set by the server and is not accessible from JavaScript. The store does not hold a token string.

Key actions: `login`, `logout`, `clearSession`, `fetchCurrentUser`.

#### `useNotificationsStore` (`stores/notifications.ts`)

Manages the notification count badge on the navbar.

#### `useToastStore` (`stores/toast.ts`)

Manages the toast notification queue.

| Action | Parameters                                                              | Description                                      |
| ------ | ----------------------------------------------------------------------- | ------------------------------------------------ |
| `show` | `(message: string, type?: 'success' \| 'error' \| 'info' \| 'warning')` | Adds a toast that auto-dismisses after 4 seconds |

```typescript
const toast = useToastStore()
toast.show('Profile saved.', 'success')
toast.show('Failed to load data.', 'error')
```

### API Layer

All API calls are in `src/api/`. Each file exports typed async functions that wrap Axios. No component or store should call Axios directly.

`src/api/index.ts` exports the configured Axios instance with:

- `baseURL: '/api/v1'`
- `withCredentials: true` — the browser automatically sends the HttpOnly `access_token` cookie on all same-origin requests
- Request interceptor: reads the readable `csrf_token` cookie and attaches its value as the `X-CSRF-Token` header on all mutating requests
- Response interceptor: redirects to `/login` on 401 responses (expired or invalid session)

Example API module pattern:

```typescript
// src/api/posts.ts
import api from './index'
import type { Post, PostCreate, PaginatedPosts } from '@/types'

export async function createPost(payload: PostCreate): Promise<Post> {
  const { data } = await api.post<Post>('/posts', payload)
  return data
}

export async function listPosts(params: {
  page?: number
  category_id?: string
}): Promise<PaginatedPosts> {
  const { data } = await api.get<PaginatedPosts>('/posts', { params })
  return data
}
```

### Composables

#### `useWebSocket` (`composables/useWebSocket.ts`)

Manages the WebSocket connection to `/api/v1/ws`. Handles:

- Connection lifecycle (connect on mount, disconnect on unmount)
- Automatic reconnection with exponential backoff
- PING/PONG heartbeat protocol
- Dispatching incoming messages to the notification store
- Handling `FORCE_LOGOUT` messages by clearing the session and redirecting

#### `usePagination` (`composables/usePagination.ts`)

Shared pagination state used across list views. Call with a `pageSize` argument; returns `{ page, total, totalPages, setPage, resetPage, updateFromResponse }`. `updateFromResponse` accepts a paginated API response and updates `total` and `totalPages` automatically.

#### `usePostDetail` (`composables/usePostDetail.ts`)

Extracts all business logic for the post detail page (fetching post, comments, reactions, edit/delete flows). Accepts `{ postId, auth, router }` options. The view component becomes a thin orchestrator + template with no business logic.

#### `useLocale` (`composables/useLocale.ts`)

Manages the active vue-i18n locale. Reads the user's `preferred_language` from the auth store on mount and persists changes to the backend via `PUT /users/me`.

### Types

All TypeScript types are in `src/types/`. The `index.ts` file re-exports everything, so imports can use `@/types` without specifying individual files:

```typescript
import type { Post, User, SigMember, Notification } from '@/types'
```

Add new types to the appropriate file (`user.ts`, `post.ts`, etc.) or create a new file for a new domain. Update `types/index.ts` to re-export it.

### Utilities

`src/utils/datetime.ts` provides date formatting helpers used consistently across views.

`src/utils/html.ts` wraps DOMPurify for sanitizing HTML before rendering with `v-html`.

`src/utils/error.ts` exports `getErrorMessage(e, fallback)` — the standard way to extract a human-readable message from any caught API error. Use this in every `catch` block instead of accessing `e.response.data.message` directly.

---

## Views Reference

| View                 | Route                    | Auth Required     | Description                              |
| -------------------- | ------------------------ | ----------------- | ---------------------------------------- |
| `HomeView`           | `/`                      | No                | Landing page with hero and feature cards |
| `LoginView`          | `/login`                 | No                | Username/password login form             |
| `RegisterView`       | `/register`              | No                | New account registration                 |
| `GuestLoginView`     | `/guest`                 | No                | Guest session with invite code           |
| `NotFoundView`       | `/:pathMatch(.*)`        | No                | 404 page                                 |
| `ForumView`          | `/forum`                 | Yes               | Post list with search and pagination     |
| `PostDetailView`     | `/forum/:id`             | Yes               | Post with comments and reactions         |
| `PostCreateView`     | `/forum/create`          | Yes (Member+)     | Create a new post                        |
| `SigsDirectoryView`  | `/sigs`                  | Yes               | List of all SIGs                         |
| `SigLayout`          | `/sigs/:id`              | Yes               | SIG parent layout (provides `sig` + `userSigRole` via inject) |
| `SigPostsView`       | `/sigs/:id` (default)    | Yes               | SIG discussion feed (nested route)       |
| `SigMembersView`     | `/sigs/:id/members`      | Yes               | SIG member roster (nested route)         |
| `SigFormsView`       | `/sigs/:id/forms`        | Yes               | SIG forms list (nested route)            |
| `SigCreateView`      | `/sigs/create`           | Yes (Member+)     | Create a new SIG                         |
| `FormView`           | `/forms/:formId`         | Yes               | View and submit a form                   |
| `FormBuilderView`    | `/sigs/:sigId/forms/new` | Yes (SIG Admin)   | Create a form                            |
| `FormBuilderView`    | `/forms/:formId/edit`    | Yes (SIG Admin)   | Edit a form                              |
| `NotificationsView`  | `/notifications`         | Yes               | Full notification list                   |
| `ProfileView`        | `/profile`               | Yes               | Edit own profile and change password     |
| `UserProfileView`    | `/users/:id`             | Yes               | View another user's public profile       |
| `AboutView`          | `/about`                 | Yes (Member+)     | Platform contributors (GitHub avatars proxied) |
| `AdminDashboardView` | `/admin`                 | Yes (Admin+)      | Platform statistics                      |
| `UsersView`          | `/admin/users`           | Yes (Admin+)      | User management                          |
| `ApplicationsView`   | `/admin/applications`    | Yes (Admin+)      | Membership applications                  |
| `ReportsView`        | `/admin/reports`         | Yes (Admin+)      | Post reports                             |
| `AuditLogsView`      | `/admin/audit-logs`      | Yes (Super Admin) | Audit log                                |
| `InviteCodesView`    | `/admin/invite-codes`    | Yes (Admin+)      | Invite code management                   |

---

## Real-Time WebSocket

The `useWebSocket` composable in `src/composables/useWebSocket.ts` is initialized in `App.vue` when the user is authenticated. It maintains a persistent connection to the server.

### Connection lifecycle

1. On `App.vue` mount, if the user is authenticated, `useWebSocket` calls `POST /api/v1/auth/ws-ticket` to obtain a one-time ticket, then connects to `/api/v1/ws?ticket=<ticket>`. The ticket is valid for 30 seconds and is consumed on first use.
2. The composable sets up a 30-second PING interval.
3. On receiving a `NOTIFICATION` message, the notification count in `useNotificationsStore` is incremented and the bell icon updates.
4. On receiving a `FORCE_LOGOUT` message (e.g., account banned), the auth store is cleared and the user is redirected to `/login`.
5. On disconnect, the composable attempts reconnection with exponential backoff (up to 5 retries).

---

## Code Style

### Formatter

Prettier is configured in `.prettierrc`:

```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100,
  "endOfLine": "auto"
}
```

Run auto-format:

```bash
npm run format
```

### Linter

ESLint uses the flat config format (`eslint.config.js`). Rules extend:

- `eslint-plugin-vue` (flat/essential)
- `@vue/eslint-config-typescript`
- `@vue/eslint-config-prettier/skip-formatting` (formatting deferred to Prettier)

`@typescript-eslint/no-explicit-any` is set to `warn` rather than error, to match the current codebase style. Eliminate `any` types in new code where possible.

Run lint with auto-fix:

```bash
npm run lint
```

### Component conventions

- All components use `<script setup lang="ts">`.
- Props are typed with TypeScript interfaces or `defineProps<{...}>()`.
- Emits are typed with `defineEmits<{...}>()`.
- Template uses semantic tokens exclusively (no raw `gray-*`, `blue-*` classes).
- All interactive elements have accessible labels (`aria-label`, `aria-expanded`, etc.) where the visual context is insufficient.

---

## Adding a New Page

1. Create the component in `src/views/` (or a subdirectory for grouped routes).
2. Add the route to `src/router/index.ts` with the appropriate `meta` fields for auth guards.
3. Use base components from `src/components/base/` for all UI primitives.
4. Use semantic color tokens (`text-foreground`, `bg-surface`, etc.) for all colors.
5. Use `useAuthStore` to access the current user.
6. Remove any page-level max-width or padding wrappers — `App.vue` provides the global layout container.

### Route meta fields

```typescript
{
  path: '/my-page',
  component: () => import('@/views/MyPageView.vue'),
  meta: {
    requiresAuth: true,          // redirect to /login if not authenticated
    requiresRole: ['ADMIN'],     // redirect to / if role does not match
  }
}
```

---

## Adding a New API Module

1. Create `src/api/my-domain.ts`.
2. Import the configured Axios instance from `./index`.
3. Import types from `@/types`.
4. Export typed async functions for each endpoint.
5. If new response types are needed, add them to `src/types/` and re-export from `src/types/index.ts`.

```typescript
// src/api/bookmarks.ts
import api from './index'
import type { Bookmark } from '@/types'

export async function listBookmarks(): Promise<Bookmark[]> {
  const { data } = await api.get<Bookmark[]>('/bookmarks')
  return data
}

export async function addBookmark(postId: string): Promise<Bookmark> {
  const { data } = await api.post<Bookmark>('/bookmarks', { post_id: postId })
  return data
}
```

---

## Environment Variables

Vite exposes environment variables prefixed with `VITE_` to the browser. Variables without this prefix are available only during the build process and are not bundled.

The frontend does not currently require any `VITE_` environment variables. All API calls go through the Vite dev server proxy at `/api`, which forwards to `http://localhost:18000` as configured in `vite.config.ts`.

To add a new build-time variable:

1. Add `VITE_MY_VAR=value` to `.env`.
2. Access it in code as `import.meta.env.VITE_MY_VAR`.
3. Add a type declaration in `src/vite-env.d.ts` if needed.
