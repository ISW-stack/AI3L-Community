# AI3L Community Frontend -- Contributor Task Guide

> **Last Updated:** 2026-03-01
> **Applies to:** Frontend codebase (`frontend/src/`)
> **Audience:** Collaborators who are new to the project or learning Vue/TypeScript

---

## Introduction

This document catalogues the current state of the AI3L Community frontend
and provides actionable tasks for contributors. It is organized into four
sections:

1. **Required Features** -- Functionality specified in the system design or
   backed by an existing backend API that has no frontend implementation yet.
2. **Optional Enhancements** -- Improvements that are not required by the
   specification but would benefit users.
3. **Known Bugs** -- Confirmed defects that need to be corrected.
4. **UI/UX Improvements** -- Refinements to existing user interface behavior
   and accessibility. Some items overlap with Section 2; where this occurs it
   is noted inline.

Each item includes a difficulty rating and a step-by-step implementation plan.

### Difficulty Scale

| Label | What it means |
|-------|--------------|
| **Beginner** | 1-3 files, no complex logic, mostly mechanical changes |
| **Intermediate** | 3-6 files, requires understanding state management or API calls |
| **Advanced** | Architectural decisions, multiple subsystems, or complex logic |

### How to Read This Document

Every item follows this structure:

- **Difficulty** rating
- **Affected files** -- which files to open first
- **Problem/Background** -- why this matters
- **Implementation Plan** -- numbered steps you can follow directly

---

## Section 1: Required Features Not Yet Implemented

These features are described in the system specification or have a
corresponding backend API endpoint, but no frontend implementation exists.

---

### 1.1 Guest Membership Application Form

**Difficulty: Intermediate**

**Affected files:**
- `src/api/users.ts` (add one function)
- `src/views/HomeView.vue` (add UI for guests)

**Background:**
The backend exposes `POST /api/v1/users/apply-member`, which lets a guest
user submit a membership application with a written description. The
`ApplicationsView` admin page already handles reviewing these applications.
However, guests currently have no way to initiate an application from the
frontend. This breaks the core onboarding flow for new users.

**Implementation Plan:**

1. Open `src/api/users.ts`. Add a new exported function at the bottom:
   ```typescript
   export const applyForMembership = (description: string) =>
     api.post('/users/apply-member', { description })
   ```

2. Open `src/views/HomeView.vue`. Locate the block that renders when
   `auth.isGuest` is true. Add a new card or section below the existing
   guest warning message.

