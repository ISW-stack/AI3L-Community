<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { sanitizeHtml } from '@/utils/sanitize'
import { useAuthStore } from '@/stores/auth'
import { getOrgChart, updateOverride, updateSigDescription, updateMemberBio } from '@/api/about'
import type {
  OrgChartResponse,
  OrgChartSig,
  OrgChartCategory,
  OrgChartMember,
} from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { getErrorMessage } from '@/utils/error'
import { Settings, Pencil, ChevronDown, ChevronRight } from 'lucide-vue-next'

const { t } = useI18n()
const auth = useAuthStore()
const loading = ref(true)
const data = ref<OrgChartResponse | null>(null)
const error = ref('')

const isSuperAdmin = computed(() => auth.isSuperAdmin)

// Inline edit state
const editingOverride = ref<{ type: string; id: string } | null>(null)
const overrideForm = ref({ custom_title: '', display_order: 0, is_visible: true })
const editingSigDesc = ref<string | null>(null)
const sigDescForm = ref('')
const editingBio = ref<{ sigId: string } | null>(null)
const bioForm = ref('')
const saving = ref(false)

const expandedSigs = ref<Set<string>>(new Set())
const failedAvatars = ref<Set<string>>(new Set())
const showAllMembers = ref<Set<string>>(new Set())
const MEMBER_PREVIEW_COUNT = 10

const roleBadgeVariant: Record<string, 'danger' | 'orange' | 'brand' | 'neutral' | 'purple'> = {
  ADMIN: 'danger',
  SUB_ADMIN: 'orange',
  MEMBER: 'brand',
}

async function fetchData() {
  loading.value = true
  failedAvatars.value.clear()
  try {
    data.value = await getOrgChart()
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    loading.value = false
  }
}

function startEditOverride(type: string, id: string, sig?: OrgChartSig, cat?: OrgChartCategory) {
  editingOverride.value = { type, id }
  const override = sig?.override ?? cat?.override
  overrideForm.value = {
    custom_title: override?.custom_title ?? '',
    display_order: override?.display_order ?? 0,
    is_visible: override?.is_visible ?? true,
  }
}

async function saveOverride() {
  if (!editingOverride.value) return
  saving.value = true
  try {
    await updateOverride(editingOverride.value.type, editingOverride.value.id, {
      custom_title: overrideForm.value.custom_title || null,
      display_order: overrideForm.value.display_order,
      is_visible: overrideForm.value.is_visible,
    })
    editingOverride.value = null
    await fetchData()
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    saving.value = false
  }
}

function startEditSigDesc(sig: OrgChartSig) {
  editingSigDesc.value = sig.id
  sigDescForm.value = sig.org_chart_description ?? ''
}

async function saveSigDesc() {
  if (!editingSigDesc.value) return
  saving.value = true
  try {
    await updateSigDescription(editingSigDesc.value, sigDescForm.value || null)
    editingSigDesc.value = null
    await fetchData()
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    saving.value = false
  }
}

function canEditSigDesc(sig: OrgChartSig): boolean {
  if (isSuperAdmin.value) return true
  const userId = auth.user?.id
  if (!userId) return false
  return sig.members.some(
    (m) => m.user_id === userId && (m.role === 'ADMIN' || m.role === 'SUB_ADMIN'),
  )
}

function canEditMyBio(sig: OrgChartSig): boolean {
  const userId = auth.user?.id
  if (!userId) return false
  return sig.members.some((m) => m.user_id === userId)
}

function startEditBio(sigId: string, currentBio: string | null) {
  editingBio.value = { sigId }
  bioForm.value = currentBio ?? ''
}

async function saveBio() {
  if (!editingBio.value) return
  saving.value = true
  try {
    await updateMemberBio(editingBio.value.sigId, bioForm.value || null)
    editingBio.value = null
    await fetchData()
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    saving.value = false
  }
}

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
    leads: members.filter((m) => m.role === 'ADMIN' || m.role === 'SUB_ADMIN'),
    regular: members.filter((m) => m.role === 'MEMBER'),
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

function handleAvatarError(userId: string) {
  failedAvatars.value.add(userId)
}

