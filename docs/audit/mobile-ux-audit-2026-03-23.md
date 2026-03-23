# AI3L Community - Mobile UX Audit Report

**Date:** 2026-03-23
**Scope:** Frontend (Vue 3 + Tailwind CSS v4 + Vite)
**Method:** Static code analysis of all views, components, layouts, and styles

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 10 |
| Medium | 14 |
| Low | 8 |
| **Total** | **35** |

---

## Critical Issues

### M-C1: PhotoGrid Hover-Only Controls Invisible on Touch Devices

**File:** `src/components/albums/PhotoGrid.vue:50,61-64,72`

Photo overlay controls (filename, "Set as Cover" button) use `group-hover:opacity-100` with `opacity-0` default. On touch devices, `hover` events don't fire, making these controls **completely invisible and unreachable**.

```html
<!-- Line 61: overlay only visible on hover -->
<div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 ...">
  <!-- Line 64: filename hidden on touch -->
  <span class="opacity-0 group-hover:opacity-100 ...">{{ photo.original_filename }}</span>
  <!-- Line 72: "Set as Cover" button hidden on touch -->
  <button class="opacity-0 group-hover:opacity-100 ...">Set as Cover</button>
</div>
```

**Impact:** Mobile users cannot see photo filenames or set album covers.
**Fix:** Add `active:` or `focus-within:` states; or always show controls on small screens with `opacity-100 md:opacity-0 md:group-hover:opacity-100`.

---

### M-C2: DM View Fixed Height Breaks on Mobile Keyboards and Landscape

**File:** `src/views/DMView.vue:333`

```html
<div style="height: calc(100vh - 200px); height: calc(100dvh - 200px)">
```

- The `200px` offset is hardcoded and doesn't adapt to varying navbar heights, breadcrumbs, or page title.
- When the mobile virtual keyboard opens, `100dvh` shrinks but `200px` remains constant — the message thread and input may become too small or completely hidden.
- In landscape on notched devices (iPhone X+), available height after keyboard is minimal.

**Impact:** Users may not be able to see or type messages on mobile when keyboard is open.
**Fix:** Use a ref-based height calculation or CSS `flex-1` with `min-h-0` instead of fixed `calc()`. Consider `visualViewport` API for keyboard-aware layout.

---

### M-C3: Modal Close Button Below Minimum Touch Target

**File:** `src/components/base/BaseModal.vue:154`

```html
<button class="p-1 -m-1 text-muted hover:text-foreground text-xl leading-none transition ml-auto">
  &times;
</button>
```

With `p-1` (4px) padding on a `text-xl` character, the total touch area is approximately **28-32px** — well below the WCAG/Apple recommended **44x44px** minimum.

**Impact:** Users frequently miss the close button on mobile, leading to frustration.
**Fix:** Use `p-2.5 -m-2.5` or add explicit `min-w-[44px] min-h-[44px]` with flex centering.

---

## High Issues

### M-H1: TipTap Editor Toolbar Buttons Too Small and Crowded

**File:** `src/components/TiptapEditor.vue:223-378`

Toolbar buttons use `p-1.5` (6px padding) with `w-4 h-4` icons, resulting in ~28x28px total touch targets. Buttons are packed with only `gap-1` between them.

**Impact:** Nearly impossible to accurately tap individual formatting buttons on mobile.
**Fix:** Use `p-2.5 sm:p-1.5` for mobile-first sizing, or wrap toolbar in a horizontally scrollable container with larger touch targets.

---

### M-H2: BaseButton min-h Drops to 0 on Tablets (sm: breakpoint)

**File:** `src/components/base/BaseButton.vue:41-44`

```typescript
sm: 'px-3 py-2.5 text-xs rounded-md min-h-[36px] sm:min-h-0',
md: 'px-4 py-2.5 text-sm rounded-lg min-h-[44px] sm:min-h-0',
```

Buttons enforce 44px min-height on phones but drop to `min-h-0` at the `sm:` breakpoint (640px+). Tablets and landscape phones (641-1024px) get no minimum height guarantee — only `py-2.5` (10px) padding keeps them tappable.

**Impact:** Buttons may be too small to tap reliably on tablets.
**Fix:** Change to `min-h-[44px] lg:min-h-0` so tablets retain touch-friendly sizing.

---

### M-H3: ReactionPicker Can Overflow Off-Screen on Mobile

**File:** `src/components/ReactionPicker.vue:104-106`

```html
<div class="absolute bottom-full left-0 mb-1.5 ... z-50">
```

The emoji picker positions `left-0` from its parent. When the reaction button is near the right edge of the screen, the picker extends beyond the viewport. No `max-w-[calc(100vw-...)]` constraint exists.

