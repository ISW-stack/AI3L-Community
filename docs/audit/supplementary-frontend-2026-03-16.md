# Supplementary Frontend Audit Report

> Date: 2026-03-16 | Scope: Areas not covered in initial audit | Total: 27 new issues

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **High** | 1 | N-U09 |
| **Medium** | 14 | N-U01–N-U06, N-U12, N-U15–N-U17, N-U21, N-U23–N-U25 |
| **Low** | 12 | N-U07, N-U08, N-U10, N-U13, N-U14, N-U18–N-U20, N-U22, N-U26–N-U28 |

---

## High Severity

### N-U09: TiptapEditor does not destroy editor on unmount — memory leak

- **Location**: `frontend/src/components/TiptapEditor.vue:41-55`
- **Category**: Performance / Bug
- **Description**: No `onUnmounted(() => editor.value?.destroy())` call. Each mount/unmount cycle of TiptapEditor leaks an entire ProseMirror instance (DOM nodes, extensions, event listeners).
- **Impact**: Memory leak on repeated navigation to/from post create/edit pages.
- **Suggested fix**: Add `onUnmounted(() => { editor.value?.destroy() })`.

---

## Medium Severity

### N-U01: `getCookie` regex does not escape cookie name

- **Location**: `frontend/src/composables/api.ts:8`
- **Category**: Security
- **Description**: `new RegExp('(^| )' + name + '=([^;]+)')` — name not regex-escaped. Latent injection vector if reused with special characters.
- **Suggested fix**: Escape `name` before embedding in regex.

### N-U02: `useFormResponseDraft` never cleans up on unmount

- **Location**: `frontend/src/composables/useFormResponseDraft.ts`
- **Category**: Bug / Performance
- **Description**: No `onUnmounted` to call `stopAutoSave()`. Relies entirely on consumer (`useFormSubmit`). Watcher and debounce timer leak if consumer fails to clean up.
- **Suggested fix**: Add `onUnmounted(() => stopAutoSave())` as safety net.

### N-U03: `useWebSocket` shared visibility handler references stale closures

- **Location**: `frontend/src/composables/useWebSocket.ts:131-135`
- **Category**: Bug
- **Description**: Only first consumer's `handleVisibility` registered. After first consumer unmounts, visibility changes operate on dead WebSocket state.
- **Impact**: WebSocket reconnect failures after first consumer unmounts.
- **Suggested fix**: Use singleton WebSocket manager, not per-component closures.

### N-U04: `social.ts` returns raw AxiosResponse, not data

- **Location**: `frontend/src/api/social.ts:11-78`
- **Category**: TypeScript / Bug
- **Description**: Functions return `api.get(...)` directly (AxiosResponse), not destructured `.data`. Consumers must know to access `.data`. Inconsistent with `posts.ts`, `users.ts`, etc.
- **Suggested fix**: Destructure `{ data }` and return `data`.

### N-U05: `albums.ts` returns raw AxiosResponse, not data

- **Location**: `frontend/src/api/albums.ts:11-98`
- **Category**: TypeScript / Bug
- **Description**: Same as N-U04. Type annotations say `Album` but runtime value is `AxiosResponse<Album>`.

### N-U06: `coauthors.ts` and `citations.ts` return raw AxiosResponse

- **Location**: `frontend/src/api/coauthors.ts:4-39`, `frontend/src/api/citations.ts:4-14`
- **Category**: TypeScript / Bug
- **Description**: Same pattern. Accessed via `res.data.co_authors` / `res.data.citations` in consumers.

### N-U12: `BaseInput` generates non-unique IDs from translated labels

- **Location**: `frontend/src/components/base/BaseInput.vue:19-23`
- **Category**: Accessibility / Bug
- **Description**: `inputId` computed from `input-${props.label.toLowerCase().replace(...)}`. Two inputs with same translated label → duplicate IDs. Breaks `<label for>` associations. RegisterView has "Password" and "Confirm Password" which could collide in some locales.
- **Suggested fix**: Use `useId()` (Vue 3.5+) or counter-based unique ID.

### N-U15: ProfileView `saveProfile` sends empty strings as `undefined` — cannot clear fields

- **Location**: `frontend/src/views/ProfileView.vue:174-179`
- **Category**: Bug
- **Description**: `bio: bio.value || undefined` — empty string becomes `undefined` → field omitted → backend keeps old value. Users cannot clear bio/affiliation/ORCID. **Pairs with backend N-B10.**
- **Suggested fix**: Send `null` explicitly to signal "clear": `bio: bio.value.trim() || null`.

### N-U16: `usePostDetail` auth options not reactive

- **Location**: `frontend/src/composables/usePostDetail.ts:58-66`
- **Category**: Bug
- **Description**: Auth is plain object (not refs), captured at call time. If session expires mid-view, `canModify`/`canReport` remain based on stale values.
- **Suggested fix**: Accept auth store directly or use reactive refs.

