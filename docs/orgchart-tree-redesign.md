# OrgChartView Tree Diagram Redesign

## Summary

Redesign `frontend/src/views/about/OrgChartView.vue` from a card-list layout into a
top-down collapsible tree diagram. No new libraries. CSS connector lines via `<style scoped>`.

---

## Target Visual

```
              ┌─────────────────────────┐
              │     AI3L Community      │   <- static root node
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
  ┌──────────┐       ┌──────────┐       ┌──────────┐
  │  SIG A ▶ │       │  SIG B ▼ │       │  SIG C ▶ │  <- click to expand
  │ 12 members│      │ 8 members│       │ 5 members│
  └──────────┘       └────┬─────┘       └──────────┘
                          │  (expands downward)
               ┌──────────────────────────────┐
               │  ADMINS & SUB-ADMINS         │
               │  [Avatar] Alice   ADMIN      │
               │  [Avatar] Bob     SUB_ADMIN  │
               │                              │
               │  MEMBERS                     │
               │  • Carol Liu                 │
               │  • David Zhang               │
               │  • Emma Wu    +5 more...     │  <- truncated at 10
               └──────────────────────────────┘
```

---

## Decisions

| # | Decision |
|---|----------|
| 1 | SIG nodes default to **collapsed** |
| 2 | Regular members truncated at **10**, with "+N more" toggle |
| 3 | SIGs may be numerous — handle wrapping gracefully (see RWD section) |
| 4 | Admin/SubAdmin bio shown as `line-clamp-1`; full text on hover via `title` attribute |

---

## Files Changed

Only one file changes: `frontend/src/views/about/OrgChartView.vue` (full rewrite of template + style block; script additions only).

No new components. No new dependencies. No backend changes.

---

## Script Changes

### New state

```typescript
const expandedSigs = ref<Set<string>>(new Set())          // all collapsed by default
const showAllMembers = ref<Set<string>>(new Set())         // tracks which SIGs show full member list
const MEMBER_PREVIEW_COUNT = 10
```

### New functions

```typescript
function toggleSig(sigId: string) {
  if (expandedSigs.value.has(sigId)) expandedSigs.value.delete(sigId)
  else expandedSigs.value.add(sigId)
}

function toggleShowAll(sigId: string) {
  if (showAllMembers.value.has(sigId)) showAllMembers.value.delete(sigId)
  else showAllMembers.value.add(sigId)
}

function groupMembers(members: OrgChartMember[]) {
  return {
    leads: members.filter(m => m.role === 'ADMIN' || m.role === 'SUB_ADMIN'),
    regular: members.filter(m => m.role === 'MEMBER'),
  }
}

function visibleRegularMembers(sig: OrgChartSig) {
  const regular = groupMembers(sig.members).regular
  if (showAllMembers.value.has(sig.id)) return regular
  return regular.slice(0, MEMBER_PREVIEW_COUNT)
}

function hiddenMemberCount(sig: OrgChartSig) {
  const total = groupMembers(sig.members).regular.length
  return Math.max(0, total - MEMBER_PREVIEW_COUNT)
}
```

### Unchanged

All existing edit state and functions are kept as-is:
- `editingOverride`, `overrideForm`, `saveOverride`, `startEditOverride`
- `editingSigDesc`, `sigDescForm`, `saveSigDesc`, `startEditSigDesc`, `canEditSigDesc`
- `editingBio`, `bioForm`, `saveBio`, `startEditBio`, `canEditMyBio`
- `handleAvatarError`

### New lucide import

Add `ChevronDown`, `ChevronRight` to the existing lucide import line.

---

## Template Structure

### SIGs Section (full replacement)