**Impact:** Emoji picker is clipped or invisible on mobile.
**Fix:** Add viewport-aware positioning — detect edge proximity and flip to `right-0` when needed, or add `max-w-[calc(100vw-2rem)]` with overflow handling.

---

### M-H4: Admin Tables Require Horizontal Scrolling with No Mobile Card Fallback

**Files:**
- `src/views/admin/AuditLogsView.vue:177-178` — `min-w-[750px]`
- `src/views/admin/ReportsView.vue:136-137` — `min-w-[650px]`
- `src/views/admin/InviteCodesView.vue:245-246` — similar pattern

These tables use `overflow-x-auto` with wide `min-w-` constraints. While `UsersView` has a mobile card view, other admin tables only offer horizontal scroll.

**Impact:** Admin operations on mobile require tedious horizontal scrolling to read or act on data.
**Fix:** Add `hidden md:block` to tables and provide mobile card layouts (like UsersView already does).

---

### M-H5: Tab Navigation Padding Not Responsive (SigLayout/AlbumLayout)

**Files:**
- `src/views/sigs/SigLayout.vue:408`
- `src/views/albums/AlbumLayout.vue:381`

```html
<button class="px-6 py-3 text-sm font-medium border-b-2 whitespace-nowrap">
```

Tab items use `px-6` (24px) horizontal padding at all breakpoints. On phones < 375px, 4-5 tabs easily overflow, forcing horizontal scroll. No visual indicator (gradient fade) tells users there are more tabs.

**Impact:** Users may not discover all tabs on narrow screens.
**Fix:** Use `px-3 sm:px-6 py-2.5 sm:py-3`. Add gradient fade overlay at scroll edges (like `CategoryFilter` already does).

---

### M-H6: Alert Dismiss Button Undersized

**File:** `src/components/base/BaseAlert.vue:32-39`

```html
<button class="shrink-0 opacity-60 hover:opacity-100 transition" @click="emit('dismiss')">
  &times;
</button>
```

No padding specified — touch target is only the text character itself (~18-20px).

**Impact:** Very difficult to dismiss alerts on mobile.
**Fix:** Add `p-2 min-w-[44px] min-h-[44px] flex items-center justify-center`.

---

### M-H7: Navbar Dropdowns May Overflow on Small Phones

**File:** `src/components/AppNavbar.vue:179,233,349`

```html
class="absolute right-0 sm:left-0 sm:right-auto mt-2 w-48 max-w-[calc(100vw-2rem)] ..."
```

User dropdown is `w-56` (224px). On phones < 360px with padding, the dropdown may be partially off-screen. The `max-w-[calc(100vw-2rem)]` helps but doesn't guarantee correct left-edge alignment.

**Impact:** Dropdown content clipped on very small phones.
**Fix:** Test on 320px viewport; consider making mobile dropdowns full-width or using a bottom sheet pattern.

---

### M-H8: Form Builder Action Buttons Undersized on Mobile

**File:** `src/components/forms/QuestionEditor.vue:160-191`

```html
<button class="px-1.5 py-1 sm:px-1 sm:py-0 touch-manipulation">&uarr;</button>
```

Move/duplicate/delete buttons have only 6px horizontal + 4px vertical padding. The `touch-manipulation` class helps prevent delay but doesn't fix the tiny target size.

**Impact:** Users frequently tap the wrong action button.
**Fix:** Increase to `p-2 sm:p-1` or use icon buttons with 44px minimum.

---

### M-H9: Post/QA Card List Spacing Too Large on Mobile

**Files:**
- `src/views/forum/ForumView.vue:139-143` — `space-y-4`
- `src/views/qa/QAListView.vue:131-134` — `space-y-3`

Fixed gap sizing means only 1-2 cards are visible without scrolling on phone screens.

**Impact:** Feed browsing feels slow; users must scroll extensively.
**Fix:** Use responsive gap: `space-y-2 md:space-y-4`.

---

### M-H10: Tooltip (`title`) Attributes Not Accessible on Touch Devices

**Files:**
- `src/views/DMView.vue:311-314` — Friends-only mode explanation
- `src/components/AppNavbar.vue:321` — User display name
- Various other components

Browser-native `title` attributes do not display on touch devices. Information conveyed only through tooltips is invisible on mobile.

**Impact:** Contextual help text unreachable on mobile.
**Fix:** For critical information, use visible text, `aria-label`, or a toggle-on-tap tooltip component. Low-priority tooltips can remain as-is.

---

## Medium Issues

### M-M1: `--spacing-layout: 8rem` Not Responsive

**File:** `src/style.css:51`

The `--spacing-layout` value of 8rem (128px) is used as side padding in `SigLayout`, `AlbumLayout`, `ProfileView`, and `AdminLayout` via `lg:px-layout`. While guarded by `lg:`, on small laptops / large tablets in landscape (1024-1280px), it consumes 256px of horizontal space.