onMounted(fetchData)
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold text-foreground mb-2">{{ t('orgChart.title') }}</h1>
    <p class="text-muted mb-8">{{ t('orgChart.subtitle') }}</p>

    <div v-if="error" class="text-danger-600 mb-4">{{ error }}</div>

    <div v-if="loading">
      <SkeletonLoader variant="list" :lines="6" />
    </div>

    <template v-else-if="data">
      <!-- SIGs Section -->
      <section class="mb-16">
        <h2 class="text-2xl font-semibold text-foreground mb-6">{{ t('orgChart.sigs') }}</h2>

        <!-- Root node -->
        <div class="flex flex-col items-center mt-6">
          <div class="root-node">AI3L Community</div>

          <!-- Tree row: connector lines drawn by CSS -->
          <div v-if="data.sigs.length > 0" class="tree-row">
            <div
              v-for="sig in data.sigs"
              :key="sig.id"
              class="tree-node-wrapper"
              :class="{ 'opacity-50': sig.override?.is_visible === false }"
            >
              <!-- SIG card / clickable node -->
              <button class="sig-node" @click="toggleSig(sig.id)">
                <div class="sig-node-header">
                  <component
                    :is="expandedSigs.has(sig.id) ? ChevronDown : ChevronRight"
                    class="w-4 h-4 shrink-0"
                  />
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
                <button
                  v-if="canEditSigDesc(sig)"
                  :title="t('orgChart.editDescription')"
                  @click.stop="startEditSigDesc(sig)"
                >
                  <Pencil class="w-3.5 h-3.5" />
                </button>
                <button
                  v-if="isSuperAdmin"
                  :title="t('orgChart.editOverride')"
                  @click.stop="startEditOverride('sig', sig.id, sig)"
                >
                  <Settings class="w-3.5 h-3.5" />
                </button>
              </div>

              <!-- Inline override edit -->
              <div
                v-if="editingOverride?.type === 'sig' && editingOverride.id === sig.id"
                class="node-edit-form"
              >
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                  <div>
                    <label for="org-custom-title" class="text-xs font-medium text-muted">{{
                      t('orgChart.customTitle')
                    }}</label>
                    <input
                      id="org-custom-title"
                      v-model="overrideForm.custom_title"
                      name="custom-title"
                      class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                      maxlength="200"
                    />
                  </div>
                  <div>
                    <label for="org-display-order" class="text-xs font-medium text-muted">{{
                      t('orgChart.displayOrder')
                    }}</label>
                    <input
                      id="org-display-order"
                      v-model.number="overrideForm.display_order"
                      type="number"
                      name="display-order"
                      class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                    />
                  </div>
                  <div class="flex items-end gap-2">
                    <label class="flex items-center gap-2 text-sm text-foreground">
                      <input v-model="overrideForm.is_visible" type="checkbox" name="is-visible" />
                      {{ t('orgChart.visible') }}
                    </label>
                  </div>
                </div>
                <div class="flex gap-2">
                  <button
                    class="px-3 py-1.5 text-sm bg-brand-600 text-white rounded hover:bg-brand-700 transition"
                    :disabled="saving"
                    @click="saveOverride"
                  >
                    {{ t('common.save') }}
                  </button>
                  <button
                    class="px-3 py-1.5 text-sm text-muted hover:text-foreground transition"
                    @click="editingOverride = null"
                  >
                    {{ t('common.cancel') }}
                  </button>
                </div>
              </div>

              <!-- Inline sig description edit -->
              <div v-if="editingSigDesc === sig.id" class="node-edit-form">
                <label for="org-sig-desc" class="text-xs font-medium text-muted">{{
                  t('orgChart.sigDescription')
                }}</label>
                <textarea
                  id="org-sig-desc"
                  v-model="sigDescForm"
                  name="sig-description"
                  class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                  rows="3"
                  maxlength="1000"
                />
                <div class="flex gap-2 mt-2">
                  <button
                    class="px-3 py-1.5 text-sm bg-brand-600 text-white rounded hover:bg-brand-700 transition"
                    :disabled="saving"
                    @click="saveSigDesc"
                  >
                    {{ t('common.save') }}
                  </button>
                  <button
                    class="px-3 py-1.5 text-sm text-muted hover:text-foreground transition"
                    @click="editingSigDesc = null"
                  >
                    {{ t('common.cancel') }}
                  </button>
                </div>
              </div>

              <!-- Connector line: node -> member panel -->
              <div
                v-if="expandedSigs.has(sig.id)"
                class="node-to-panel-line"
                aria-hidden="true"
              ></div>

              <!-- Expanded member panel -->
              <Transition name="panel-expand">
                <div v-if="expandedSigs.has(sig.id)" class="member-panel">
                  <!-- SIG description -->
                  <p v-if="sig.org_chart_description || sig.description" class="sig-panel-desc">
                    {{ sig.org_chart_description || sig.description }}
                  </p>

                  <!-- Leads: ADMIN + SUB_ADMIN with avatar -->
                  <div v-if="groupMembers(sig.members).leads.length > 0" class="member-section">
                    <div
                      v-for="m in groupMembers(sig.members).leads"
                      :key="m.user_id"
                      class="lead-member-row"
                    >
                      <!-- Avatar -->
                      <router-link :to="`/users/${m.user_id}`" class="shrink-0">
                        <div class="w-9 h-9">
                          <img
                            v-if="m.avatar_url && !failedAvatars.has(m.user_id)"
                            :src="m.avatar_url"
                            :alt="m.display_name"
                            class="w-9 h-9 rounded-full object-cover border border-border"
                            @error="handleAvatarError(m.user_id)"
                          />
                          <div
                            v-else
                            class="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-semibold"
                          >
                            {{ m.display_name.charAt(0).toUpperCase() }}
                          </div>
                        </div>
                      </router-link>
                      <!-- Info -->
                      <div class="min-w-0">
                        <router-link
                          :to="`/users/${m.user_id}`"
                          class="text-sm font-medium text-foreground hover:text-brand-600 transition truncate block"
                        >
                          {{ m.display_name }}
                        </router-link>
                        <div class="flex items-center gap-1.5 mt-0.5">
                          <BaseBadge :variant="roleBadgeVariant[m.role] || 'neutral'" size="sm">
                            {{ m.role.replace('_', ' ') }}
                          </BaseBadge>
                        </div>
                        <p
                          v-if="m.org_chart_bio"
                          class="text-xs text-muted mt-0.5 line-clamp-1"
                          :title="m.org_chart_bio"
                          v-html="sanitizeHtml(m.org_chart_bio)"
                        ></p>
                      </div>
                      <!-- Edit bio button -->
                      <button
                        v-if="canEditMyBio(sig) && m.user_id === auth.user?.id"
                        class="p-1 text-muted hover:text-foreground transition shrink-0"
                        :title="t('orgChart.editBio')"
                        @click.stop="startEditBio(sig.id, m.org_chart_bio)"
                      >
                        <Pencil class="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  <!-- Divider (only if both leads and regular exist) -->
                  <div
                    v-if="
                      groupMembers(sig.members).leads.length > 0 &&
                      groupMembers(sig.members).regular.length > 0
                    "
                    class="border-t border-border my-2"
                  ></div>

                  <!-- Regular members: name only, no avatar -->
                  <div v-if="groupMembers(sig.members).regular.length > 0" class="member-section">
                    <div
                      v-for="m in visibleRegularMembers(sig)"
                      :key="m.user_id"
                      class="regular-member-row"
                    >
                      <span class="text-muted text-xs mr-1">•</span>
                      <router-link
                        :to="`/users/${m.user_id}`"
                        class="text-sm text-foreground hover:text-brand-600 transition truncate"
                      >
                        {{ m.display_name }}
                      </router-link>
                      <!-- Edit bio button -->
                      <button
                        v-if="canEditMyBio(sig) && m.user_id === auth.user?.id"
                        class="p-1 text-muted hover:text-foreground transition shrink-0 ml-auto"
                        :title="t('orgChart.editBio')"
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
                      <span v-if="!showAllMembers.has(sig.id)"
                        >+{{ hiddenMemberCount(sig) }} more</span
                      >
                      <span v-else>Show less</span>
                    </button>
                  </div>

                  <!-- Empty state -->
                  <p v-if="sig.members.length === 0" class="text-xs text-muted text-center py-2">
                    No members
                  </p>

                  <!-- Inline bio edit form -->
                  <div v-if="editingBio?.sigId === sig.id" class="node-edit-form mt-2">
                    <label for="org-bio" class="text-xs font-medium text-muted">{{
                      t('orgChart.myBio')
                    }}</label>
                    <textarea
                      id="org-bio"
                      v-model="bioForm"
                      name="bio"
                      class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                      rows="2"
                      maxlength="500"
                    />
                    <div class="flex gap-2 mt-2">
                      <button
                        class="px-3 py-1.5 text-sm bg-brand-600 text-white rounded hover:bg-brand-700 transition"
                        :disabled="saving"
                        @click="saveBio"
                      >
                        {{ t('common.save') }}
                      </button>
                      <button
                        class="px-3 py-1.5 text-sm text-muted hover:text-foreground transition"
                        @click="editingBio = null"
                      >
                        {{ t('common.cancel') }}
                      </button>
                    </div>
                  </div>
                </div>
              </Transition>
            </div>
          </div>

          <div v-else class="text-muted mt-4">{{ t('orgChart.noSigs') }}</div>
        </div>
      </section>

      <!-- Forum Categories Section -->
      <section>
        <h2 class="text-2xl font-semibold text-foreground mb-6">
          {{ t('orgChart.forumCategories') }}
        </h2>

        <div v-if="data.categories.length === 0" class="text-muted">
          {{ t('orgChart.noCategories') }}
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="cat in data.categories"
            :key="cat.id"
            class="bg-surface border border-border rounded-xl p-5"
            :class="{ 'border-dashed border-muted/40': cat.override?.is_visible === false }"
          >
            <div class="flex items-start justify-between mb-2">
              <div class="flex items-center gap-2">
                <h3 class="text-base font-semibold text-foreground">
                  {{ cat.override?.custom_title || cat.name }}
                </h3>
                <BaseBadge v-if="cat.override?.is_visible === false" variant="neutral" size="sm">
                  {{ t('orgChart.hidden') }}
                </BaseBadge>
              </div>
              <button
                v-if="isSuperAdmin"
                class="p-1 text-muted hover:text-foreground transition"
                :title="t('orgChart.editOverride')"
                @click="startEditOverride('category', cat.id, undefined, cat)"
              >
                <Settings class="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
            <p v-if="cat.description" class="text-sm text-muted mb-3">{{ cat.description }}</p>
            <div v-if="cat.creator_display_name" class="flex items-center gap-2 mt-2">
              <router-link v-if="cat.creator_id" :to="`/users/${cat.creator_id}`" class="shrink-0">
                <div class="w-8 h-8">
                  <img
                    v-if="cat.creator_avatar_url && !failedAvatars.has(cat.creator_id ?? '')"
                    :src="cat.creator_avatar_url"
                    :alt="cat.creator_display_name"
                    class="w-8 h-8 rounded-full object-cover"
                    @error="handleAvatarError(cat.creator_id ?? '')"
                  />
                  <div
                    v-else
                    class="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold"
                  >
                    {{ cat.creator_display_name.charAt(0).toUpperCase() }}
                  </div>
                </div>
              </router-link>
              <span class="text-xs text-muted font-medium">
                {{ t('common.by') }} {{ cat.creator_display_name }}
              </span>
            </div>

            <!-- Inline override edit for category -->
            <div
              v-if="editingOverride?.type === 'category' && editingOverride.id === cat.id"
              class="bg-surface-alt border border-border rounded-lg p-4 mt-3"
            >
              <div class="space-y-3 mb-3">
                <div>
                  <label for="org-custom-title" class="text-xs font-medium text-muted">{{
                    t('orgChart.customTitle')
                  }}</label>
                  <input
                    id="org-custom-title"
                    v-model="overrideForm.custom_title"
                    name="custom-title"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                    maxlength="200"
                  />
                </div>
                <div>
                  <label for="org-display-order" class="text-xs font-medium text-muted">{{
                    t('orgChart.displayOrder')
                  }}</label>
                  <input
                    id="org-display-order"
                    v-model.number="overrideForm.display_order"
                    type="number"
                    name="display-order"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                  />
                </div>
                <label class="flex items-center gap-2 text-sm text-foreground">
                  <input v-model="overrideForm.is_visible" type="checkbox" name="is-visible" />
                  {{ t('orgChart.visible') }}
                </label>
              </div>
              <div class="flex gap-2">
                <button
                  class="px-3 py-1.5 text-sm bg-brand-600 text-white rounded hover:bg-brand-700 transition"
                  :disabled="saving"
                  @click="saveOverride"
                >
                  {{ t('common.save') }}
                </button>
                <button
                  class="px-3 py-1.5 text-sm text-muted hover:text-foreground transition"
                  @click="editingOverride = null"
                >
                  {{ t('common.cancel') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
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
  flex-wrap: wrap;
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
  width: 200px;
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

.tree-node-wrapper:first-child::after {
  left: 50%;
  right: 0;
}
.tree-node-wrapper:last-child::after {
  left: 0;
  right: 50%;
}
.tree-node-wrapper:not(:first-child):not(:last-child)::after {
  left: 0;
  right: 0;
}
.tree-node-wrapper:only-child::after {
  display: none;
}

/* ── SIG node card ────────────────────────────────── */
.sig-node {
  width: 100%;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
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
  padding-left: 1.375rem;
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
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.panel-expand-enter-from,
.panel-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 767px) {
  .tree-row {
    flex-direction: column;
    align-items: stretch;
    padding-top: 1rem;
    gap: 0.5rem;
  }

  .tree-row::before,
  .tree-node-wrapper::before,
  .tree-node-wrapper::after {
    display: none;
  }

  .tree-node-wrapper {
    padding-top: 0;
    width: 100%;
    padding-left: 1.25rem;
    border-left: 2px solid var(--color-border);
  }

  .member-panel {
    width: 100%;
  }
}
</style>