```html
<section class="mb-16">
  <h2>{{ t('orgChart.sigs') }}</h2>

  <!-- Root node -->
  <div class="flex flex-col items-center mt-6">
    <div class="root-node">
      AI3L Community
    </div>

    <!-- Tree row: connector lines drawn by CSS -->
    <div class="tree-row" v-if="data.sigs.length > 0">

      <div
        v-for="sig in data.sigs"
        :key="sig.id"
        class="tree-node-wrapper"
        :class="{ 'opacity-50': sig.override?.is_visible === false }"
      >
        <!-- SIG card / clickable node -->
        <button class="sig-node" @click="toggleSig(sig.id)">
          <div class="sig-node-header">
            <component :is="expandedSigs.has(sig.id) ? ChevronDown : ChevronRight" class="w-4 h-4 shrink-0" />
            <span class="font-semibold text-sm truncate">
              {{ sig.override?.custom_title || sig.name }}
            </span>
            <BaseBadge v-if="sig.override?.is_visible === false" variant="neutral" size="sm">
              {{ t('orgChart.hidden') }}
            </BaseBadge>
          </div>
          <div class="sig-node-meta">
            {{ sig.member_count }} {{ t('orgChart.memberCount') }}
          </div>
        </button>

        <!-- Admin action buttons (outside the clickable button to avoid event bubbling) -->
        <div class="sig-node-actions">
          <button v-if="canEditSigDesc(sig)" @click.stop="startEditSigDesc(sig)" :title="t('orgChart.editDescription')">
            <Pencil class="w-3.5 h-3.5" />
          </button>
          <button v-if="isSuperAdmin" @click.stop="startEditOverride('sig', sig.id, sig)" :title="t('orgChart.editOverride')">
            <Settings class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Inline edit forms (unchanged logic, restyled to fit below node) -->
        <div v-if="editingOverride?.type === 'sig' && editingOverride.id === sig.id" class="node-edit-form">
          <!-- ... same fields as before ... -->
        </div>
        <div v-if="editingSigDesc === sig.id" class="node-edit-form">
          <!-- ... same fields as before ... -->
        </div>

        <!-- Connector line: node -> member panel -->
        <div v-if="expandedSigs.has(sig.id)" class="node-to-panel-line" aria-hidden="true"></div>

        <!-- Expanded member panel -->
        <Transition name="panel-expand">
          <div v-if="expandedSigs.has(sig.id)" class="member-panel">

            <!-- SIG description -->
            <p v-if="sig.org_chart_description || sig.description" class="sig-panel-desc">
              {{ sig.org_chart_description || sig.description }}
            </p>

            <!-- Leads: ADMIN + SUB_ADMIN with avatar -->
            <div v-if="groupMembers(sig.members).leads.length > 0" class="member-section">
              <div v-for="m in groupMembers(sig.members).leads" :key="m.user_id" class="lead-member-row">
                <!-- Avatar -->
                <router-link :to="`/users/${m.user_id}`" class="shrink-0">
                  <div class="relative w-9 h-9">
                    <img
                      v-if="m.avatar_url"
                      :src="m.avatar_url"
                      :alt="m.display_name"
                      class="w-9 h-9 rounded-full object-cover border border-border"
                      @error="handleAvatarError"
                    />
                    <div
                      class="avatar-fallback w-9 h-9 rounded-full bg-brand-100 text-brand-700 items-center justify-center text-sm font-semibold absolute inset-0"
                      :style="{ display: m.avatar_url ? 'none' : 'flex' }"
                    >
                      {{ m.display_name.charAt(0).toUpperCase() }}
                    </div>
                  </div>
                </router-link>
                <!-- Info -->
                <div class="min-w-0">
                  <router-link :to="`/users/${m.user_id}`" class="text-sm font-medium text-foreground hover:text-brand-600 transition truncate block">
                    {{ m.display_name }}
                  </router-link>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <BaseBadge :variant="roleBadgeVariant[m.role] || 'neutral'" size="sm">
                      {{ m.role.replace('_', ' ') }}
                    </BaseBadge>
                  </div>
                  <p v-if="m.org_chart_bio" class="text-xs text-muted mt-0.5 line-clamp-1" :title="m.org_chart_bio">
                    {{ m.org_chart_bio }}
                  </p>
                </div>
                <!-- Edit bio button -->
                <button
                  v-if="canEditMyBio(sig) && m.user_id === auth.user?.id"
                  class="p-1 text-muted hover:text-foreground transition shrink-0"
                  @click.stop="startEditBio(sig.id, m.org_chart_bio)"
                >
                  <Pencil class="w-3 h-3" />
                </button>
              </div>
            </div>

            <!-- Divider (only if both leads and regular exist) -->
            <div
              v-if="groupMembers(sig.members).leads.length > 0 && groupMembers(sig.members).regular.length > 0"
              class="border-t border-border my-2"
            ></div>

            <!-- Regular members: name only, no avatar -->
            <div v-if="groupMembers(sig.members).regular.length > 0" class="member-section">
              <div v-for="m in visibleRegularMembers(sig)" :key="m.user_id" class="regular-member-row">
                <span class="text-muted text-xs mr-1">•</span>
                <router-link :to="`/users/${m.user_id}`" class="text-sm text-foreground hover:text-brand-600 transition truncate">
                  {{ m.display_name }}
                </router-link>
                <!-- Edit bio button -->
                <button
                  v-if="canEditMyBio(sig) && m.user_id === auth.user?.id"
                  class="p-1 text-muted hover:text-foreground transition shrink-0 ml-auto"
                  @click.stop="startEditBio(sig.id, m.org_chart_bio)"
                >
                  <Pencil class="w-3 h-3" />
                </button>
              </div>
              <!-- Show more / less -->
              <button
                v-if="hiddenMemberCount(sig) > 0 || showAllMembers.has(sig.id)"
                class="text-xs text-brand-600 hover:text-brand-700 mt-1 transition"
                @click.stop="toggleShowAll(sig.id)"
              >
                <span v-if="!showAllMembers.has(sig.id)">+{{ hiddenMemberCount(sig) }} more</span>
                <span v-else>Show less</span>
              </button>
            </div>

            <!-- Empty state -->
            <p v-if="sig.members.length === 0" class="text-xs text-muted text-center py-2">
              No members
            </p>

            <!-- Inline bio edit form -->
            <div v-if="editingBio?.sigId === sig.id" class="node-edit-form mt-2">
              <!-- ... same fields as before ... -->
            </div>

          </div>
        </Transition>
      </div>

    </div>

    <div v-else class="text-muted mt-4">{{ t('orgChart.noSigs') }}</div>
  </div>
</section>
```