**Fix:** Consider reducing to `6rem` or defining responsive values via media queries.

---

### M-M2: DM View Sidebar Toggle Feels Janky

**File:** `src/views/DMView.vue:337-351`

Mobile DM uses `hidden md:block` / `hidden md:flex` toggling to show either the conversation list or the message thread. There is no transition animation — the panels simply show/hide.

**Fix:** Add slide transitions for the panel switch, or consider a bottom-sheet conversation picker pattern.

---

### M-M3: Floating Create Button and Back-to-Top Button Overlap

**Files:**
- `src/components/FloatingCreateButton.vue:30-31` — `bottom: max(1.5rem, env(safe-area-inset-bottom))`
- `src/components/BackToTop.vue:54-56` — `bottom: max(2rem, calc(env(safe-area-inset-bottom) + 0.5rem))`

Both are fixed-position at the bottom-right corner with `z-40`. They will overlap on pages where both are visible.

**Fix:** Offset BackToTop vertically when FloatingCreateButton is present, or stack them vertically.

---

### M-M4: BaseModal Size Classes Can Exceed Phone Width

**File:** `src/components/base/BaseModal.vue:34-42`

```typescript
lg: 'max-w-lg',    // 32rem = 512px
xl: 'max-w-2xl max-h-[80vh] overflow-y-auto',
```

On 375px phones, `max-w-lg` (512px) plus `p-4` padding means the modal is constrained by `max-w-[calc(100vw-2rem)]` but internal content may still overflow.

**Fix:** Add `w-full` to all size classes on mobile; test form-heavy modals on 320px viewports.

---

### M-M5: Captcha Image Too Small on Mobile

**File:** `src/views/LoginView.vue:169-176`

Captcha image uses `h-10` (40px) at all breakpoints. On narrow phones, the captcha text may be hard to read.

**Fix:** Use `h-12 sm:h-10` for slightly larger captcha on mobile.

---

### M-M6: Form Validation Error Text Too Small

**File:** `src/views/forms/FormView.vue:540`

```html
<p class="text-xs text-danger-600 mt-1">
```

Error messages at `text-xs` (12px) are below the recommended 14px minimum for readable text.

**Fix:** Use `text-sm` for error messages consistently.

---

### M-M7: Rating Buttons Shrink Below Touch Target

**File:** `src/views/forms/FormView.vue:389-413`

```html
:class="[ratingCount(q) > 7 ? 'w-8 h-8 text-xs' : 'w-10 h-10', ...]"
```

When a rating scale has > 7 options, buttons shrink to 32x32px.

**Fix:** Allow horizontal scroll for many options rather than shrinking buttons below 40px.

---

### M-M8: Language Switcher Dropdown Too Tall on Mobile

**File:** `src/components/LanguageSwitcher.vue:99-173`

Dropdown uses `max-h-80` (320px), which occupies most of a 640px phone screen.

**Fix:** Use `max-h-60 sm:max-h-80` or a bottom-sheet pattern on mobile.

---

### M-M9: Bulk Action Bar Wraps Unpredictably

**File:** `src/views/admin/UsersView.vue:296-317`

Multiple interactive elements (selected count, dropdown, apply button, clear button) in a `flex-wrap` container create unpredictable wrapping on narrow screens.

**Fix:** Stack vertically on mobile: `flex-col sm:flex-row`.

---

### M-M10: Audit Log Filter Bar Takes Too Much Vertical Space

**File:** `src/views/admin/AuditLogsView.vue:115-166`

Three date/user filter inputs stack vertically on mobile, consuming significant screen real estate before the actual log entries.

**Fix:** Collapse filters behind a toggle button on mobile (e.g., "Filters" button that expands/collapses).

---

### M-M11: Keyword Badges Can Overflow on Narrow Screens

**File:** `src/views/forum/PostDetailView.vue:284-286`

Keywords can be up to 50 characters. A single long keyword badge on a 320px screen will overflow.

**Fix:** Add `max-w-full truncate` to individual badges.

---

### M-M12: Form Builder Toolbar Wraps Unpredictably

**File:** `src/views/forms/FormBuilderView.vue:223-269`

Action buttons use `flex items-center gap-2 flex-wrap` — on narrow mobile screens, buttons wrap to multiple lines making the toolbar very tall.

**Fix:** Use a horizontal scroll container or overflow menu for mobile.

---

### M-M13: Raw `<textarea>` Elements Cause iOS Zoom

**Files:**
- `src/views/forum/PostDetailView.vue:480,541,661`
- `src/views/forum/PostCreateView.vue:283`

Direct `<textarea>` elements use `text-sm` (14px) instead of `text-base` (16px). iOS auto-zooms on focus for inputs with font-size < 16px.

**Fix:** Use `BaseTextarea` component (which has `text-base md:text-sm`) or add `text-base md:text-sm` directly.