3. Inside this new section, add:
   - A short explanation ("Apply for a full membership to access all
     features.")
   - A `BaseTextarea` for the applicant to write their motivation (at least
     50 characters is a reasonable minimum to enforce client-side).
   - A `BaseButton` labelled "Submit Application".

4. Implement the submit handler:
   ```typescript
   const submitApplication = async () => {
     if (description.value.trim().length < 50) {
       // show inline error
       return
     }
     try {
       await applyForMembership(description.value)
       toast.show('Your application has been submitted.', 'success')
       hasApplied.value = true
     } catch (err) {
       toast.show('Failed to submit application. You may have already applied.', 'error')
     }
   }
   ```

5. When `hasApplied` is true, hide the form and show a confirmation message
   so the user cannot submit twice.

---

### 1.2 Admin Category Management UI

**Difficulty: Intermediate**

**Affected files:**
- `src/api/categories.ts` (add three functions)
- `src/views/admin/CategoriesView.vue` (new file)
- `src/router/index.ts` (add one route)
- `src/components/AppNavbar.vue` (add one link)

**Background:**
The backend provides full CRUD for forum categories:
`POST /categories`, `PUT /categories/{id}`, `DELETE /categories/{id}`.
The `GET /categories` endpoint is already used in the forum to populate the
category filter. However, admins have no way to create, rename, or delete
categories from the frontend. This means category management must be done
directly in the database, which is error-prone.

**Implementation Plan:**

1. Open `src/api/categories.ts`. Add three new functions:
   ```typescript
   export const createCategory = (name: string, description: string) =>
     api.post('/categories', { name, description })

   export const updateCategory = (
     id: number,
     payload: { name?: string; description?: string }
   ) => api.put(`/categories/${id}`, payload)

   export const deleteCategory = (id: number) =>
     api.delete(`/categories/${id}`)
   ```

2. Create `src/views/admin/CategoriesView.vue`. This page should:
   - On mount, call the existing `listCategories()` function and display
     results in a `BaseTable` (columns: Name, Description, Actions).
   - Have a "Create Category" `BaseButton` that opens a `BaseModal`
     containing two `BaseInput` fields (Name and Description).
   - Each table row has an "Edit" button (opens the same modal pre-filled)
     and a "Delete" button (shows a confirmation modal; see Section 4.1).

3. In `src/router/index.ts`, add the route inside the admin routes block:
   ```typescript
   {
     path: '/admin/categories',
     component: () => import('../views/admin/CategoriesView.vue'),
     meta: { requiresAdmin: true }
   }
   ```

4. In `src/components/AppNavbar.vue`, add "Categories" to the admin
   dropdown link list, pointing to `/admin/categories`.

---

### 1.3 SIG Creation UI

**Difficulty: Intermediate**

**Affected files:**
- `src/api/sigs.ts` (add one function)
- `src/views/SigsDirectoryView.vue` (add button and modal)

**Background:**
The frontend lets users browse SIGs and SIG admins edit their own SIG, but
there is no way to create a new SIG. The `sigs.ts` API module has no
`createSig()` function and there is no route for it. SIG creation should
be restricted to platform admins.

**Pre-check:** Before starting, verify with the backend developer that
`POST /api/v1/sigs` is implemented and what payload it expects (likely
`{ name: string, description: string }`).

**Implementation Plan:**

1. In `src/api/sigs.ts`, import the `Sig` type from `../types` and add:
   ```typescript
   export const createSig = (payload: { name: string; description: string }) =>
     api.post<Sig>('/sigs', payload)
   ```

2. In `src/views/SigsDirectoryView.vue`, add a "Create SIG" `BaseButton`
   at the top of the page. Wrap it in a `v-if="auth.isAdmin"` condition so
   only admins see it.

3. Add a `BaseModal` with two `BaseInput` fields (SIG name and description)
   and a "Create" submit button.

4. In the submit handler:
   ```typescript
   const handleCreate = async () => {
     try {
       await createSig({ name: sigName.value, description: sigDescription.value })
       toast.show('SIG created successfully.', 'success')
       showModal.value = false
       await fetchSigs() // refresh the list
     } catch (err) {
       toast.show('Failed to create SIG.', 'error')
     }
   }
   ```

---

### 1.4 TipTap Editor: Direct Image File Upload

**Difficulty: Intermediate**

**Affected files:**
- `src/components/TiptapEditor.vue`

**Background:**
The system specification (Section 12.2) states that `TiptapEditor` should
support "image upload" in its toolbar. The backend endpoint
`POST /api/v1/files/upload/editor` already exists, and the `uploadEditorFile()`
and `getPresignedUrl()` functions are in `src/api/files.ts`. However, the
current implementation inserts images by asking the user to type a URL
using the browser's `prompt()` dialog. This bypasses the file storage
system and is a poor user experience.

**Implementation Plan:**

1. In `TiptapEditor.vue`, add a hidden file input element after the
   closing `</nav>` tag of the toolbar:
   ```html
   <input
     ref="imageFileInput"
     type="file"
     accept="image/png,image/jpeg,image/gif,image/webp"
     class="hidden"
     @change="handleImageUpload"
   />
   ```

2. Add a template ref and an `isUploadingImage` loading state:
   ```typescript
   const imageFileInput = ref<HTMLInputElement | null>(null)
   const isUploadingImage = ref(false)
   ```

3. Change the existing image toolbar button click handler from calling
   `prompt()` to triggering the file input:
   ```typescript
   const openImagePicker = () => imageFileInput.value?.click()
   ```

4. Add the `handleImageUpload` function:
   ```typescript
   const handleImageUpload = async (event: Event) => {
     const file = (event.target as HTMLInputElement).files?.[0]
     if (!file) return
     isUploadingImage.value = true
     try {
       const { key } = await uploadEditorFile(file)
       const { url } = await getPresignedUrl(key)
       editor.value?.chain().focus().setImage({ src: url }).run()
     } catch {
       // show toast error
     } finally {
       isUploadingImage.value = false
       if (imageFileInput.value) imageFileInput.value.value = ''
     }
   }
   ```

5. Disable the image toolbar button and show a spinner while
   `isUploadingImage` is true.

---

### 1.5 TipTap Editor: Table Support

**Difficulty: Intermediate**

**Affected files:**
- `package.json`
- `src/components/TiptapEditor.vue`

**Background:**
The system specification (Section 12.2) lists "table" as a required TipTap
toolbar feature. The current implementation has no table support. TipTap
provides official packages for this.

**Implementation Plan:**

1. Install the required packages (run from the `frontend/` directory):
   ```bash
   npm install @tiptap/extension-table @tiptap/extension-table-row \
               @tiptap/extension-table-header @tiptap/extension-table-cell
   ```

2. In `TiptapEditor.vue`, add imports at the top of the `<script setup>` block:
   ```typescript
   import Table from '@tiptap/extension-table'
   import TableRow from '@tiptap/extension-table-row'
   import TableHeader from '@tiptap/extension-table-header'
   import TableCell from '@tiptap/extension-table-cell'
   ```

3. Register the extensions inside the `useEditor({ extensions: [...] })`
   call:
   ```typescript
   Table.configure({ resizable: true }),
   TableRow,
   TableHeader,
   TableCell,
   ```

4. Add a "Table" button to the toolbar. On click, run:
   ```typescript
   editor.value?.chain().focus()
     .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
     .run()
   ```

5. Optionally add secondary buttons (Add Row, Add Column, Delete Table)
   that appear only when `editor.value?.isActive('table')` is true.

---

### 1.6 Comment Edit UI

**Difficulty: Beginner**

**Affected files:**
- `src/views/PostDetailView.vue`

**Background:**
The backend supports comment editing via
`PUT /api/v1/posts/{post_id}/comments/{comment_id}`, and `updateComment()`
is already in `src/api/comments.ts`. However, `PostDetailView.vue` provides
no "Edit" button for comments. Users can delete their comments but not
correct them.

**Implementation Plan:**

1. At the top of `<script setup>` in `PostDetailView.vue`, add two reactive
   variables:
   ```typescript
   const editingCommentId = ref<string | null>(null)
   const editContent = ref('')
   ```

2. In the comment template, add an "Edit" button next to the existing
   "Delete" button. Show it only for the comment's author:
   ```html
   <BaseButton
     v-if="auth.user?.id === comment.author.id"
     variant="ghost"
     size="sm"
     @click="startEdit(comment)"
   >
     Edit
   </BaseButton>
   ```

3. Add the `startEdit` function:
   ```typescript
   const startEdit = (comment: Comment) => {
     editingCommentId.value = comment.id
     editContent.value = comment.content
   }
   ```

4. In the comment template, replace the rendered HTML with a textarea
   and Save/Cancel buttons when the comment is being edited:
   ```html
   <template v-if="editingCommentId === comment.id">
     <BaseTextarea v-model="editContent" :rows="3" />
     <BaseButton size="sm" @click="saveEdit(comment)">Save</BaseButton>
     <BaseButton size="sm" variant="ghost" @click="editingCommentId = null">Cancel</BaseButton>
   </template>
   <div v-else v-html="sanitize(comment.content)" />
   ```

5. Add the `saveEdit` function:
   ```typescript
   const saveEdit = async (comment: Comment) => {
     try {
       const updated = await updateComment(postId, comment.id, { content: editContent.value })
       // Replace the comment in the local array
       const index = comments.value.findIndex(c => c.id === comment.id)
       if (index !== -1) comments.value[index] = updated.data
       editingCommentId.value = null
     } catch {
       toast.show('Failed to save edit.', 'error')
     }
   }
   ```

---

### 1.7 Account Deletion (GDPR Right to Erasure)

**Difficulty: Beginner**

**Affected files:**
- `src/views/ProfileView.vue`

**Background:**
The system specification (Section 1) explicitly requires GDPR compliance,
including the right to erasure. The backend supports account anonymization
via `DELETE /api/v1/users/me`, and `deleteAccount()` is in `src/api/users.ts`.
`ProfileView.vue` has no UI for this. Guest users should not see this option
(they do not have persistent accounts).

**Implementation Plan:**

1. At the bottom of the profile form in `ProfileView.vue`, add a "Danger
   Zone" section with a red left border or red border around it to visually
   signal that this is a destructive area.

2. Add a `BaseButton` with `variant="danger"` labelled "Delete My Account".
   Wrap it in `v-if="!auth.isGuest"`.

3. When clicked, open a `BaseModal` that:
   - Explains the action is permanent and results in anonymization.
   - Contains a `BaseInput` where the user must type their username to
     confirm (use `v-model` and validate that it matches `auth.user?.username`
     before enabling the confirm button).

4. On confirmation:
   ```typescript
   const handleDeleteAccount = async () => {
     try {
       await deleteAccount()
       auth.clearSession()
       router.push('/login')
     } catch {
       toast.show('Failed to delete account. Please try again.', 'error')
     }
   }
   ```

---

## Section 2: Optional Enhancements

These items are not required by the system specification but would improve
the product. They are ordered roughly by impact.

---

### 2.1 Comment Pagination

**Difficulty: Intermediate**

**Affected files:** `src/views/PostDetailView.vue`

The backend supports `offset`/`limit` parameters on comment listing (max 200
comments per post). `PostDetailView.vue` currently loads all comments in one
request. For high-traffic posts, this can slow page loads significantly.

**Implementation Plan:**
1. Add `commentPage` reactive state (starts at 1) and a `COMMENTS_PAGE_SIZE`
   constant (e.g., 20).
2. Modify `fetchComments()` to send:
   `?offset=${(commentPage.value - 1) * COMMENTS_PAGE_SIZE}&limit=${COMMENTS_PAGE_SIZE}`
3. Store the total comment count from the response to calculate total pages.
4. Add a `BasePagination` component below the comments section.
5. When `commentPage` changes (watch it), re-fetch comments.
6. Note: if comments are threaded (parent/child), paginate only top-level
   comments and load replies on demand or load them with the parent.

---

### 2.2 Post Draft Auto-Save

**Difficulty: Advanced**

**Affected files:** `src/views/PostCreateView.vue`

When writing a long post, users risk losing their content if the browser
crashes or they accidentally navigate away.

**Implementation Plan:**
1. In `PostCreateView.vue`, use `localStorage` to save the draft. Choose a
   key such as `draft:new-post`.
2. Set up a `watch` on the title, content, category, and keywords. On any
   change (debounced by 2 seconds), save the current form state to
   `localStorage` as a JSON string.
3. On component mount, check if a saved draft exists. If so, prompt the
   user with a modal: "You have an unsaved draft. Restore it?"
4. On successful post submission, delete the draft key from `localStorage`.
5. Add an `onBeforeRouteLeave` guard that warns the user if they try to
   navigate away with unsaved, non-empty content.

---

### 2.3 Form Preview Mode

**Difficulty: Intermediate**

**Affected files:** `src/views/FormBuilderView.vue`

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

### 2.4 SIG Search and Filter

**Difficulty: Beginner**

**Affected files:** `src/views/SigsDirectoryView.vue`

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

### 2.5 Password Visibility Toggle

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

### 2.6 Frontend Unit Tests

**Difficulty: Advanced**

**Affected files:** new files under `src/` following `*.test.ts` naming convention

Vitest is configured but no test files exist. The CI/CD pipeline (spec
Section 16.1) expects frontend unit tests to run on every push. Without
tests, regressions are hard to detect.

**Implementation Plan:**
1. Start with the Pinia stores (`auth.ts`, `notifications.ts`, `toast.ts`)
   as they have well-defined inputs and outputs and do not depend on the DOM.
2. Test utility functions: `utils/datetime.ts` and `utils/html.ts`.
3. Use `@vue/test-utils` to mount and test individual components.
4. Example test for the toast store:
   ```typescript
   import { setActivePinia, createPinia } from 'pinia'
   import { useToastStore } from '../stores/toast'

   describe('Toast Store', () => {
     beforeEach(() => setActivePinia(createPinia()))

     it('adds a toast and auto-dismisses', async () => {
       const store = useToastStore()
       store.show('Hello', 'info')
       expect(store.toasts).toHaveLength(1)
     })
   })
   ```
5. Focus on critical paths first: authentication flow, form validation
   logic, and store state transitions.

---

### 2.7 Invite Code Generation for Members

**Difficulty: Beginner**

**Affected files:** `src/views/ProfileView.vue`

The specification states that Members (not just Admins) can generate invite
codes. Currently the only invite code UI is in the Admin panel.

**Implementation Plan:**
1. Add a "Invite Codes" section to `ProfileView.vue`, visible to all
   non-guest authenticated users (`v-if="!auth.isGuest"`).
2. Add a "Generate Invite Code" `BaseButton`.
3. On click, call `createInviteCode()` from `src/api/admin.ts`. This
   function already exists.
4. Display the returned code in a read-only `BaseInput` with a "Copy to
   Clipboard" button that calls `navigator.clipboard.writeText(code)`.
5. Show a success toast when the code is generated.

---

## Section 3: Known Bugs

These are confirmed defects in the current code that must be fixed.

---

### 3.1 BaseInput and BaseTextarea: maxlength Prop Not Applied

**Difficulty: Beginner**
**Files:** `src/components/base/BaseInput.vue`, `src/components/base/BaseTextarea.vue`

**Problem:**
Both components define a `maxlength` prop, but the prop is not bound to the
actual `<input>` or `<textarea>` HTML element. This means that even when a
parent passes `:maxlength="100"`, the user can type unlimited characters.
The prop is silently ignored.

**Fix:**
1. Open `src/components/base/BaseInput.vue`.
2. Find the `<input>` element and add `:maxlength="maxlength"` to its
   attribute list.
3. Repeat for the `<textarea>` in `src/components/base/BaseTextarea.vue`.
4. To verify: add `:maxlength="5"` to any `BaseInput` in the app and
   confirm you cannot type more than 5 characters.

---

### 3.2 relativeTime() Utility Function Is Duplicated

**Difficulty: Beginner**
**Files:** `src/utils/datetime.ts`, `src/views/NotificationsView.vue`

**Problem:**
A `relativeTime()` function is defined in `src/utils/datetime.ts` but is
not used anywhere. Instead, `NotificationsView.vue` contains a local copy of
the same logic. If the time formatting logic needs to change, both copies
must be updated separately, which is error-prone.

**Fix:**
1. Open `src/views/NotificationsView.vue`.
2. Remove the locally defined `relativeTime` function from the `<script setup>` block.
3. Add the following import at the top of the script block:
   ```typescript
   import { relativeTime } from '../utils/datetime'
   ```
4. Verify that notification timestamps still display correctly in the browser.

---

### 3.3 Forum Post Preview Uses Inconsistent HTML Handling

**Difficulty: Beginner**
**Files:** `src/views/ForumView.vue`

**Problem:**
`PostDetailView.vue` uses DOMPurify to sanitize HTML before rendering post
content, which is the correct approach. However, `ForumView.vue` generates
the post preview text using a different method (likely a simple DOM element
or regex-based strip) that does not go through DOMPurify. This is
inconsistent and could expose raw HTML tags or unsafe content in the
listing view.

**Fix:**
1. Open `src/views/ForumView.vue`. Find where post content is processed
   for the preview (look for a computed property or inline expression that
   shortens or strips the content).
2. Import DOMPurify at the top of the script block:
   ```typescript
   import DOMPurify from 'dompurify'
   ```
3. Replace the existing stripping logic with:
   ```typescript
   const preview = DOMPurify.sanitize(post.content, { ALLOWED_TAGS: [] })
     .slice(0, 200)
   ```
   This strips all HTML tags (leaving plain text) and then trims to a
   preview length.

---

### 3.4 Post Edit: Version Conflict Error (SYS_409) Not Explained to the User

**Difficulty: Intermediate**
**Files:** `src/views/PostDetailView.vue`

**Problem:**
The backend uses optimistic locking on post edits. If two users edit the
same post at the same time, the second save will be rejected with error code
`SYS_409`. The frontend currently catches this as a generic error and shows
no specific guidance. The user does not know why the save failed or what to
do next.

**Fix:**
1. In `PostDetailView.vue`'s save handler, check if the error response
   contains the error code `SYS_409`:
   ```typescript
   } catch (err: unknown) {
     const apiError = err as { response?: { data?: { detail?: { code?: string } } } }
     if (apiError.response?.data?.detail?.code === 'SYS_409') {
       toast.show(
         'Someone else edited this post while you were writing. Please reload to see the latest version.',
         'warning'
       )
     } else {
       toast.show('Failed to save post.', 'error')
     }
   }
   ```
2. Optionally, add a "Reload Post" button that fetches the latest version
   of the post from the API and updates the editor content.

---

### 3.5 FormBuilder: Rating Question Allows Invalid Min/Max Values

**Difficulty: Beginner**
**Files:** `src/views/FormBuilderView.vue`

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
4. Prevent form submission if any question has a rating error (add a check
   in the existing `validateForm()` or `serializeForm()` function).

---

### 3.6 Forum Search: Pagination State Not Reset on Mode Change

**Difficulty: Beginner**
**Files:** `src/views/ForumView.vue`

**Problem:**
If the user is browsing page 3 of posts and then submits a search, the
search results are requested but the `currentPage` variable may not be
reset to 1. Depending on the implementation, the user can end up viewing
page 3 of search results (which may be empty) or page 3 of the browse
results after clearing the search.

**Fix:**
1. Find the `submitSearch()` handler (or wherever the search query is
   applied) in `ForumView.vue`.
2. At the top of that function, reset the page:
   ```typescript
   currentPage.value = 1
   ```
3. Similarly, find where the search is cleared (e.g., a "Clear" or "Reset"
   button) and reset the page there as well.
4. Test by navigating to page 2+, submitting a search, and verifying that
   results start from page 1.

---

## Section 4: UI/UX Improvements

These are refinements to existing behavior. Items marked
**[See also Sec. 2]** have a related entry in Section 2 where additional
context is provided.

---

### 4.1 Replace Browser confirm() Dialogs with Styled Confirmation Modals

**Difficulty: Beginner**
**Files:** `src/views/PostDetailView.vue`, `src/views/admin/CategoriesView.vue`

**Problem:**
Destructive actions (deleting a post, deleting a comment) use the browser's
native `confirm()` dialog. This dialog is styled by the operating system,
cannot match the application's design, and is considered a poor UX pattern.

**Implementation Plan:**
1. Create a reusable composable `src/composables/useConfirm.ts`:
   ```typescript
   import { ref } from 'vue'

   const isOpen = ref(false)
   const resolveRef = ref<((value: boolean) => void) | null>(null)

   export function useConfirm() {
     const confirm = (): Promise<boolean> =>
       new Promise(resolve => {
         isOpen.value = true
         resolveRef.value = resolve
       })

     const accept = () => { resolveRef.value?.(true); isOpen.value = false }
     const cancel = () => { resolveRef.value?.(false); isOpen.value = false }

     return { isOpen, confirm, accept, cancel }
   }
   ```
2. Add a `ConfirmModal.vue` component (or extend `BaseModal`) that uses
   this composable to show a "Are you sure?" dialog with Cancel and Confirm
   buttons.
3. Replace all `if (confirm('...'))` calls in views with:
   ```typescript
   if (await confirm()) { /* proceed */ }
   ```

---

### 4.2 Keyboard Navigation for Dropdown Menus

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
   - `ArrowDown`: move focus to the next menu item (use `querySelectorAll`
     to find focusable items and track an index).
   - `ArrowUp`: move focus to the previous item.
   - `Enter`/`Space`: activate the focused item.
   - `Escape`: close the dropdown and return focus to the trigger button.
4. Add `tabindex="-1"` to each menu item so they can receive programmatic
   focus without appearing in the natural tab order.

---

### 4.3 Focus Management in Modal Dialogs

**Difficulty: Intermediate**
**Files:** `src/components/base/BaseModal.vue`

**Problem:**
When a modal opens, the browser does not automatically move focus inside it.
When the modal closes, focus is not returned to the element that opened it.
This makes modals difficult to use with keyboard navigation and breaks screen
reader workflows.

**Implementation Plan:**
1. In `BaseModal.vue`, add a template ref on the modal container:
   ```html
   <div ref="modalContainer" tabindex="-1" ...>
   ```
2. In `onMounted` or in a `watch` on the `modelValue`/`open` prop, save
   the currently focused element and focus the modal container:
   ```typescript
   const previousFocus = ref<HTMLElement | null>(null)
   watch(isOpen, (open) => {
     if (open) {
       previousFocus.value = document.activeElement as HTMLElement
       nextTick(() => modalContainer.value?.focus())
     } else {
       previousFocus.value?.focus()
     }
   })
   ```
3. Implement a focus trap: listen for `Tab` keydown inside the modal.
   Collect all focusable elements (`a, button, input, textarea, select`)
   inside the modal. When the last element is focused and `Tab` is pressed,
   wrap back to the first. When the first element is focused and
   `Shift+Tab` is pressed, wrap to the last.

---

### 4.4 TipTap Image URL Insertion: Replace prompt() with a Modal Dialog

**Difficulty: Beginner**
**Files:** `src/components/TiptapEditor.vue`

**Note:** If Section 1.4 (direct file upload) is implemented, this item
becomes less critical. However, URL-based insertion may still be useful as
a fallback for external images.

**Problem:**
The current image insertion path uses `window.prompt()` to ask for a URL.
This is jarring and cannot be styled.

**Implementation Plan:**
1. Replace the `prompt()` call with a `BaseModal` that contains one
   `BaseInput` for the image URL and two buttons: "Cancel" and "Insert".
2. Add `showImageUrlModal` and `imageUrl` reactive variables.
3. On "Insert", validate that `imageUrl` starts with `http://` or
   `https://` before calling the TipTap image command.

---

### 4.5 Forum Search: Date Range Validation

**Difficulty: Beginner**
**Files:** `src/views/ForumView.vue`

**Problem:**
The forum search form has "Date From" and "Date To" fields. There is no
validation preventing "Date From" from being later than "Date To", which
would produce zero results and confuse users.

**Implementation Plan:**
1. Add a computed property or a watcher:
   ```typescript
   const dateRangeError = computed(() =>
     dateFrom.value && dateTo.value && dateFrom.value > dateTo.value
       ? '"Date From" must be before "Date To".'
       : ''
   )
   ```
2. Display `dateRangeError` as an inline error message below the date
   fields.
3. Disable the search button when `dateRangeError` is non-empty.

---

### 4.6 Toast Notifications: Allow Manual Dismissal

**Difficulty: Beginner**
**Files:** `src/components/ToastNotification.vue`

**Problem:**
Toast notifications auto-dismiss after 5 seconds but cannot be closed
manually. Users who have read the notification must wait for the timer.

**Implementation Plan:**
1. Open `src/components/ToastNotification.vue`.
2. In the template for each toast item, add a close button (use
   `XIcon` from `lucide-vue-next`).
3. Wire its click handler to call:
   ```typescript
   toastStore.dismiss(toast.id)
   ```
   The `dismiss` action already exists in the toast store.

---

### 4.7 Improve Error Messages on Form Submission

**Difficulty: Beginner**
**Files:** `src/views/LoginView.vue`, `src/views/RegisterView.vue`, and other
form views

**Problem:**
Most form error handlers display a generic string such as "Registration
failed". The backend returns structured error responses with specific
`message` fields (see Section 17 of the system specification). Displaying
these messages directly would help users understand what went wrong.

**Implementation Plan:**
1. The API interceptor in `composables/api.ts` already parses backend error
   responses and re-throws them. The thrown error's `message` property
   contains the backend's human-readable description.
2. In each form's catch block, extract and display this message:
   ```typescript
   } catch (err: unknown) {
     const message = (err as Error).message || 'An unexpected error occurred.'
     errorMessage.value = message
   }
   ```
3. Apply this to login, registration, guest login, profile update, and
   password change forms.

---

### 4.8 Admin Users Table: Pagination

**Difficulty: Beginner**
**Files:** `src/views/admin/UsersView.vue`

**Problem:**
`UsersView.vue` fetches users with a hardcoded `limit: 100`. This is both
a performance concern and a functional limit: it will silently omit users
beyond the first 100 as the platform grows.

**Implementation Plan:**
1. Define a `ADMIN_PAGE_SIZE` constant (it already exists in
   `src/constants.ts` as `50`).
2. Add a `currentPage` reactive variable (starts at 1).
3. Modify the `listUsers()` call to use:
   `{ offset: (currentPage.value - 1) * ADMIN_PAGE_SIZE, limit: ADMIN_PAGE_SIZE }`
4. Store the total user count from the API response.
5. Add a `BasePagination` component below the table.
6. Remove the hardcoded `limit: 100`.

---

## Appendix: Getting Started

### Key Directories

```
frontend/src/
-- api/         HTTP request functions (one file per domain area)
-- components/  Reusable Vue components; base/ is the design system
-- composables/ Vue composables (api.ts, useWebSocket.ts)
-- router/      Route definitions and navigation guards (index.ts)
-- stores/      Pinia global state (auth.ts, notifications.ts, toast.ts)
-- types/       TypeScript interfaces for all data models
-- utils/       Utility functions (datetime, html)
-- views/       One file per page/route
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

### Recommended Order for First-Time Contributors

1. Read `src/types/index.ts` and the files it exports. Understanding the
   data models makes everything else easier.
2. Open `src/router/index.ts` to see all pages and their access rules.
3. Pick a **Beginner** item. Open the relevant files and read them fully
   before writing any code.
4. Check your changes work for different user roles (Guest, Member, Admin,
   Super Admin) by logging in with each role type.
5. Run the linter before submitting: `npm run lint` inside `frontend/`.

### Common Patterns

**Calling the API and handling errors:**
```typescript
const isLoading = ref(false)
const error = ref('')

const fetchData = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const res = await someApiFunction()
    data.value = res.data
  } catch (err: unknown) {
    error.value = (err as Error).message || 'Failed to load data.'
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