### N-U17: `loadCaptcha` in auth views has no error handling

- **Location**: `LoginView.vue:34-38`, `RegisterView.vue:41-46`, `GuestLoginView.vue:27-32`
- **Category**: Bug
- **Description**: No try/catch around `getCaptcha()`. If captcha API fails, form renders without captcha image, no error shown, login/register impossible.
- **Suggested fix**: Wrap in try/catch; show error or retry button.

### N-U21: `app.config.errorHandler` swallows component rendering errors

- **Location**: `frontend/src/main.ts:18-22`
- **Category**: Bug
- **Description**: Global handler catches ALL Vue errors, shows generic toast. Critical rendering errors reduced to toast while broken component tree remains. `useToastStore()` could also throw during early init.
- **Suggested fix**: Add `<ErrorBoundary>` for critical views; guard `useToastStore()`.

### N-U23: `renderMentions` operates on raw HTML — injection risk

- **Location**: `frontend/src/utils/html.ts:69-81`
- **Category**: Security
- **Description**: Regex replaces `@username` in raw HTML strings. Can match inside HTML attributes (e.g., `<a href="mailto:@admin">`), injecting `<span>` into attributes → corrupted HTML, potential XSS.
- **Suggested fix**: Parse to DOM tree first, apply replacement only on text nodes.

### N-U24: `/forms/:formId` route has no `requiresAuth` meta

- **Location**: `frontend/src/router/index.ts:251-254`
- **Category**: Security / Bug
- **Description**: Route has no `meta` at all. Unauthenticated users can navigate to form page, see loading skeleton, get API errors instead of clean redirect.
- **Suggested fix**: Add `meta: { requiresAuth: true }`.

### N-U25: All 17 locale bundles eagerly loaded in main bundle

- **Location**: `frontend/src/locales/index.ts:2-18`
- **Category**: Performance
- **Description**: All 17 locale files statically imported. Each is tens of KB. Users typically use 1 locale but download all 17.
- **Impact**: Significant initial bundle size increase.
- **Suggested fix**: Use `vue-i18n` lazy loading with dynamic `import()` for non-default locales.

---

## Low Severity

### N-U07: `recommendations.ts` returns raw AxiosResponse
- **Location**: `frontend/src/api/recommendations.ts:4-9`
- Same pattern as N-U04.

### N-U08: `Question.type` is `string` instead of union type
- **Location**: `frontend/src/types/form.ts:8`
- No compile-time protection against invalid question types.

### N-U10: `setContent` uses double-cast workaround
- **Location**: `frontend/src/components/TiptapEditor.vue:62-63`
- `false as unknown as SetContentOptions` papers over API mismatch.

### N-U13: `useInfiniteScroll` observer not re-created on ref change
- **Location**: `frontend/src/composables/useInfiniteScroll.ts:16-27`
- After `v-if` toggle, sentinel changes but observer watches old element.

### N-U14: NotificationsView `unreadCount` drifts from store
- **Location**: `frontend/src/views/NotificationsView.vue:32,56,71,83`
- Local count and store count diverge after mark-all-read. Navbar badge stale.
- **Suggested fix**: Use `notificationStore.markAllRead()` instead of direct API call.

### N-U18: PostCreateView draft key shared for all general posts
- **Location**: `frontend/src/views/forum/PostCreateView.vue:47`
- Key `ai3l_post_draft_general` shared across all non-SIG posts. Old draft silently restored.

### N-U19: ForumView `isSearchLoading` can get stuck
- **Location**: `frontend/src/views/forum/ForumView.vue:250-258`
- If `immediateSearch` fires after `onSearchInput` sets loading=true, debounce timer cleared, `.finally()` never runs.

### N-U20: Redundant totalPages computation in useFormResponseViewer
- **Location**: `frontend/src/composables/useFormResponseViewer.ts:120`
- Manual `Math.ceil` when `usePagination` already computes it.

### N-U22: PostCard reaction rollback doesn't restore pre-click state
- **Location**: `frontend/src/components/PostCard.vue:104-131`
- On error, sets `localReactions = null` instead of saving/restoring pre-click state.

### N-U26: BaseModal uses duplicate `id="modal-title"` with stacked modals
- **Location**: `frontend/src/components/base/BaseModal.vue:145`
- Hardcoded ID → duplicate when multiple modals open. Screen readers may announce wrong title.

### N-U27: Locale sync may override recent guest choice on login
- **Location**: `frontend/src/composables/useLocale.ts:31-43`
- DB `preferred_language` silently overrides session locale after login.

### N-U28: Minor cookie regex edge case
- **Location**: `frontend/src/composables/api.ts:8`
- `(^| )` prefix misses cookies without space after semicolon. Nearly zero risk in practice.