---

### M-M14: QuestionEditor Collapse Toggle Button Too Small

**File:** `src/components/forms/QuestionEditor.vue:135-144`

Collapse button uses `text-sm px-1` with only a triangle symbol. No explicit height, resulting in a tiny touch target.

**Fix:** Add `p-2 min-w-[36px] min-h-[36px]` with centering.

---

## Low Issues

### M-L1: `scroll-padding-top` Not Set for Sticky Navbar

**File:** `src/style.css:61-64`

No `scroll-padding-top` to account for the sticky navbar (64px). Anchor-linked content scrolls behind it.

**Fix:** Add `scroll-padding-top: 5rem` to `html`.

---

### M-L2: Notification Badge Font Size Very Small

**File:** `src/components/NotificationBell.vue:97` and `AppNavbar.vue:306`

Badge uses `text-[10px]` with `h-[18px]` — borderline readable on high-DPI screens but very small on standard mobile displays.

**Fix:** Use `text-[11px]` minimum or `text-xs` (12px).

---

### M-L3: No Landscape-Specific Adjustments

No `@media (orientation: landscape)` queries exist. The DM view, modals, and form views can become cramped in landscape orientation on phones.

**Fix:** Test key views in landscape; consider reducing vertical padding or using horizontal layouts for DM in landscape.

---

### M-L4: `inputmode` Missing on Numeric Inputs

**File:** `src/components/forms/QuestionEditor.vue:258,332,345,380`

Number inputs (`type="number"`) don't specify `inputmode="numeric"`. Some mobile browsers may show a full keyboard instead of the numeric pad.

**Fix:** Add `inputmode="numeric"` to all `type="number"` inputs.

---

### M-L5: Photo Grid Gap Too Large on Very Small Screens

**File:** `src/components/albums/PhotoGrid.vue:38`

`gap-3` (12px) with 2-column grid on a 320px phone leaves only ~148px per image.

**Fix:** Use `gap-1.5 sm:gap-3`.

---

### M-L6: Login Form Width on Ultra-Small Devices

**File:** `src/views/LoginView.vue:112`

`max-w-md` (448px) with double padding layers (`p-4` container + `p-4 sm:p-6` card) consumes significant space on 320px phones.

**Fix:** Use `p-3 sm:p-4` for the outer container on small screens.

---

### M-L7: ConversationList Avatar Sizing Counterintuitive

**File:** `src/components/dm/ConversationList.vue:73`

Avatars are `w-11 h-11 sm:w-10 sm:h-10` — larger on mobile, smaller on tablet. This is the opposite of typical responsive patterns.

**Fix:** Use consistent sizing, or if intentionally larger for touch, document the rationale.

---

### M-L8: File Delete Button in Form View Lacks Padding

**File:** `src/views/forms/FormView.vue:504-511`

Remove file button is text-only (`text-sm font-medium`) with no padding — small touch target for a destructive action.

**Fix:** Add `px-2 py-1` padding around the remove button.

---

## Positive Patterns (Already Done Well)

- **Viewport meta tag:** Correctly includes `viewport-fit=cover` for notch devices
- **Safe area insets:** `body` has `env(safe-area-inset-left/right)` padding; navbar has `env(safe-area-inset-top)`
- **BaseInput/BaseTextarea:** Use `text-base md:text-sm` to prevent iOS zoom (good pattern)
- **Mobile hamburger menu:** AppNavbar has a proper mobile menu with `lg:hidden` toggle
- **Mobile pagination:** `BasePagination` shows simplified prev/next on small screens
- **UsersView:** Has dedicated mobile card layout (`hidden md:block` table + mobile cards)
- **DM mobile toggle:** Conversation list / thread toggle works at `md:` breakpoint
- **`touch-manipulation`:** Applied to key interactive elements to reduce 300ms tap delay
- **FloatingCreateButton:** Properly accounts for safe area insets

---

## Recommended Priority for Fixes

### Phase 1 — Critical (fix immediately)
1. **M-C1** PhotoGrid hover-only controls — add touch-friendly visibility
2. **M-C2** DM view height — replace `calc()` with flexbox layout
3. **M-C3** Modal close button — increase touch target

### Phase 2 — High (next sprint)
4. **M-H1** TipTap toolbar — mobile-first button sizing
5. **M-H2** BaseButton tablet min-height
6. **M-H3** ReactionPicker viewport-aware positioning
7. **M-H4** Admin tables — add mobile card views
8. **M-H5** Tab nav responsive padding + scroll indicators
9. **M-H6** Alert dismiss button sizing
10. **M-H7** Navbar dropdown edge handling

### Phase 3 — Medium (backlog)
11. Remaining Medium items (M-M1 through M-M14) — batch by component area

### Phase 4 — Low (nice to have)
12. Low items as time permits