### Forum Categories Section (minor changes only)

Keep existing grid. Changes:
- Creator avatar: `w-6 h-6` → `w-8 h-8`
- Creator name: add `font-medium` class
- Add "Created by" label before the name (already exists as `t('common.by')`, just style upgrade)

No structural changes.

---

## CSS (`<style scoped>`)

```css
/* ── Root node ─────────────────────────────────────── */
.root-node {
  background-color: var(--color-brand-600);
  color: #fff;
  font-weight: 600;
  font-size: 0.9375rem;
  padding: 0.625rem 1.75rem;
  border-radius: 0.75rem;
  letter-spacing: 0.01em;
}

/* ── Tree row ─────────────────────────────────────── */
.tree-row {
  display: flex;
  flex-wrap: wrap;           /* graceful wrap when many SIGs */
  justify-content: center;
  align-items: flex-start;
  gap: 1rem;
  padding-top: 2.5rem;
  position: relative;
}

/* Vertical line: root → horizontal bar */
.tree-row::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  height: 2.5rem;
  background-color: var(--color-border);
}

/* ── Tree node wrapper ────────────────────────────── */
.tree-node-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  padding-top: 2rem;
  width: 200px;               /* fixed width for even spacing */
}

/* Vertical line: horizontal bar → node top */
.tree-node-wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  height: 2rem;
  background-color: var(--color-border);
}

/* Horizontal bar (each node contributes its half) */
.tree-node-wrapper::after {
  content: '';
  position: absolute;
  top: 0;
  height: 2px;
  background-color: var(--color-border);
}

.tree-node-wrapper:first-child::after  { left: 50%;  right: 0; }
.tree-node-wrapper:last-child::after   { left: 0;    right: 50%; }
.tree-node-wrapper:not(:first-child):not(:last-child)::after { left: 0; right: 0; }
.tree-node-wrapper:only-child::after   { display: none; }

/* NOTE: When nodes wrap to a second row, the ::after horizontal line
   will still render per-row but won't connect back to root.
   This is acceptable — the root vertical line becomes a visual anchor.
   If this is unacceptable in future, consider limiting to one row with
   horizontal scroll, or increasing node width to force single row. */

/* ── SIG node card ────────────────────────────────── */
.sig-node {
  width: 100%;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  position: relative;
}

.sig-node:hover {
  border-color: var(--color-brand-400);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand-600) 10%, transparent);
}

.sig-node-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.sig-node-meta {
  font-size: 0.75rem;
  color: var(--color-muted);
  margin-top: 0.25rem;
  padding-left: 1.375rem;  /* indent past chevron */
}

/* Admin action buttons row (sits below the sig-node button) */
.sig-node-actions {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.375rem;
  justify-content: flex-end;
  width: 100%;
  padding: 0 0.25rem;
}

.sig-node-actions button {
  padding: 0.25rem;
  color: var(--color-muted);
  border-radius: 0.25rem;
  transition: color 0.15s;
}

.sig-node-actions button:hover {
  color: var(--color-foreground);
}

/* ── Connector: node → member panel ──────────────── */
.node-to-panel-line {
  width: 2px;
  height: 1rem;
  background-color: var(--color-border);
  flex-shrink: 0;
}

/* ── Member panel ─────────────────────────────────── */
.member-panel {
  width: 100%;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  padding: 0.875rem;
  margin-top: 0;
}

.sig-panel-desc {
  font-size: 0.75rem;
  color: var(--color-muted);
  margin-bottom: 0.625rem;
  line-height: 1.4;
}

.member-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* Lead member row (with avatar) */
.lead-member-row {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}

/* Regular member row (no avatar) */
.regular-member-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
}

/* ── Inline edit forms ────────────────────────────── */
.node-edit-form {
  width: 100%;
  background-color: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
  padding: 0.75rem;
  margin-top: 0.5rem;
}

/* ── Expand/collapse transition ───────────────────── */
.panel-expand-enter-active,
.panel-expand-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-expand-enter-from,
.panel-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 767px) {
  /* Switch to vertical indented layout on mobile */
  .tree-row {
    flex-direction: column;
    align-items: stretch;
    padding-top: 1rem;
    gap: 0.5rem;
  }

  /* Hide the horizontal-bar pseudo-elements on mobile */
  .tree-row::before,
  .tree-node-wrapper::before,
  .tree-node-wrapper::after {
    display: none;
  }

  /* Left-side indent border as visual substitute */
  .tree-node-wrapper {
    padding-top: 0;
    width: 100%;
    padding-left: 1.25rem;
    border-left: 2px solid var(--color-border);
  }

  .member-panel {
    /* Remove fixed width constraint on mobile */
    width: 100%;
  }
}
```

