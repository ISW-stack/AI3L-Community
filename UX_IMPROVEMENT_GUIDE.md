# AI3L Community — UX Improvement Contributor Guide

> **Created:** 2026-03-06
> **Last Updated:** 2026-03-12
> **Audience:** Frontend + Backend contributors
> **Language:** English throughout

This guide catalogues confirmed UX issues and improvement opportunities in the AI3L Community platform. Each section explains the problem, pinpoints the affected files, and provides a detailed implementation plan. Contributors should pick up one task at a time and open a PR against the `frontend` branch (or `backend` for backend-only tasks).

---

## Table of Contents

**Completed:**
- ~~[1. Admin Sidebar Layout Shift](#1-admin-sidebar-layout-shift--done)~~ — Done
- ~~[2. SIG Detail Page Redesign](#2-sig-detail-page-redesign--done)~~ — Done
- ~~[3. Forum Post Card — Richer Preview](#3-forum-post-card--richer-preview--done)~~ — Done
- ~~[4. Home Page Enhancement](#4-home-page-enhancement--done)~~ — Done
- ~~[5. Post-Level Reactions](#5-post-level-reactions--done)~~ — Done
- ~~[6. Internationalization (i18n) and Language Switcher](#6-internationalization-i18n-and-language-switcher--done)~~ — Done
- ~~[7. Silent Error Handling — Toast Notifications](#7-silent-error-handling--toast-notifications--done)~~ — Done
- ~~[8. Confirmation Dialogs for Destructive Actions](#8-confirmation-dialogs-for-destructive-actions--done)~~ — Done
- ~~[9. Image Lazy Loading and Fallbacks](#9-image-lazy-loading-and-fallbacks--done)~~ — Done
- ~~[10. Breadcrumb Navigation](#10-breadcrumb-navigation--done)~~ — Done
- ~~[11. Accessibility Improvements](#11-accessibility-improvements--done)~~ — Done
- ~~[12. Empty State Consistency](#12-empty-state-consistency--done)~~ — Done
- ~~[13. Page Transition Animations](#13-page-transition-animations--done)~~ — Done
- ~~[14. Responsive Breakpoint Gaps](#14-responsive-breakpoint-gaps--done)~~ — Done
- ~~[15. Forum Search UX](#15-forum-search-ux--done)~~ — Done
- ~~[16. Pagination Enhancements](#16-pagination-enhancements--done)~~ — Done
- ~~[17. Public Stats API Endpoint (Backend)](#17-public-stats-api-endpoint-backend--done)~~ — Done
- ~~[18. User Preferences API (Backend)](#18-user-preferences-api-backend--done)~~ — Done
- ~~[19. Search Suggestions API (Backend)](#19-search-suggestions-api-backend--done)~~ — Done
- ~~[20. SIG Members Pagination](#20-sig-members-pagination--done)~~ — Done

**All tasks complete as of 2026-03-12.**

---

## 1. Admin Sidebar Layout Shift — DONE

> **Status:** Completed. `scrollbar-gutter: stable` added to `src/style.css` (line 62).

No further action needed.

---

## 2. SIG Detail Page Redesign — DONE

> **Status:** Completed. Refactored into `SigLayout.vue` + `SigPostsView.vue` + `SigMembersView.vue` + `SigFormsView.vue` with nested routes and `provide/inject`. Old `SigDetailView.vue` deleted.

No further action needed.

---

## 3. Forum Post Card — Richer Preview — DONE

> **Status:** Completed. PostCard now shows post-level reactions (interactive for members, read-only for guests), thumbnail extraction, and optimistic UI updates. PostDetailView also shows post-level reactions. 14 new PostCard tests added.

**Problem:** The `PostCard.vue` component (126 lines) shows minimal information before clicking into a post. Content is stripped of HTML and clamped to 6 lines with a gradient fade. There are no images, no post-level reactions, and no engagement metrics beyond comment count and view count.

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

> **Note:** Avoid regex-based HTML parsing (`/<img[^>]+src="([^"]+)"/`) — it is fragile. Prefer `DOMParser` in the browser, or better yet, extract and store the first image URL on the backend when a post is saved (add a `thumbnail_url` column).

**Browser-side approach (if backend change is out of scope):**

```typescript
function extractFirstImage(html: string): string | null {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const img = doc.querySelector('img')
  return img?.getAttribute('src') ?? null
}
```

If an image is found, display it as a thumbnail on the right side of the card or as a full-width banner above the content.

**3.2 — Increase content preview**

Change the default line clamp from 6 to 8, or switch to character-based truncation (~300 characters):

```vue
<p class="text-sm text-muted line-clamp-8">
  {{ stripHtml(post.content).slice(0, 300) }}
</p>
```

**3.3 — Add engagement metrics to card footer**

Redesign the footer to show richer information (requires post-level reactions from [Section 5](#5-post-level-reactions)):

```
LIKE 12  SMILE 3  CRY 1    |    [chat] 5 comments    [eye] 120    Last reply 2h ago
```

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

## 4. Home Page Enhancement — DONE

> **Status:** Completed. Home page now shows trending posts (PostCard with contentClamp=3), recent posts (PostCard), community stats widget (real numbers from `/public/stats`), user's SIGs sidebar, featured SIGs sidebar, and responsive `md:grid-cols-3` layout. Unauthenticated landing shows real stats. All locale files updated.

**Problem:** After logging in, clicking the top-left AI3L icon leads to a page that only shows a welcome card, 5 recent posts, an unread notification badge, and a few quick links. It feels static and uninviting.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/views/HomeView.vue` | 1-292 | Home page (authenticated + unauthenticated) |

### Backend Status

- `GET /posts/trending` — **already exists** (top 5 posts, last 7 days, by comments+views)
- `GET /sigs/my` — **already exists** (returns user's joined SIGs with `my_role`)
- Public stats endpoint — **missing** (see [Section 17](#17-public-stats-api-endpoint-backend))

### Proposed Layout (Authenticated)

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

Create `src/components/CommunityStats.vue`. Requires a public stats endpoint ([Section 17](#17-public-stats-api-endpoint-backend)) or reuse admin dashboard data for authenticated users.

**4.2 — Trending posts section**

Use the existing `GET /posts/trending` endpoint. Show 3-5 posts with `PostCard` using a compact `contentClamp: 3`.

**4.3 — User's SIGs section**

Use the existing `GET /sigs/my` endpoint. Show as small cards with SIG name, member count, and quick "View" link.

**4.4 — Featured SIGs sidebar**

Show 3 most active or newest SIGs for users who haven't joined many groups. Acts as a discovery mechanism.

**4.5 — Unauthenticated landing page**

Replace the hardcoded feature cards ("Open Community", "Academic Focus", "Global Network") with real numbers once the public stats endpoint exists.

### Priority

Start with 4.2 (trending — endpoint exists) and 4.3 (my SIGs — endpoint exists). They add the most value with existing backend support.

---

## 5. Post-Level Reactions — DONE

> **Status:** Completed. Full-stack implementation: Alembic migration (reactions JSONB on posts), shared `reaction_helpers.py` (refactored comment_repo to use it too), `POST /posts/{post_id}/reactions` endpoint, PostResponse schema + converter updated, toggle API in frontend, optimistic UI in PostCard + PostDetailView. 16 new backend tests + 14 new frontend tests.

**Problem:** Users must click into a post to leave a reaction. Reactions (LIKE, SMILE, CRY) only exist on comments, not on posts themselves. This creates friction for quick engagement.

### Dependency Note

This task is a **prerequisite** for Section 3.3 (post card engagement metrics). Complete this first.

### Current Reaction Architecture (Comments)

Reactions are stored as JSONB on the `comments` table:
```json
{ "LIKE": ["user-id-1", "user-id-2"], "SMILE": ["user-id-3"] }
```

Available types: `LIKE`, `SMILE`, `CRY` (validated in `app/schemas/comment.py:39`).

Toggle logic in `comment_repo.py:177-219`:
1. Lock row with `SELECT ... FOR UPDATE`
2. Parse JSONB reactions
3. Add or remove user ID from the reaction array
4. Remove empty reaction keys
5. Write back to DB

### Affected Files

**Backend:**

| File | Role |
|------|------|
| `app/api/v1/endpoints/posts.py` | Post endpoints (no reaction endpoint yet) |
| `app/repositories/post_repo.py` | Post repo (no reaction method yet) |
| `app/repositories/comment_repo.py:177-219` | Existing reaction toggle pattern to reuse |
| `app/schemas/post.py` | PostResponse (no reactions field yet) |
| `app/schemas/comment.py:39` | ReactionRequest schema (reuse) |

**Frontend:**

| File | Role |
|------|------|
| `src/components/PostCard.vue` | Post preview card (no reactions) |
| `src/types/post.ts` | Post type (no reactions field) |
| `src/api/posts.ts` | Post API module |

### Implementation Plan

#### 5.1 — Backend

**Step 1 — Database migration:** Add `reactions JSONB` to `posts` table.

**Step 2 — Extract shared helper:** Create `app/repositories/reaction_helpers.py`:

```python
async def toggle_reaction_jsonb(
    conn, table: str, row_id: str, user_id: str, reaction_type: str
) -> dict:
    ...
```

Refactor `comment_repo.py` to use this shared helper too.

**Step 3 — Update PostResponse schema** — add `reactions: dict[str, list[str]] | None = None`

**Step 4 — Create endpoint:**

```python
@router.post("/{post_id}/reactions")
async def toggle_post_reaction(
    post_id: str,
    body: ReactionRequest,  # reuse from comment schema
    current_user = Depends(get_current_user),
    conn = Depends(get_connection)
):
    ...
```

> **Route ordering:** Place this route BEFORE `/{post_id}` param routes to avoid 422 errors.

#### 5.2 — Frontend

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

Use `@click.stop` to prevent card click (navigation) from firing.

**Step 4 — Optimistic UI update** with rollback on API failure.

---

## 6. Internationalization (i18n) and Language Switcher — DONE

> **Status:** Completed (prior to this guide). vue-i18n 11.x with 18 languages, `LanguageSwitcher.vue` in AppNavbar, `useLocale.ts` composable, `preferred_language` column in users table, RTL support for Arabic. All views use `t()` calls.

**Problem:** All UI text is hardcoded in English across ~54 Vue files (~500-700 strings). There is no i18n infrastructure, no translation files, and no language switcher.

> **Recommendation:** This is the largest task (~30-50 hours). Only start if there is a confirmed need for multi-language support. The setup phase (Phase 1) can be done independently.

### Implementation Plan

#### Phase 1 — Setup (1 PR)

1. Install `vue-i18n@11`
2. Create `src/locales/en/` directory with domain-based files (common, nav, auth, forum, admin, sigs, forms, notifications)
3. Initialize in `main.ts` with `legacy: false` (Composition API mode)
4. Create `src/composables/useLocale.ts` helper
5. Create test helper for injecting i18n plugin in Vitest mounts

#### Phase 2 — String Extraction (Multiple PRs, one domain per PR)

For each domain, extract hardcoded strings into locale files and replace with `t('key')` calls.

**String key conventions:**
- Dot-notation namespacing: `domain.section.key`
- camelCase keys: `auth.loginFailed`
- Short but descriptive

#### Phase 3 — Language Switcher UI (1 PR)

Add language dropdown in `AppNavbar.vue`. Persist to `localStorage`.

#### Phase 4 — Translation Files (Per language)

Copy `src/locales/en/` and translate each value.

### Testing Impact

All 391 Vitest tests that mount Vue components will need the i18n plugin injected. Use a shared test helper.

---

## 7. Silent Error Handling — Toast Notifications — DONE

> **Status:** Completed (audited 2026-03-12). All 21 files using `useToastStore` — silent catches were already fixed across views.

**Problem:** 11+ views silently swallow API errors in `catch` blocks, leaving users with blank content and no feedback. The platform already has a working toast system (`useToastStore`) — it's just not used consistently.

### Affected Files

| File | Lines | Issue |
|------|-------|-------|
| `src/views/NotificationsView.vue` | 50, 66, 78 | Silent catch on fetch/mark-read/mark-all |
| `src/views/sigs/SigsDirectoryView.vue` | 36 | Silent catch on SIG list fetch |
| `src/views/HomeView.vue` | 50 | Silent catch on recent posts fetch |
| `src/views/admin/AdminDashboardView.vue` | 19 | Silent catch on stats fetch |
| `src/views/forum/PostCreateView.vue` | 91, 99 | Silent catch on category/SIG fetch |
| `src/views/admin/ReportsView.vue` | 29, 40 | Silent catch on fetch + review action |
| `src/views/admin/InviteCodesView.vue` | 29 | Silent catch on codes fetch |
| `src/views/sigs/SigPostsView.vue` | 29 | console.error only, no user feedback |
| `src/views/sigs/SigMembersView.vue` | 48 | console.error only, no user feedback |
| `src/views/forum/ForumView.vue` | 58, 66, 96, 130 | console.error only |
| `src/views/sigs/SigLayout.vue` | 70 | console.error only |
| `src/views/UserProfileView.vue` | 77 | console.error only |

### Implementation Plan

For each silent catch block, add toast feedback using the existing pattern:

```typescript
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'

const toast = useToastStore()

// In catch block:
catch (e: unknown) {
  toast.show(getErrorMessage(e, 'Failed to load data.'), 'error')
}
```

**For fetch errors** (data loading): Show error toast + set an `error` ref to display inline error state.

**For action errors** (save, delete, update): Show error toast only — the user can retry.

### Effort: 1-2 hours | Impact: High

---

## 8. Confirmation Dialogs for Destructive Actions — DONE

> **Status:** Completed (audited 2026-03-12). `SigMembersView` and `SigLayout` both use `BaseModal` with confirm state machine for removeMember/leaveSig.

**Problem:** Two destructive actions lack confirmation dialogs — member removal and SIG leave. The platform already uses `BaseModal` for confirmation elsewhere (post delete, account delete, category delete, etc.).

### Affected Files

| File | Lines | Issue |
|------|-------|-------|
| `src/views/sigs/SigMembersView.vue` | 59-66 | `removeMember()` — no confirmation, removes immediately |
| `src/views/sigs/SigLayout.vue` | 119-121 | `leaveSig()` — no confirmation, leaves immediately |

### Implementation Plan

Follow the existing pattern used in `PostDetailView.vue` and `CategoriesView.vue`:

1. Add a `confirmAction` ref to store pending action details
2. Show `BaseModal` with warning message and Cancel/Confirm buttons
3. Execute action only on confirm

### Effort: 30 min | Impact: Medium (prevents accidental data loss)

---

## 9. Image Lazy Loading and Fallbacks — DONE

> **Status:** Completed (commit 27229a3 + audited 2026-03-12). All images use `loading="lazy"`, `width`/`height` attributes, and `@error` fallback handlers.

**Problem:** No images in the app use `loading="lazy"` or explicit `width/height` attributes. All images load immediately on page render regardless of viewport position, and there are no error fallbacks.

### Affected Files

| File | Element | Issue |
|------|---------|-------|
| `src/components/base/BaseAvatar.vue` | Avatar images | No lazy loading, no error fallback |
| `src/views/forms/FormView.vue:212` | Banner image | No lazy loading |
| `src/views/forms/FormBuilderView.vue:243,488` | Banner images | No lazy loading |
| `src/views/ProfileView.vue:286` | Avatar preview | No lazy loading |
| `src/views/AboutView.vue:79` | Contributor avatars | No lazy loading (multiple images) |
| `src/views/NotificationsView.vue:196` | Notification avatars | No lazy loading |

### Implementation Plan

**9.1 — Add `loading="lazy"` to all off-viewport images.**

Exception: above-the-fold images (e.g., the user's own avatar in navbar) should keep eager loading.

**9.2 — Add `width` and `height` attributes** to prevent Cumulative Layout Shift (CLS).

**9.3 — Add `@error` fallback handler** on `<img>` tags to show a placeholder when images fail to load.

```vue
<img
  :src="avatarUrl"
  loading="lazy"
  width="40"
  height="40"
  @error="(e: Event) => (e.target as HTMLImageElement).src = '/fallback-avatar.svg'"
  class="w-10 h-10 object-cover rounded-full"
/>
```

### Effort: 1 hour | Impact: Medium (performance + robustness)

---

## 10. Breadcrumb Navigation — DONE

> **Status:** Completed (2026-03-12). `BaseBreadcrumb` added to 14 views: PostDetailView, ProfileView, UserProfileView, SigPostsView, SigMembersView, SigFormsView, FormBuilderView, FormView, and all 8 admin views. Hardcoded "Back to Forum" links replaced. i18n keys in all 17 locale files.

**Problem:** A `BaseBreadcrumb.vue` component exists in the codebase but is **never used** in any view. Users have no contextual navigation path and rely on hardcoded "Back" links that always point to `/forum`.

### Affected Files

| File | Issue |
|------|-------|
| `src/components/base/BaseBreadcrumb.vue` | Exists but unused |
| `src/views/ProfileView.vue:231` | Hardcoded "Back to Forum" link |
| `src/views/UserProfileView.vue:111` | Hardcoded "Back to Forum" link |

### Implementation Plan

Add `BaseBreadcrumb` to key views:

| View | Breadcrumb Path |
|------|----------------|
| PostDetailView | Home > Forum > [Category] > Post Title |
| ProfileView | Home > My Profile |
| UserProfileView | Home > Forum > [User Name] |
| SigLayout (children) | Home > SIGs > [SIG Name] > Posts/Members/Forms |
| Admin pages | Admin > [Page Name] |
| FormBuilderView | Home > SIGs > [SIG Name] > Forms > [Form Title] |

### Effort: 2-3 hours | Impact: Medium (navigation clarity)

---

## 11. Accessibility Improvements — DONE

> **Status:** Completed (2026-03-12). FormBuilderView: aria-label on move/delete/option buttons. FormView: aria-required, aria-pressed on rating buttons, role="group". NotificationsView: role="tablist/tab", aria-selected. BasePagination: aria-current="page", nav element with aria-label. BaseModal: aria-label fallback when no title. i18n keys in all 17 locale files.

**Problem:** Several interactive elements lack ARIA attributes, making the platform harder to use with screen readers and keyboard navigation.

### Issues by File

| File | Lines | Issue |
|------|-------|-------|
| `src/views/forms/FormBuilderView.vue` | 310-330 | Move/delete buttons (↑ ↓ ×) have no `aria-label` |
| `src/views/forms/FormBuilderView.vue` | 394-408 | Choice option inputs have no labels |
| `src/views/forms/FormView.vue` | 325-340 | Rating buttons lack `aria-label` and `aria-pressed` |
| `src/views/forms/FormView.vue` | 261 | Required fields: `*` only, no `aria-required="true"` |
| `src/views/NotificationsView.vue` | 147-173 | Filter tabs missing `aria-selected` |
| `src/components/base/BasePagination.vue` | 49-60 | Active page missing `aria-current="page"` |
| `src/components/base/BaseModal.vue` | 109-110 | `aria-labelledby` undefined when no title |

### Implementation Plan

Each item is a small, independent fix. Can be batched into one PR:

1. Add `aria-label="Move question up/down"` and `aria-label="Delete question"` to FormBuilder buttons
2. Add `aria-label="Option N"` to choice input fields
3. Add `aria-label="Rate N out of M"` and `aria-pressed` to rating buttons
4. Add `aria-required="true"` to required form inputs
5. Add `aria-selected` to notification filter tabs
6. Add `aria-current="page"` to active pagination button
7. Ensure BaseModal always has a valid `aria-labelledby` target

### Effort: 1-2 hours | Impact: High (WCAG compliance)

---

## 12. Empty State Consistency — DONE

> **Status:** Completed (audited 2026-03-12). All 4 locations (PostDetailView, SigFormsView, FormBuilderView, SigsDirectoryView) already use `EmptyState` component with proper props.

**Problem:** Some list views show styled `EmptyState` components when data is empty, while others use plain text. The experience is inconsistent.

### Affected Files

| File | Lines | Current | Recommended |
|------|-------|---------|-------------|
| `src/views/forum/PostDetailView.vue` | 257-259 | Plain text "No comments yet." | `EmptyState` with CTA |
| `src/views/sigs/SigFormsView.vue` | 196-197 | Plain text "No one has responded..." | `EmptyState` component |
| `src/views/forms/FormView.vue` | 572-574 | Plain text "No questions added yet" | `EmptyState` with icon |
| `src/views/sigs/SigsDirectoryView.vue` | — | No empty state for search results | Add "No SIGs found" |

### Implementation Plan

Replace plain text with the existing `EmptyState` component pattern used elsewhere in the app. Include an icon, a title, and a helpful message or CTA.

### Effort: 30 min | Impact: Low (visual polish)

---

## 13. Page Transition Animations — DONE

> **Status:** Completed (audited 2026-03-12). `src/style.css` has `.page-enter-active/.page-leave-active` 150ms opacity fade transitions.

**Problem:** `App.vue:41` wraps `<RouterView>` in `<Transition name="page" mode="out-in">` but no `.page-enter-active` / `.page-leave-active` CSS classes are defined. Route changes have no visual transition.

### Affected Files

| File | Lines | Role |
|------|-------|------|
| `src/App.vue` | 41 | Transition wrapper (name="page") |
| `src/style.css` | — | Missing transition CSS |

### Implementation Plan

Add to `src/style.css`:

```css
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
}
```

Keep it subtle (150ms opacity fade). Avoid slide animations — they feel sluggish on fast navigations.

### Effort: 10 min | Impact: Low (perceived polish)

---

## 14. Responsive Breakpoint Gaps — DONE

> **Status:** Completed (audited 2026-03-12). HomeView and all major views use `sm:`/`md:`/`lg:` multi-breakpoint grids.

**Problem:** Several views jump from single-column to multi-column layout at `lg:` (1024px) with no intermediate `md:` (768px) breakpoint. Tablets get either a cramped multi-column or an unnecessarily wide single-column.

### Affected Files

| File | Lines | Issue |
|------|-------|-------|
| `src/views/HomeView.vue` | 68 | `grid-cols-1 lg:grid-cols-3` — no `md:` |
| `src/views/forms/FormBuilderView.vue` | 334-357 | `grid-cols-1 sm:grid-cols-3` — jumps too early |
| `src/views/ProfileView.vue` | 226 | Only `lg:px-layout` — no `md:` padding |
| `src/views/forum/ForumView.vue` | 352 | Right sidebar fixed `w-[280px]` — not responsive |

### Implementation Plan

Add `md:` breakpoint variants where only `lg:` exists. Example for HomeView:

```vue
<!-- Before -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

<!-- After -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
```

### Effort: 1-2 hours | Impact: Medium (tablet UX)

---

## 15. Forum Search UX — DONE

> **Status:** Completed (2026-03-12). ForumView now has 300ms debounced search on input + loading spinner during search + immediate search on Enter/button click.

**Problem:** Forum search triggers only on Enter key with no debounce, no loading indicator during search, and no search suggestions. The `UsersView.vue` admin search has a proper 300ms debounce — the forum should follow the same pattern.

### Affected Files

| File | Lines | Issue |
|------|-------|-------|
| `src/views/forum/ForumView.vue` | 232-245 | Search on Enter only, no debounce |
| `src/views/forum/ForumView.vue` | 250-281 | Advanced filters with no debounce |

### Implementation Plan

**15.1 — Add debounce to search input** (300ms, matching UsersView pattern).

**15.2 — Add loading spinner** next to search input while API request is in-flight.

**15.3 — (Optional) Search suggestions** — requires backend endpoint (see [Section 19](#19-search-suggestions-api-backend)).

### Effort: 1 hour (15.1 + 15.2) | Impact: Medium

---

## 16. Pagination Enhancements — DONE

> **Status:** Completed (2026-03-12). `BasePagination` now shows "Showing X-Y of Z" result count text. Mobile-optimized: screens below `sm` show only prev/next + "Page X of Y". i18n keys in all 17 locale files.

**Problem:** `BasePagination.vue` shows page numbers and prev/next buttons but lacks "Showing X-Y of Z" context, page size selector, and mobile-optimized display.

### Affected Files

| File | Role |
|------|------|
| `src/components/base/BasePagination.vue` | Shared pagination component |
| `src/composables/usePagination.ts` | Pagination composable |

### Implementation Plan

**16.1 — Add result count text:** "Showing 1-20 of 150" below or above pagination buttons.

**16.2 — Mobile-optimize:** On narrow screens, show only prev/next + current page indicator instead of all page numbers.

**16.3 — (Optional) Page size selector:** Allow users to choose 10/20/50 items per page.

### Effort: 1-2 hours | Impact: Low-Medium

---

## 17. Public Stats API Endpoint (Backend) — DONE

> **Status:** Completed. `GET /public/stats` returns `{ member_count, post_count, sig_count }` with 5-minute in-memory cache, no auth required. 3 backend tests added.

**Problem:** The admin dashboard has stats (user/post/SIG counts) but they're admin-only. The home page needs public-accessible community stats for both authenticated and unauthenticated users.

### Affected Files

| File | Role |
|------|------|
| `backend/app/api/v1/endpoints/admin.py:15-20` | Existing admin-only stats |
| `backend/app/repositories/dashboard_repo.py` | Has all count functions |

### Implementation Plan

Create a lightweight public endpoint:

```python
# app/api/v1/endpoints/public.py (new file)
@router.get("/stats")
async def get_public_stats(conn=Depends(get_connection)):
    return {
        "member_count": await dashboard_repo.get_user_count(conn),
        "post_count": await dashboard_repo.get_post_count(conn),
        "sig_count": await dashboard_repo.get_sig_count(conn),
    }
```

Register in the API router under `/public/stats`. No authentication required.

**Cache consideration:** Add a 5-minute in-memory cache since stats don't change frequently.

### Effort: 30 min | Impact: Enables Home Page Enhancement (Section 4)

---

## 18. User Preferences API (Backend) — DONE

> **Status:** Completed (2026-03-12). Separate `user_preferences` table (Alembic migration), `preferences_repo.py` with upsert, `services/preferences.py`, endpoints `GET/PUT /users/me/preferences`. `GET /users/me` now includes preferences in response. 14 new backend tests.

**Problem:** No backend support for storing user preferences (theme, language, notification settings). All preferences are currently client-side only (localStorage).

### Implementation Plan

**Step 1 — Create `user_preferences` table:**

```sql
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(10) DEFAULT 'light',
    language VARCHAR(10) DEFAULT 'en',
    notify_mentions BOOLEAN DEFAULT TRUE,
    notify_replies BOOLEAN DEFAULT TRUE,
    notify_sig_posts BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Step 2 — Create endpoint:** `GET/PUT /users/me/preferences`

**Step 3 — Return preferences in auth response** so the frontend can apply them on login.

### Effort: 3-4 hours | Impact: Medium (enables i18n, dark mode, notification control)

---

## 19. Search Suggestions API (Backend) — DONE

> **Status:** Completed (2026-03-12). `GET /posts/suggestions?q=&limit=` endpoint with ILIKE on post titles and keyword array. Returns `{ posts: [{id, title}], keywords: [] }`. 10 new backend tests.

**Problem:** No autocomplete/suggestions endpoint exists. Users must type full queries and wait for results.

### Implementation Plan

Create lightweight suggestion endpoints:

```python
@router.get("/posts/suggestions")
async def search_suggestions(q: str = Query(min_length=2), limit: int = 5):
    # Return matching post titles and keywords using ILIKE or trigram similarity
    ...
```

Use PostgreSQL `pg_trgm` extension for fuzzy matching if available, otherwise simple `ILIKE '%query%'`.

### Effort: 2-3 hours | Impact: Medium (better search UX)

---

## 20. SIG Members Pagination — DONE

> **Status:** Completed (2026-03-12). Backend already supported `offset`/`limit`. Frontend `SigMembersView` now uses `usePagination` composable (PAGE_SIZE=20) + `BasePagination` component. `getSigMembers()` API updated with optional `{ offset, limit }` params. 5 new frontend tests.

**Problem:** `SigMembersView.vue` loads **all members at once** via `getSigMembers()` without pagination. This works for small SIGs but will cause performance issues as membership grows.

### Affected Files

| File | Role |
|------|------|
| `src/views/sigs/SigMembersView.vue:44` | Frontend — fetches all members |
| `backend/app/api/v1/endpoints/sigs.py` | Backend — members endpoint |

### Implementation Plan

1. Add `page` and `page_size` query params to the backend members endpoint
2. Return paginated response with `total` and `items`
3. Use `usePagination` composable in `SigMembersView.vue`

### Effort: 1-2 hours | Impact: Medium (scalability)

---

## Priority Order

| Priority | Task | Effort | Impact | Scope |
|----------|------|--------|--------|-------|
| 1 | **#7** Silent error handling → toasts | 1-2h | High | Frontend |
| 2 | **#13** Page transition CSS | 10 min | Low | Frontend |
| 3 | **#8** Confirmation dialogs (SIG member/leave) | 30 min | Medium | Frontend |
| 4 | **#12** Empty state consistency | 30 min | Low | Frontend |
| 5 | **#9** Image lazy loading + fallbacks | 1h | Medium | Frontend |
| 6 | **#11** Accessibility (ARIA) improvements | 1-2h | High | Frontend |
| 7 | **#17** Public stats API | 30 min | Medium | Backend |
| 8 | **#3** Forum post card richer preview | 2-4h | High | Frontend |
| 9 | **#5** Post-level reactions | 6-10h | High | Full-stack |
| 10 | **#4** Home page enhancement | 4-8h | High | Frontend |
| 11 | **#10** Breadcrumb navigation | 2-3h | Medium | Frontend |
| 12 | **#14** Responsive breakpoint gaps | 1-2h | Medium | Frontend |
| 13 | **#15** Forum search UX (debounce) | 1h | Medium | Frontend |
| 14 | **#16** Pagination enhancements | 1-2h | Low-Medium | Frontend |
| 15 | **#20** SIG members pagination | 1-2h | Medium | Full-stack |
| 16 | **#18** User preferences API | 3-4h | Medium | Backend |
| 17 | **#19** Search suggestions API | 2-3h | Medium | Backend |
| 18 | **#6** i18n and language switcher | 30-50h | High | Full-stack |

---

## General Guidelines

- **One PR per task** (or per sub-task for larger items)
- **Branch naming:** `feat/ux-error-toasts`, `feat/ux-post-reactions`, `fix/ux-a11y-aria`, etc.
- **Test coverage:** Add or update Vitest tests for any new components or changed behavior
- **Mobile responsiveness:** All changes must work on screens down to 375px width
- **Accessibility:** Maintain keyboard navigation and ARIA attributes
- **No Chinese in UI:** All user-facing text must be in English (translations come later via i18n)
- **Use existing patterns:** The codebase has `getErrorMessage()`, `useToastStore()`, `usePagination()`, `BaseModal`, `EmptyState`, `BaseBreadcrumb` — use them instead of creating new utilities
- **TypeScript:** Avoid `any` — use proper types. Use `e: unknown` in catch blocks
