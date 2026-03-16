# UI/UX Audit Report

> Date: 2026-03-16 | Scope: Vue 3 + TypeScript + Tailwind CSS v4 Frontend | Total: 28 issues

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| **High** | 3 | U01, U02, U03 |
| **Medium** | 11 | U04–U14 |
| **Low** | 14 | U15–U28 |

---

## High Severity

### U01: QA "Ask Question" routes to non-existent `/qa/create`

- **Location**: `frontend/src/views/qa/QAListView.vue:54, 83`
- **Category**: Usability
- **Description**: `goToCreate()` pushes to `/qa/create`, but the router defines `/qa/ask`. The EmptyState component's `action-to` also uses `/qa/create`. Both paths lead to 404.
- **Impact**: QA question creation is completely broken from the QA list page.
- **Suggested fix**: Change both references to `/qa/ask`.

### U02: `v-html` without DOMPurify in PostDetailView

- **Location**: `frontend/src/views/forum/PostDetailView.vue:231`
- **Category**: Usability / Security
- **Description**: `<div v-if="seg.type === 'html'" v-html="seg.content">` renders HTML without `DOMPurify.sanitize()`. All other `v-html` usages go through DOMPurify, but this one does not.
- **Impact**: Defense-in-depth XSS risk if server-side sanitization has a gap.
- **Suggested fix**: Change to `v-html="DOMPurify.sanitize(seg.content)"`.

### U03: Missing `autocomplete` attributes on all form inputs

- **Location**: `LoginView.vue:105-127`, `RegisterView.vue:137-204`, `GuestLoginView.vue:91-102`, `PasswordChangeForm.vue`
- **Category**: Accessibility
- **Description**: No `<input>` in the application uses `autocomplete` attributes. Password managers cannot auto-fill correctly.
- **Impact**: WCAG compliance failure; impaired usability for users relying on password managers or autofill.
- **Suggested fix**: Add `autocomplete="username"`, `autocomplete="current-password"` / `autocomplete="new-password"` to appropriate inputs.

---

## Medium Severity

### U04: Missing `role="tabpanel"` on tab content regions

- **Location**: `ProfileView.vue:272-460`, `FriendsView.vue:182-215`, `NotificationsView.vue:166-198`, `UserProfileView.vue:228-255`
- **Category**: Accessibility
- **Description**: Tabs use `role="tablist"` and `role="tab"` but no content panels have `role="tabpanel"`, `aria-labelledby`, or `id`. Screen readers cannot navigate tab content.
- **Suggested fix**: Add `<div role="tabpanel" :id="'panel-'+tabName" :aria-labelledby="'tab-'+tabName">`.

### U05: Hardcoded English strings bypass i18n

- **Location**: `PostCard.vue:196` ("Question"), `PostDetailView.vue:346` (comment pluralization), `PostDetailView.vue:287,294` ("self", "by")
- **Category**: i18n
- **Description**: Several strings use raw English text instead of `t()` calls. Comment pluralization uses JS ternary instead of vue-i18n plural forms.
- **Suggested fix**: Replace with `t()` calls and i18n plural syntax.

### U06: `<html lang="zh-TW">` hardcoded despite 17-language support

- **Location**: `frontend/index.html:2`
- **Category**: Accessibility / i18n
- **Description**: Screen readers announce all content as Traditional Chinese regardless of selected locale.
- **Suggested fix**: In `App.vue` or `useLocale.ts`, set `document.documentElement.lang` dynamically.

### U07: No unsaved changes warning on PostCreateView

- **Location**: `frontend/src/views/forum/PostCreateView.vue`
- **Category**: Usability
- **Description**: PostDetailView (editing) has `beforeRouteLeave` guard, but PostCreateView relies only on auto-save. Navigating away between debounce intervals loses work.
- **Suggested fix**: Add `beforeRouteLeave` guard checking non-empty title/content.

### U08: Admin "Create Account" has no password strength validation

- **Location**: `frontend/src/views/admin/UsersView.vue:159-180`
- **Category**: Usability
- **Description**: Admin create form accepts any password, while registration enforces 8+ chars with upper/lower/digit. Admins could create weak accounts.
- **Suggested fix**: Apply same password validation as registration.

### U09: FormsDirectoryView search only filters current page

- **Location**: `frontend/src/views/forms/FormsDirectoryView.vue:33-41, 51-62`
- **Category**: Usability
- **Description**: Client-side filter on `filteredForms` only applies to the current paginated page. Forms on page 2 are invisible to search on page 1.
- **Impact**: Users may think a form doesn't exist when it's on another page.
- **Suggested fix**: Send search query to server API, or fetch all forms for client-side search.

### U10: Router guard silently redirects on permission failures

- **Location**: `frontend/src/router/index.ts:283-295`
- **Category**: Usability
- **Description**: Permission-denied redirects to home with no toast or explanation. Users think the app is broken.
- **Suggested fix**: Show a toast explaining the reason, or redirect to a 403 page.

### U11: No `scrollBehavior` on router

- **Location**: `frontend/src/router/index.ts:5-266`
- **Category**: Usability
- **Description**: No scroll-to-top on route changes. After scrolling a feed and clicking a post, users land at a random scroll position.
- **Suggested fix**: Add `scrollBehavior: () => ({ top: 0 })` to `createRouter`.

