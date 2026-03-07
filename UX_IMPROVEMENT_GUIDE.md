# AI3L Community — UX Improvement Contributor Guide

> **Created:** 2026-03-06
> **Audience:** Frontend contributors
> **Language:** English throughout

This guide describes six confirmed UX issues in the AI3L Community platform. Each section explains the problem, pinpoints the affected files, and provides a detailed implementation plan. Contributors should pick up one task at a time and open a PR against the `frontend` branch.

---

## Table of Contents

1. [Admin Sidebar Layout Shift](#1-admin-sidebar-layout-shift)
2. [SIG Detail Page Redesign](#2-sig-detail-page-redesign)
3. [Forum Post Card — Richer Preview](#3-forum-post-card--richer-preview)
4. [Home Page Enhancement](#4-home-page-enhancement)
5. [Internationalization (i18n) and Language Switcher](#5-internationalization-i18n-and-language-switcher)
6. [Post-Level Reactions and Inline Comments](#6-post-level-reactions-and-inline-comments)

---

## 1. Admin Sidebar Layout Shift

**Problem:** The admin panel's left sidebar navigation jumps horizontally when navigating between pages. Pages with short content (Dashboard, Categories) have no vertical scrollbar, while pages with long content (Users, Audit Logs) trigger one — the ~15px scrollbar appearance/disappearance shifts the entire layout.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/components/AdminLayout.vue` | 48-128 | Admin layout with sidebar + content flex container |
| `src/style.css` | — | Global stylesheet (no scrollbar rules exist) |

### Root Cause

The layout uses `display: flex` with the main content area set to `flex-1`. When the browser's vertical scrollbar appears or disappears, the viewport width changes, causing the flex container to resize. The sidebar itself (`lg:w-56 lg:shrink-0`) is stable, but the content area shifts because the available width changes.

### Implementation Plan

**Option A — CSS `scrollbar-gutter` (Recommended, simplest)**

In `src/style.css`, add to the existing `html` rule or create one:

```css
html {
  scrollbar-gutter: stable;
}
```

This reserves space for the scrollbar at all times, preventing any width change when content overflows. Supported in all modern browsers (Chrome 94+, Firefox 97+, Safari 17.4+).

**Option B — Always-visible thin scrollbar (fallback)**

If broader browser support is needed:

```css
html {
  overflow-y: scroll;
}
```

This forces the scrollbar to always be visible. Combine with custom scrollbar styling to keep it unobtrusive:

```css
html {
  overflow-y: scroll;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}
```

### Verification

1. Navigate to Admin > Dashboard (short content, no scroll)
2. Navigate to Admin > Users (long table, scroll appears)
3. The sidebar and header should not shift horizontally during navigation

---

## 2. SIG Detail Page Redesign

**Problem:** The SIG detail page (`SigDetailView.vue`) stacks Posts, Members, and Forms under horizontal pill-button tabs. The three sections use completely different layouts (post cards vs. data table vs. 2-column grid), making the page feel disjointed. The tab style also differs from the underline tabs used on `ProfileView.vue`.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/views/sigs/SigDetailView.vue` | 1-611 | SIG detail page with tabs |
| `src/router/index.ts` | 134-139 | SIG detail route |

### Current Structure

```
SigDetailView.vue
  +-- Header (SIG name, description, actions)
  +-- Tab bar: [Posts] [Members] [Forms]  (pill-button style)
  +-- Tab content:
      +-- Posts:   single-column card list
      +-- Members: full-width data table
      +-- Forms:   2-column card grid
```

### Recommended Approach — Sub-route Layout with Sidebar

Convert the SIG detail page from a single-component tab view into a **layout + nested routes** pattern. This gives each section its own URL and makes navigation more natural.

**Step 1 — Create a SIG layout wrapper**

Create `src/views/sigs/SigLayout.vue`:

```
+----------------------------------------------+
| SIG Header (name, description, actions)      |
+----------+-----------------------------------+
| Sidebar  | <router-view />                   |
| - Posts  |                                   |
| - Members|                                   |
| - Forms  |                                   |
+----------+-----------------------------------+
```

The sidebar should use the same underline/highlight style as `ProfileView.vue` for consistency.

On mobile (below `lg` breakpoint), collapse the sidebar into horizontal tabs or a dropdown.

**Step 2 — Split into child views**

- `src/views/sigs/SigPostsView.vue` — Post list with "New Post" button
- `src/views/sigs/SigMembersView.vue` — Members table with role management
- `src/views/sigs/SigFormsView.vue` — Forms grid with create/manage actions

**Step 3 — Update router**

```typescript
{
  path: '/sigs/:id',
  component: () => import('@/views/sigs/SigLayout.vue'),
  meta: { requiresAuth: true },
  children: [
    { path: '',        redirect: { name: 'sig-posts' } },
    { path: 'posts',   name: 'sig-posts',   component: () => import('@/views/sigs/SigPostsView.vue') },
    { path: 'members', name: 'sig-members', component: () => import('@/views/sigs/SigMembersView.vue') },
    { path: 'forms',   name: 'sig-forms',   component: () => import('@/views/sigs/SigFormsView.vue') },
  ]
}
```

**Step 4 — Unify card styles**

All three child views should use `BaseCard` with consistent padding, spacing, and hover behavior. The Members view should switch from a raw table to member cards on mobile (responsive).

### Benefits

- Each section has a shareable URL (`/sigs/123/members`)
- Browser back/forward works per section
- Code splitting — only the active section's component is loaded
- SIG header data is fetched once in the layout and shared via `provide/inject`

---

## 3. Forum Post Card — Richer Preview

**Problem:** The `PostCard.vue` component shows minimal information before clicking into a post. Content is stripped of HTML and clamped to 6 lines with a gradient fade. There are no images, no post-level reactions, and no engagement metrics beyond comment count and view count.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/components/PostCard.vue` | 1-126 | Post preview card in forum list |
| `src/views/forum/ForumView.vue` | 1-412 | Forum list page |
| `src/types/post.ts` | 1-36 | Post type definition |

### Current Card Structure

```
[Avatar] Author Name            [Pinned badge] Time ago
                                               [Category]
Post Title
Content preview (text only, line-clamp-6, gradient fade)...

[keyword] [keyword] [keyword]

--- divider ---
5 comments    [eye] 120    Last reply 2h ago
```

### Implementation Plan

**3.1 — Extract first image from post content**

Add a utility function in `src/utils/` or directly in `PostCard.vue`:

```typescript
function extractFirstImage(html: string): string | null {
  const match = html.match(/<img[^>]+src="([^"]+)"/)
  return match ? match[1] : null
}
```

If an image is found, display it as a thumbnail on the right side of the card (similar to Reddit/Facebook link previews) or as a full-width banner above the content.

**3.2 — Increase content preview**

Change the default line clamp from 6 to a more generous value, or switch to a character-based truncation (~300 characters) to show more meaningful content:

```vue
<!-- PostCard.vue: change line 80 area -->
<p class="text-sm text-muted line-clamp-8">
  {{ stripHtml(post.content).slice(0, 300) }}
</p>
```

**3.3 — Add engagement metrics to card footer**

Redesign the footer to show richer information:

```
LIKE 12  SMILE 3  CRY 1    |    [chat] 5 comments    [eye] 120    Last reply 2h ago
```

This requires post-level reactions (see [Section 6](#6-post-level-reactions-and-inline-comments)).

**3.4 — Show author context**

Optionally add a small role badge or SIG badge next to the author name to give context about who is posting.

### Design Reference

Think Facebook post card:
- Author + avatar + timestamp at top
- Full text content (expandable with "See more")
- Image/media preview if present
- Reaction bar + comment count at bottom
- Quick reaction buttons visible without clicking in

---

## 4. Home Page Enhancement

**Problem:** After logging in, clicking the top-left AI3L icon leads to a page that only shows a welcome card, 5 recent posts, an unread notification badge, and a few quick links. It feels static and uninviting.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/views/HomeView.vue` | 1-292 | Home page (authenticated + unauthenticated) |

### Current Layout (Authenticated User)

```
+------------------------------------------+
| Welcome back, {name}                     |
| [Browse Forum]  [My SIGs]               |
+------------------------------------------+
| Guest warning (if guest)                 |
| Guest membership form (if guest)         |
+------------------------------------------+
| Recent Posts (5 items)     | Notifications|
|                            | Quick Links  |
+------------------------------------------+
```

### Proposed Layout

```
+------------------------------------------+
| Welcome back, {name}                     |
| [Browse Forum]  [My SIGs]               |
+----------+-------------------------------+
| Left Col |  Trending Posts (7 days)      |
|          |  (3-5 posts with engagement)  |
| Community|-------------------------------+
| Stats    |  Recent Posts                 |
| - Members|  (5 latest, richer cards)     |
| - Posts  |-------------------------------+
| - SIGs   |  Your SIGs                   |
|          |  (SIGs you've joined, quick   |
| Featured |   access with member count)   |
| SIGs     |                               |
| (top 3)  |                               |
+----------+-------------------------------+
```

### Implementation Plan

**4.1 — Community statistics widget**

Create a new component `src/components/CommunityStats.vue` that shows real data. The admin dashboard API already returns stats — create a lightweight public endpoint or reuse existing data:

- Total members (from user count)
- Total posts (from post count)
- Active SIGs (from SIG count)

Display as a compact card with icon + number + label in a vertical stack.

**4.2 — Trending posts section**

The backend already has `GET /posts?sort=trending` support (or can be added). Show 3-5 posts sorted by engagement (comments + views) from the last 7 days. Use `PostCard` with `contentClamp: 3` for a compact view.

**4.3 — User's SIGs section**

Fetch the SIGs the current user has joined (`GET /sigs?member=true` or filter from `/sigs`). Show as small cards with:
- SIG name
- Member count
- Latest post title
- Quick "View" link

**4.4 — Featured SIGs sidebar**

Show 3 most active or newest SIGs for users who haven't joined many groups. Acts as a discovery mechanism.

**4.5 — Unauthenticated landing page**

Replace the hardcoded stat cards ("Open Community", "Academic Focus", "Global Network") with real numbers fetched from a public stats endpoint.

### Priority

Start with 4.1 (stats) and 4.2 (trending) — they add the most value with the least effort.

---

## 5. Internationalization (i18n) and Language Switcher

**Problem:** All UI text is hardcoded in English across 51 Vue files (~500-700 strings). There is no i18n infrastructure, no translation files, and no language switcher.

### Current State

- **No i18n library** installed
- **No locale files** or translation directories
- **~51 Vue files** with hardcoded English strings
- Strings are in templates, computed properties, error handlers, and object literals

### Affected Files (All Vue files, highest priority first)

| File | Estimated Strings | Complexity |
|------|------------------|------------|
| `src/views/admin/UsersView.vue` | 80+ | High |
| `src/views/forum/ForumView.vue` | 60+ | High |
| `src/views/forms/FormBuilderView.vue` | 60+ | High |
| `src/components/AppNavbar.vue` | 40+ | Medium |
| `src/views/ProfileView.vue` | 50+ | High |
| `src/views/auth/LoginView.vue` | 20+ | Low |
| `src/views/auth/RegisterView.vue` | 25+ | Low |
| All other views and components | 200+ | Varies |

### Implementation Plan

This is a large task. Break it into phases and assign to multiple contributors.

#### Phase 1 — Setup (1 PR)

**1.1 Install vue-i18n:**

```bash
cd frontend
npm install vue-i18n@11
```

**1.2 Create locale directory structure:**

```
src/
  locales/
    en/
      common.ts      # Shared: buttons, labels, errors
      nav.ts         # Navigation labels
      auth.ts        # Login, register, password
      forum.ts       # Forum, posts, comments
      admin.ts       # Admin panel strings
      sigs.ts        # SIG-related strings
      forms.ts       # Form builder strings
      notifications.ts
    zh-TW/           # Future: Traditional Chinese
      ...same files...
    index.ts         # Merges all locale modules, exports i18n instance
```

**1.3 Initialize in `main.ts`:**

```typescript
import { createI18n } from 'vue-i18n'
import en from '@/locales/en'

const i18n = createI18n({
  legacy: false,            // Composition API mode
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en }
})

app.use(i18n)
```

**1.4 Create a composable helper:**

```typescript
// src/composables/useLocale.ts
import { useI18n } from 'vue-i18n'

export function useLocale() {
  const { t, locale } = useI18n()

  function setLocale(lang: string) {
    locale.value = lang
    localStorage.setItem('locale', lang)
  }

  return { t, locale, setLocale }
}
```

#### Phase 2 — String Extraction (Multiple PRs, one domain per PR)

For each domain (auth, forum, admin, etc.), create a PR that:

1. Extracts all hardcoded strings into the corresponding locale file
2. Replaces template strings with `{{ t('key') }}`
3. Replaces script strings with `const { t } = useI18n()`
4. Updates tests to provide the i18n plugin in test mounts

**Example — Before:**
```vue
<BaseButton>Log In</BaseButton>
<p v-if="error">Login failed. Please try again.</p>
```

**Example — After:**
```vue
<BaseButton>{{ t('auth.login') }}</BaseButton>
<p v-if="error">{{ t('auth.loginFailed') }}</p>
```

**String key conventions:**
- Use dot-notation namespacing: `domain.section.key`
- Use camelCase for keys: `auth.loginFailed`, not `auth.login-failed`
- Keep keys short but descriptive
- Group related strings under common parents

#### Phase 3 — Language Switcher UI (1 PR)

Add a language dropdown in `src/components/AppNavbar.vue` between the notification bell and user dropdown:

```vue
<!-- Desktop -->
<button @click="toggleLangMenu" class="text-sm px-2 py-1 rounded hover:bg-surface-alt">
  {{ currentLocaleLabel }}
</button>

<!-- Dropdown -->
<div v-if="langMenuOpen" class="absolute right-0 mt-2 w-32 bg-surface border rounded shadow-lg">
  <button @click="setLocale('en')">English</button>
  <button @click="setLocale('zh-TW')">繁體中文</button>
</div>
```

Persist the selection to `localStorage` and read it on app startup.

#### Phase 4 — Add Translation Files (Per language)

Once the English keys are extracted, contributors can add translation files for other languages by copying `src/locales/en/` and translating each value.

### Testing Considerations

All existing Vitest tests that mount Vue components will need the i18n plugin injected. Create a test helper:

```typescript
// tests/helpers/i18n.ts
import { createI18n } from 'vue-i18n'
import en from '@/locales/en'

export const testI18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en }
})
```

Use in tests:
```typescript
mount(Component, { global: { plugins: [testI18n] } })
```

---

## 6. Post-Level Reactions and Inline Comments

**Problem:** Users must click into a post to leave a comment or react. Reactions (LIKE, SMILE, CRY) only exist on comments, not on posts themselves. This creates friction for quick engagement.

### Affected Files

**Frontend:**

| File | Lines | Role |
|------|-------|------|
| `src/components/PostCard.vue` | 1-126 | Post preview card (no reactions) |
| `src/views/forum/PostDetailView.vue` | 1-982 | Post detail with comment reactions |
| `src/types/post.ts` | 1-36 | Post type (no reactions field) |
| `src/types/comment.ts` | 1-13 | Comment type (has reactions) |
| `src/api/posts.ts` | — | Post API module |
| `src/api/comments.ts` | 1-42 | Comment API (has reaction toggle) |

**Backend:**

| File | Lines | Role |
|------|-------|------|
| `app/api/v1/endpoints/posts.py` | 1-226 | Post endpoints (no reaction endpoint) |
| `app/api/v1/endpoints/comments.py` | 1-119 | Comment endpoints (has reaction toggle) |
| `app/repositories/comment_repo.py` | 174-216 | Reaction toggle logic (JSONB update) |
| `app/schemas/post.py` | 49-64 | PostResponse (no reactions field) |

### Current Reaction Architecture

Reactions are stored as JSONB on the `comments` table:
```json
{ "LIKE": ["user-id-1", "user-id-2"], "SMILE": ["user-id-3"] }
```

Available types: `LIKE`, `SMILE`, `CRY` (validated in `app/schemas/comment.py:39`).

Toggle logic in `comment_repo.py:174-216`:
1. Lock row with `SELECT ... FOR UPDATE`
2. Parse JSONB reactions
3. Add or remove user ID from the reaction array
4. Remove empty reaction keys
5. Write back to DB

### Implementation Plan

#### 6.1 — Backend: Add post-level reactions

**Step 1 — Database migration:**

Create a new Alembic migration to add a `reactions` JSONB column to the `posts` table:

```python
op.add_column('posts', sa.Column('reactions', sa.JSON(), nullable=True))
```

**Step 2 — Update PostResponse schema (`app/schemas/post.py`):**

Add to the `PostResponse` class:
```python
reactions: dict[str, list[str]] | None = None
```

**Step 3 — Create reaction endpoint (`app/api/v1/endpoints/posts.py`):**

```python
@router.post("/{post_id}/reactions")
async def toggle_post_reaction(
    post_id: str,
    body: ReactionToggle,  # reuse from comment schema
    current_user = Depends(get_current_user),
    conn = Depends(get_connection)
):
    ...
```

**Step 4 — Add repository method (`app/repositories/post_repo.py`):**

Reuse the same JSONB toggle pattern from `comment_repo.py:174-216`. Consider extracting a shared helper to avoid duplication:

```python
# app/repositories/reaction_helpers.py
async def toggle_reaction_jsonb(
    conn, table: str, row_id: str, user_id: str, reaction_type: str
) -> dict:
    ...
```

#### 6.2 — Frontend: Post reactions on PostCard

**Step 1 — Update Post type (`src/types/post.ts`):**

```typescript
reactions: Record<string, string[]> | null
```

**Step 2 — Add API function (`src/api/posts.ts`):**

```typescript
export function togglePostReaction(postId: string, reactionType: string) {
  return api.post(`/posts/${postId}/reactions`, { reaction_type: reactionType })
}
```

**Step 3 — Add reaction bar to `PostCard.vue`:**

Below the existing footer divider, add reaction buttons:

```vue
<div class="flex items-center gap-2 px-4 pb-2">
  <button
    v-for="r in ['LIKE', 'SMILE', 'CRY']"
    :key="r"
    @click.stop="toggleReaction(r)"
    :class="[
      'text-xs px-2 py-1 rounded-full transition',
      hasReacted(r) ? 'bg-brand-100 text-brand-700' : 'hover:bg-surface-alt text-muted'
    ]"
  >
    {{ emojiMap[r] }} {{ getCount(r) || '' }}
  </button>
</div>
```

Use `@click.stop` to prevent the card click (navigation to detail) from firing.

**Step 4 — Optimistic UI update:**

Instead of refetching all posts after a reaction toggle, update the local state immediately:

```typescript
function toggleReaction(type: string) {
  const reactions = { ...(post.reactions || {}) }
  const users = reactions[type] || []
  if (users.includes(currentUserId)) {
    reactions[type] = users.filter(id => id !== currentUserId)
  } else {
    reactions[type] = [...users, currentUserId]
  }
  // Update locally first, then call API
  emit('update:reactions', reactions)
  togglePostReaction(post.id, type).catch(() => {
    // Revert on failure
  })
}
```

#### 6.3 — Inline quick comment (Optional, lower priority)

Adding full inline commenting from the list view is complex. A simpler approach:

**Quick comment input:** Add a collapsed text input at the bottom of `PostCard.vue` that expands on click. When submitted, it posts a top-level comment via the existing `POST /posts/{post_id}/comments` endpoint and increments the local comment count.

This can be a follow-up PR after post-level reactions are working.

---

## Priority Order

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Admin sidebar layout shift | 15 min | Quick win, eliminates visual bug |
| 2 | Forum post card richer preview | 2-4 hours | Immediate UX improvement |
| 3 | Home page enhancement | 4-8 hours | Better first impression |
| 4 | Post-level reactions | 6-10 hours | More engagement (backend + frontend) |
| 5 | SIG detail page redesign | 8-12 hours | Better information architecture |
| 6 | i18n and language switcher | 30-50 hours | Large, can be phased across sprints |

---

## General Guidelines

- **One PR per task** (or per sub-task for larger items)
- **Branch naming:** `feat/ux-admin-sidebar`, `feat/ux-post-reactions`, etc.
- **Test coverage:** Add or update Vitest tests for any new components or changed behavior
- **Mobile responsiveness:** All changes must work on screens down to 375px width
- **Accessibility:** Maintain keyboard navigation and ARIA attributes
- **No Chinese in UI:** All user-facing text must be in English (translations come later via i18n)
