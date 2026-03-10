# Frontend Performance Audit

Date: 2026-03-07 (updated 2026-03-11)

## HIGH Priority

### 1. Large Bundle Size — No Code Splitting — ✅ Resolved
- **Status:** All route components use `() => import(...)` lazy loading in the router.

### 2. TipTap Editor Bundle Weight — ✅ Resolved (2026-03-11)
- **Status:** TiptapEditor is now loaded via `defineAsyncComponent()` in PostCreateView and PostDetailView. The ~200KB TipTap bundle only loads when users visit pages that use the editor.

### 3. No Image Optimization — Partially Resolved (2026-03-11)
- **Status:** Added `loading="lazy"` to all below-fold images (PostCard thumbnails, BaseAvatar, FormView/FormBuilderView banners). Server-side image resizing and responsive `srcset` remain as future improvements.

## MEDIUM Priority

### 4. Redundant API Calls on Navigation
- **Issue:** Views fetch data on every `onMounted`, even when navigating back to a previously loaded page.
- **Fix:** Implement stale-while-revalidate pattern in Pinia stores, or use `keepAlive` on frequently revisited routes.

### 5. Unoptimized Re-renders in List Views
- **Issue:** Large list views re-render the entire list when any item changes. No virtual scrolling for long lists.
- **Fix:** Use `v-memo` for expensive list items, or integrate a virtual scroll library for lists > 50 items.

### 6. DOMPurify Loaded Globally — ✅ Resolved
- **Status:** DOMPurify is imported locally in individual components, enabling proper tree-shaking.

### 7. No Prefetching for Likely Navigation
- **Issue:** No hover-based data prefetching for likely navigation targets.
- **Fix:** Consider implementing prefetch on hover for post links.

## LOW Priority

### 8. CSS Bundle — Unused Tailwind Classes
- **Issue:** Verify production build purging is working correctly with Tailwind v4.
- **Fix:** Audit production CSS bundle size.

### 9. Font Loading Strategy — ✅ Resolved
- **Status:** Using `@fontsource-variable/inter` package (imported in `main.ts`), which includes `font-display: swap` by default.

### 10. No Service Worker / Offline Support
- **Issue:** No service worker for static asset caching.
- **Fix:** Low priority for an academic platform.
