# Frontend Performance Audit

Date: 2026-03-07

## HIGH Priority

### 1. Large Bundle Size — No Code Splitting
- **Issue:** All views are eagerly imported in the router, meaning the entire application is loaded upfront. Users downloading the initial bundle get all admin views, form builder, TipTap editor, etc. even if they never visit those pages.
- **Impact:** Slow initial load, especially on mobile/slow connections.
- **Fix:** Use dynamic imports in router: `component: () => import('@/views/admin/UsersView.vue')` for all routes. This enables Vite's automatic code splitting.

### 2. TipTap Editor Bundle Weight
- **Issue:** TipTap with all extensions (StarterKit, Table, Link, etc.) adds ~200KB+ to the bundle. It's loaded even on pages that don't use the editor.
- **Fix:** Lazy-load the TipTap component using `defineAsyncComponent()` or dynamic import in the parent view.

### 3. No Image Optimization
- **Issue:** User avatars and uploaded images are served at full resolution without any resizing, compression, or responsive `srcset`. Large avatars (e.g., 2MB photos) are loaded at 32x32px display size.
- **Fix:** Generate thumbnail variants on upload (backend), serve appropriate sizes via query params, use `loading="lazy"` on images below the fold.

## MEDIUM Priority

### 4. Redundant API Calls on Navigation
- **Issue:** Views fetch data on every `onMounted`, even when navigating back to a previously loaded page. No client-side caching strategy exists.
- **Fix:** Implement stale-while-revalidate pattern in Pinia stores, or use `keepAlive` on frequently revisited routes.

### 5. Unoptimized Re-renders in List Views
- **Issue:** Large list views (forum posts, admin users) re-render the entire list when any item changes. No virtual scrolling for long lists.
- **Fix:** Use `v-memo` for expensive list items, or integrate a virtual scroll library (e.g., `vue-virtual-scroller`) for lists > 50 items.

### 6. DOMPurify Loaded Globally
- **Issue:** DOMPurify (~15KB) is imported in components that render HTML content. If not tree-shaken properly, it may be included in the main bundle.
- **Fix:** Ensure DOMPurify is only imported in components that use `v-html`, and consider lazy-loading those components.

### 7. No Prefetching for Likely Navigation
- **Issue:** When a user is on the forum list, clicking a post requires a full round-trip to fetch post data. No prefetching on hover.
- **Fix:** Use `router-link` with `prefetch` or implement hover-based data prefetching for likely navigation targets.

## LOW Priority

### 8. CSS Bundle — Unused Tailwind Classes
- **Issue:** Tailwind v4 should handle purging automatically, but verify that the production build doesn't include unused utility classes from third-party component examples or commented-out code.
- **Fix:** Audit production CSS bundle size and ensure Tailwind's content paths are correctly configured.

### 9. Font Loading Strategy
- **Issue:** No explicit font loading strategy (preload, font-display). May cause FOUT (Flash of Unstyled Text) or FOIT (Flash of Invisible Text).
- **Fix:** Add `font-display: swap` and preload critical fonts.

### 10. No Service Worker / Offline Support
- **Issue:** The app has no service worker for caching static assets. Every visit requires downloading all assets.
- **Fix:** Consider adding a basic service worker for static asset caching (low priority for an academic platform).