---

## Edge Cases

| Situation | Handling |
|-----------|----------|
| Only 1 SIG | `::after` hidden via `:only-child`; `::before` still draws vertical from root |
| SIG with 0 members | Panel shows "No members" text |
| SIG with only regular members (no ADMIN) | Leads section not rendered; no divider |
| SIG with only leads (no regular MEMBER) | Regular section not rendered; no "more" button |
| SIG with `is_visible = false` | Wrapper gets `opacity-50`; dashed border on `.sig-node` |
| SIGs wrapping to 2nd row | 2nd-row nodes have their own local horizontal line (orphaned from root); acceptable trade-off |
| Regular members <= 10 | "more" button not rendered |

---

## What Does NOT Change

- All API calls and data fetching (`fetchData`, `getOrgChart`)
- All admin edit logic and inline form fields (override, sig description, bio)
- `OrgChartMember`, `OrgChartSig`, `OrgChartCategory`, `OrgChartResponse` types
- `roleBadgeVariant` mapping
- Forum Categories template logic (grid stays, only minor style tweaks)
- i18n keys (no new keys needed; "Show more"/"Show less" can use `t('common.showMore')` / `t('common.showLess')` if they exist, otherwise hardcode English)
- Test file (`OrgChartView.spec.ts`) — may need minor updates if selectors change

---

## Implementation Order

1. Add new `ref`s and helper functions to `<script setup>`
2. Add `ChevronDown`, `ChevronRight` to lucide import
3. Replace the SIGs `<section>` template block
4. Apply minor styling to Forum Categories creator row
5. Add `<style scoped>` block
6. Verify in browser: expand/collapse, truncation, admin edits, mobile layout
