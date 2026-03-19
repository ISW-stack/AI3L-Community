# UI Layout Fixes Specification

**Date:** 2026-03-19
**Scope:** 5 layout and responsiveness bugs across Forms, DM, and SIGs views
**Target reader:** Beginner contributors who are familiar with Vue 3 and Tailwind CSS
**Working directory:** `frontend/src/`

---

## Global CSS context you must know before editing

Before reading each fix, note that `frontend/src/style.css` already contains:

```css
html, body {
  overflow-y: scroll;
  scrollbar-gutter: stable;
}
```

This means the page always reserves a scrollbar gutter, and the viewport width never changes due to a scrollbar appearing or disappearing. Any root cause that mentions "scrollbar width change" is therefore NOT applicable to this project.

---

## Table of Contents

1. [Issue 1: Forms search empty state causes title and button to jump](#issue-1)
2. [Issue 2: DM container shifts when the message input textarea grows](#issue-2)
3. [Issue 3: SIG search empty state causes title and button to jump](#issue-3)
4. [Issue 4: DM messages overflow the screen edges on mobile](#issue-4)
5. [Issue 5: SIG page title and Create SIG button overlap on mobile](#issue-5)

---

<a id="issue-1"></a>
## Issue 1: Forms Search Empty State Causes Title and Button to Jump

### File to edit

`frontend/src/views/forms/FormsDirectoryView.vue`

### What the bug looks like

When a user types a search query that returns no forms, the page height drops significantly (the card grid disappears and is replaced by the much shorter `EmptyState` component). If the user had previously scrolled down to see more cards, the browser clamps the scroll position to the new maximum (which is near zero), causing the entire page to snap back to the top. The title and "Create Form" button appear to jump to a different position.

### Root cause

The results container on line 102 has `min-h-[200px]`. The `EmptyState` component renders with `py-12` (96px top and bottom padding), an icon, and two lines of text — total height is roughly 200px, which barely fills the container. When a search previously showed many cards (the grid could easily be 600px or taller), and a new search returns zero results, the page height drops by roughly 400px. If the user was scrolled down 200px, the scroll position becomes invalid and the browser resets it to 0, making the header appear to jump.

The root `<div>` of this view (line 80) is a plain `<div>` with no height-related classes. It does not fill the `<main>` element's height the way the SIGs view does. This means the view can shrink to a small height when results are empty.

### Fix

**Step 1.** On **line 80**, add `flex-1` to the root element so this view always fills the full height of its flex parent (`<main>`), the same way `SigsDirectoryView` does. This prevents the view from collapsing to a small height when results are empty.

Find this line:
```html
<template>
  <div>
```

Replace with:
```html
<template>
  <div class="flex-1 flex flex-col">
```

**Step 2.** On **line 102**, change `min-h-[200px]` to `min-h-[400px]`. This gives the results area a taller minimum height, so even with `EmptyState` rendered, the page does not collapse dramatically.

Find this line:
```html
    <div v-else class="min-h-[200px]">
```

Replace with:
```html
    <div v-else class="min-h-[400px]">
```

### Why these two changes together

`flex-1` on the root makes the view always occupy the full available height of `<main>`, so the page height never drops below the viewport when results are empty. `min-h-[400px]` ensures the results area has a reasonable minimum, preventing jarring content collapse.

### How to verify

1. Navigate to `/forms`.
2. Wait for the form cards to load and appear.
3. Scroll down if there are multiple rows of cards.
4. Type a search query that matches no forms (for example: `xyznonexistent`).
5. The page should not snap the title and button to a different vertical position. The empty state message should appear without the page jumping.
6. Clear the search and confirm the grid reappears without a layout jump.

---

<a id="issue-2"></a>
## Issue 2: DM Container Shifts When the Message Input Textarea Grows

### Files to edit

- `frontend/src/views/DMView.vue`
- `frontend/src/components/dm/MessageThread.vue`

### What the bug looks like

When the user sends or receives many messages, or when the user types a multi-line message causing the textarea to grow, the message thread area does not scroll correctly. New messages may push the layout instead of scrolling within the thread. The overall DM box can appear to shift vertically.

### Root cause

This is a well-known CSS flexbox issue. When you nest flex containers and want an inner element to scroll with `overflow-y: auto`, the browser must know the element has a **definite height** that is smaller than its content. By default, every flex item has `min-height: auto`, which means "be at least as tall as my content". This overrides the constraint that the flex parent is trying to impose, so `overflow-y: auto` never activates — the element grows to fit all content instead of scrolling.

The fix is to add `min-h-0` (which sets `min-height: 0`) to each flex item that needs to be scroll-constrained. This tells the browser: "this element is allowed to be smaller than its content, so constrain it and scroll."

In this project, the affected elements are:

- **Right panel** in `DMView.vue` (line 342): a `flex-1 flex flex-col` element. Without `min-h-0`, it can grow beyond the outer container's fixed height.
- **MessageThread** root div (line 202 of `MessageThread.vue`): a `flex-1 overflow-y-auto` element. Without `min-h-0`, it does not scroll — it grows to show all messages, pushing other elements out of place.

### Fix

**Step 1.** In `DMView.vue`, on **line 342**, add `min-h-0` to the right panel div.

Find this line:
```html
      <div
        class="flex-1 flex flex-col min-w-0"
        :class="{ 'hidden sm:flex': !dmStore.activeConversationId && !activeOtherUserId }"
      >
```

Replace with:
```html
      <div
        class="flex-1 flex flex-col min-w-0 min-h-0"
        :class="{ 'hidden sm:flex': !dmStore.activeConversationId && !activeOtherUserId }"
      >
```

**Step 2.** In `MessageThread.vue`, on **line 202**, add `min-h-0` to the scroll container.

Find this line:
```html
    class="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative"
```

Replace with:
```html
    class="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative min-h-0"
```

### How to verify

1. Navigate to `/messages` and open a conversation that has many messages (or send enough messages to fill the visible area).
2. Confirm the message thread area scrolls internally — the "Messages" title at the top and the input area at the bottom should remain fixed.
3. Type a long multi-line message (press Shift+Enter to add lines). The textarea should grow upward and the message thread area should shrink to accommodate, without the overall DM box shifting.
4. Confirm the "Load older messages" button and the sticky "New message" hint button appear correctly.

---

<a id="issue-3"></a>
## Issue 3: SIG Search Empty State Causes Title and Button to Jump

### File to edit

`frontend/src/views/sigs/SigsDirectoryView.vue`

### What the bug looks like

When a user types a search query that matches no SIGs, the title ("Special Interest Groups") and the "Create SIG" button appear to jump. The same scroll-position-reset mechanism as Issue 1 is responsible here.

### Root cause

The SIG search is **client-side** (line 24–32: `filteredSigs` is a computed property that filters in memory). When many SIG cards are shown, the grid grows taller than the viewport, making the page scrollable. The user may have scrolled down. When they type a search query that matches nothing, `filteredSigs` becomes an empty array immediately and synchronously. Vue removes the grid from the DOM and inserts `EmptyState`. The page height drops instantly. If the browser's current scroll position exceeds the new page height, the scroll position is clamped to zero, causing the header to appear to jump.

The inner content container at line 63 already has `min-h-[400px]`, but the problem is that the SIG card **grid can grow much taller than 400px** without being constrained, because the container has `flex-1` and `flex flex-col` but no `overflow: hidden` or `max-height`. The grid overflows the container, making the page taller than the viewport and enabling page-level scroll. When the grid disappears, the page height collapses and the scroll resets.

### Fix

The most targeted fix is to prevent the SIG card grid from overflowing to page level. Instead, make the content area itself scroll internally when the grid is taller than the allocated space. This eliminates page-level scroll for SIG cards and prevents the scroll-position-reset problem.

**Step 1.** On **line 63**, add `max-h-[60vh] overflow-y-auto min-h-0` to the content area, and remove `flex-1`.

Find this line:
```html
    <div class="flex-1 w-full flex flex-col min-h-[400px]">
```

Replace with:
```html
    <div class="w-full flex flex-col min-h-[400px] max-h-[60vh] overflow-y-auto">
```

**What this does:**
- `max-h-[60vh]`: limits the content area to 60% of the viewport height. If there are many SIG cards, the area becomes scrollable internally rather than overflowing the page.
- `overflow-y-auto`: shows a scrollbar only when the content is taller than the allocated space.
- Removing `flex-1`: the content area no longer tries to fill remaining parent height; it is sized by its content up to the `max-h-[60vh]` cap.
- `min-h-[400px]` is kept: ensures the area is always at least 400px tall, giving the empty state sufficient visual space.

**Note for reviewers:** This changes scrolling from page-level to component-level for the SIG card list. This is a deliberate UX trade-off to eliminate the layout-shift bug. If the product team decides page-level scrolling must be preserved, a different approach (such as JavaScript scroll-position saving and restoration) would be needed.

### How to verify

1. Log in as an admin so that the "Create SIG" button is visible.
2. Navigate to `/sigs`.
3. If there are many SIGs, scroll down to see more cards. Confirm the SIG list scrolls within its container (not the full page).
4. Type a search query in the search box that matches no SIGs.
5. The title and "Create SIG" button should remain in place. The empty state message should appear without any jump.
6. Clear the search and confirm the grid reappears correctly and is still scrollable within its container.

---

<a id="issue-4"></a>
## Issue 4: DM Messages Overflow the Screen Edges on Mobile

### Files to edit

- `frontend/src/views/DMView.vue`
- `frontend/src/components/dm/MessageThread.vue`

### What the bug looks like

On mobile screens (typically below 640px wide), a message that contains a very long word, URL, or any unbroken string of characters extends beyond the left or right edge of the screen, causing horizontal scroll on the entire page.

### Root cause

The message bubble wrapper at `MessageThread.vue` line 290 uses `max-w-[70%]` to limit the bubble's width. Inside the bubble, line 309 uses the Tailwind class `break-words`, which maps to the CSS property `overflow-wrap: break-word`.

`overflow-wrap: break-word` only breaks words when they would overflow, but it does not change the element's intrinsic size for flexbox/layout calculations. On mobile devices with narrow viewports, the bubble's container may not resolve `max-w-[70%]` to a small enough fixed value, allowing the content to push past the screen edges.

The stronger property is `overflow-wrap: anywhere`, which allows breaking at any character position AND influences the element's minimum content size in layout calculations, ensuring the bubble truly cannot exceed its container.

Additionally, the DM page root wrapper does not have `overflow-x-hidden`, so any overflow can leak to the page level.

### Fix

**Important: do NOT add `overflow-hidden` to the bubble wrapper div on line 290.** That wrapper contains the action menu (Edit / Recall dropdown) at lines 414-449, which uses `absolute` positioning with `-left-8` / `-right-8` to appear outside the bubble. Adding `overflow-hidden` would clip the action menu and make it invisible on hover.

**Step 1.** In `MessageThread.vue`, on **line 309**, strengthen word breaking by adding `[overflow-wrap:anywhere]` alongside the existing `break-words`.

Find this line:
```html
              <p v-if="item.message.content" class="whitespace-pre-wrap break-words">
```

Replace with:
```html
              <p v-if="item.message.content" class="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
```

The `[overflow-wrap:anywhere]` syntax is a Tailwind v4 arbitrary value. It applies the CSS property `overflow-wrap: anywhere` directly. This is stronger than `break-word` in two ways: (1) it breaks at any character boundary when needed, and (2) it changes the element's minimum content size in flexbox and grid layout calculations to essentially zero, preventing the bubble from expanding beyond its `max-w-[70%]` constraint.

This single change is the primary fix. The `<p>` element sits inside the bubble div, which sits inside the `max-w-[70%]` wrapper. With `overflow-wrap: anywhere`, the text will wrap within whatever width the wrapper provides, even if the text is a single unbroken 200-character string.

**Step 2.** In `DMView.vue`, on **line 297**, add `overflow-x-hidden` to the outermost page wrapper. This is a safety net that prevents any horizontal overflow from leaking to the page level.

Find this line:
```html
  <div class="max-w-6xl mx-auto px-4 py-6">
```

Replace with:
```html
  <div class="max-w-6xl mx-auto px-4 py-6 overflow-x-hidden">
```

### How to verify

1. Open the Messages page on a mobile device or in browser DevTools with a narrow viewport (for example, iPhone SE preset at 375px wide).
2. Open any conversation.
3. Send a message that is a single long unbroken string with no spaces. For example:
   ```
   aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
   ```
4. Also test with a long URL:
   ```
   https://example.com/this/is/a/very/long/path/segment/that/has/no/spaces
   ```
5. Confirm the text wraps within the bubble and does NOT cause horizontal scroll on the page.
6. Confirm that normal messages with spaces and line breaks still render correctly.
7. On desktop, hover over your own recent message and confirm the action menu (three-dot icon with Edit/Recall dropdown) still appears correctly outside the bubble. This verifies no `overflow-hidden` was accidentally added to the bubble wrapper.

---

<a id="issue-5"></a>
## Issue 5: SIG Page Title and Create SIG Button Overlap on Mobile

### File to edit

`frontend/src/views/sigs/SigsDirectoryView.vue`

### What the bug looks like

On screens narrower than approximately 640px (typical mobile width), the "Special Interest Groups" heading and the "Create SIG" button overlap each other. The title text is long enough that it pushes into the button's space in a `flex justify-between` single-row layout.

### Root cause

The header at line 52 uses `flex justify-between items-center`. On desktop, there is enough horizontal space for both the title (approximately 280px at `text-2xl`) and the button (approximately 120px), with space between them. On mobile screens of 375px width, subtracting padding leaves roughly 343px of content width. The title and button combined are wider than 343px, so they overlap or one is clipped.

The current code has no responsive breakpoint to stack the elements vertically on small screens.

### Fix

**Step 1.** On **line 52**, change the header div to use a vertical (column) flex layout on mobile and switch to a horizontal (row) layout starting at the `sm` breakpoint (640px).

Find this line:
```html
    <div class="flex justify-between items-center mb-6 shrink-0">
```

Replace with:
```html
    <div class="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mb-6 shrink-0">
```

**What each class does:**
- `flex flex-col`: on mobile, stack children vertically (title on top, button below).
- `gap-3`: 12px of space between the stacked title and button on mobile.
- `sm:flex-row`: at 640px and wider, switch to a horizontal row.
- `sm:justify-between`: on wider screens, push title to the left and button to the right.
- `sm:items-center`: on wider screens, vertically center both items in the row.
- `mb-6 shrink-0`: unchanged from the original.

**Step 2.** On **line 54**, add `class="shrink-0"` to the `router-link` wrapping the "Create SIG" button. This prevents the button from being compressed when the row layout is active at intermediate screen widths.

Find this line:
```html
      <router-link v-if="auth.isAdmin" to="/sigs/create">
```

Replace with:
```html
      <router-link v-if="auth.isAdmin" to="/sigs/create" class="shrink-0">
```

### How to verify

1. Log in as an admin so that the "Create SIG" button is visible.
2. Navigate to `/sigs`.
3. Open browser DevTools and set the viewport to 375px wide (iPhone SE).
4. Confirm the "Special Interest Groups" title appears on its own line, and the "Create SIG" button appears below it with visible spacing between them. They must not overlap.
5. Widen the viewport to 640px and above. Confirm the layout switches back to side-by-side, with the title on the left and the button on the right.
6. Confirm no visual regression at common desktop widths (1280px, 1440px).

---

## Also Apply the Same Responsive Fix to FormsDirectoryView

The `FormsDirectoryView.vue` header at line 84 has the same single-row `flex justify-between` pattern. Although the "Forms Directory" title is shorter than the SIG title, applying the same responsive pattern is correct and prevents future regressions if the title text changes.

### File to edit

`frontend/src/views/forms/FormsDirectoryView.vue`

### Fix

On **line 84**, apply the same responsive pattern.

Find this line:
```html
    <div class="flex justify-between items-center mb-2">
```

Replace with:
```html
    <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center mb-2">
```

On **line 86**, add `class="shrink-0"` to the `router-link`:

Find this line:
```html
      <router-link v-if="canCreate" to="/forms/new">
```

Replace with:
```html
      <router-link v-if="canCreate" to="/forms/new" class="shrink-0">
```

---

## Complete Change Summary

Use this table as a checklist when working through the fixes. Each row is one edit.

| # | File | Line | Original text (key part) | New text (key part) |
|---|------|------|--------------------------|---------------------|
| 1a | `views/forms/FormsDirectoryView.vue` | 80 | `<div>` | `<div class="flex-1 flex flex-col">` |
| 1b | `views/forms/FormsDirectoryView.vue` | 102 | `class="min-h-[200px]"` | `class="min-h-[400px]"` |
| 2a | `views/DMView.vue` | 342 | `class="flex-1 flex flex-col min-w-0"` | `class="flex-1 flex flex-col min-w-0 min-h-0"` |
| 2b | `components/dm/MessageThread.vue` | 202 | `class="flex-1 overflow-y-auto ..."` | add `min-h-0` at end |
| 3 | `views/sigs/SigsDirectoryView.vue` | 63 | `class="flex-1 w-full flex flex-col min-h-[400px]"` | `class="w-full flex flex-col min-h-[400px] max-h-[60vh] overflow-y-auto"` |
| 4a | `components/dm/MessageThread.vue` | 309 | `class="whitespace-pre-wrap break-words"` | add `[overflow-wrap:anywhere]` at end |
| 4b | `views/DMView.vue` | 297 | `class="max-w-6xl mx-auto px-4 py-6"` | add `overflow-x-hidden` at end |
| 5a | `views/sigs/SigsDirectoryView.vue` | 52 | `class="flex justify-between items-center mb-6 shrink-0"` | `class="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mb-6 shrink-0"` |
| 5b | `views/sigs/SigsDirectoryView.vue` | 54 | `<router-link v-if="auth.isAdmin" to="/sigs/create">` | add `class="shrink-0"` |
| 5c | `views/forms/FormsDirectoryView.vue` | 84 | `class="flex justify-between items-center mb-2"` | `class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center mb-2"` |
| 5d | `views/forms/FormsDirectoryView.vue` | 86 | `<router-link v-if="canCreate" to="/forms/new">` | add `class="shrink-0"` |

---

## Final Testing Checklist

After completing all edits, verify the following:

- [ ] `/forms`: search with no results — title and button do not jump or shift
- [ ] `/forms` on mobile (375px) — title and "Create Form" button stack vertically, no overlap
- [ ] `/forms`: grid results appear and disappear without layout jump
- [ ] `/sigs`: search with no results — title and button do not jump or shift
- [ ] `/sigs` on mobile (375px) — title and "Create SIG" button stack vertically, no overlap
- [ ] `/sigs`: SIG card list scrolls within the content box when there are many SIGs
- [ ] `/sigs`: switching from grid to empty state does not cause a scroll position jump
- [ ] `/messages`: sending many messages — message thread scrolls internally, container does not shift
- [ ] `/messages`: typing a multi-line message — textarea grows up, thread shrinks, no outer layout shift
- [ ] `/messages` on mobile (375px) — long unbroken text wraps within the bubble, no horizontal scroll on page
- [ ] `/messages` on mobile — normal messages with spaces and newlines still render correctly
- [ ] `/messages` on desktop — hover over own message shows action menu (Edit/Recall) correctly
- [ ] All pages at 1280px+ desktop width — no visual regressions