### U12: Mobile menu does not trap focus

- **Location**: `frontend/src/components/AppNavbar.vue:320-493`
- **Category**: Accessibility
- **Description**: When mobile menu opens, focus is not trapped. Keyboard users can Tab into hidden desktop nav or background content.
- **Suggested fix**: Implement focus trapping or set `inert` on main content when menu is open.

### U13: Language selector on auth pages overlaps navbar

- **Location**: `LoginView.vue:72`, `RegisterView.vue:104`, `GuestLoginView.vue:55`
- **Category**: Visual / Usability
- **Description**: `absolute top-4 right-4 z-10` positions behind sticky navbar (`z-50`) on mobile/short viewports.
- **Suggested fix**: Change to `fixed top-20 right-4 z-40` or integrate into form header.

### U14: `toLocaleString()` / `toLocaleDateString()` without locale parameter

- **Location**: `PostDetailView.vue:178,420,528,628`, `SigLayout.vue:259`, `UserProfileView.vue:179`, `FormView.vue:194`, `QADetailView.vue:185`, `FormBuilderView.vue:125`
- **Category**: i18n
- **Description**: Date formatting uses browser system locale instead of app's selected locale. Japanese-language user with English OS sees English-formatted dates.
- **Suggested fix**: Create shared date utility accepting current i18n locale.

---

## Low Severity

### U15: Toast close button has hardcoded English aria-label

- **Location**: `frontend/src/components/ToastNotification.vue:31`
- **Description**: `aria-label="Dismiss notification"` bypasses i18n.

### U16: Modal close button has hardcoded English aria-label

- **Location**: `frontend/src/components/base/BaseModal.vue:152`
- **Description**: `aria-label="Close"` bypasses i18n.

### U17: NotificationBell has hardcoded English aria-label

- **Location**: `frontend/src/components/NotificationBell.vue:85`
- **Description**: `aria-label="Notifications"` bypasses i18n.

### U18: Captcha images have non-descriptive alt text, no audio alternative

- **Location**: `LoginView.vue:147`, `RegisterView.vue:224`, `GuestLoginView.vue:122`
- **Description**: `alt="captcha"` provides no useful information. No audio captcha alternative for visually impaired users.

### U19: Password toggle button positioned with magic number

- **Location**: `LoginView.vue:121`, `RegisterView.vue:160,197`
- **Description**: `top-[34px]` depends on label height. Breaks on font size changes or long translations.

### U20: Inconsistent page padding for full-width routes

- **Location**: `App.vue:34-38`, `ForumView.vue:312`, `SigLayout.vue:202`, `QAListView.vue:61`
- **Description**: Each full-width view adds its own padding (`px-4 sm:px-6 lg:px-8` vs `lg:px-layout px-4` vs `px-4`).

### U21: SkeletonLoader uses hardcoded `bg-gray-200`

- **Location**: `frontend/src/components/SkeletonLoader.vue:13-40`
- **Description**: Hardcoded color instead of semantic theme token.

### U22: NotFoundView uses hardcoded `text-gray-300`

- **Location**: `frontend/src/views/NotFoundView.vue:12-13`
- **Description**: Bypasses semantic color system.

### U23: HomeView stats show dashes instead of skeleton during load

- **Location**: `frontend/src/views/HomeView.vue:382-401`
- **Description**: `'—'` placeholders look like content, not loading indicators.

### U24: AboutView loading is plain text, not skeleton

- **Location**: `frontend/src/views/AboutView.vue:65`
- **Description**: Inconsistent with the rest of the app which uses `<SkeletonLoader>`.

### U25: SigLayout delete has no loading state on confirm button

- **Location**: `frontend/src/views/sigs/SigLayout.vue:333-334`
- **Description**: No `:loading` prop; button can be clicked multiple times.

### U26: PostCard thumbnail has no width/height — layout shift (CLS)

- **Location**: `frontend/src/components/PostCard.vue:233-239`
- **Description**: Missing dimensions cause content to jump when images load. Core Web Vitals issue.

### U27: Auth store session expiry toast is hardcoded English

- **Location**: `frontend/src/stores/auth.ts:158`
- **Description**: `'Your session has expired. Please log in again.'` bypasses i18n.

### U28: Arabic locale exists but no RTL support

- **Location**: `frontend/src/locales/ar.ts`, entire CSS
- **Category**: i18n
- **Description**: Arabic is a supported locale, but no `dir="rtl"` is set dynamically, and Tailwind has no RTL-aware utilities. Arabic users see a broken layout.
- **Suggested fix**: Add RTL support or remove Arabic until supported.

---

## Top Priority Fixes

1. **U01**: QA "Ask Question" completely broken — wrong route
2. **U02**: Missing DOMPurify on `v-html` — XSS defense-in-depth
3. **U03**: Missing `autocomplete` — password managers broken
4. **U11**: No scroll-to-top — poor navigation UX
5. **U06**: Hardcoded `lang="zh-TW"` — screen reader pronunciation broken
6. **U09**: Forms search misleading — only filters current page
7. **U10**: Silent permission redirects — confusing UX
