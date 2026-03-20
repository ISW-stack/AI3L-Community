<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getOrgChart, updateOverride, updateSigDescription, updateMemberBio } from '@/api/about'
import type { OrgChartResponse, OrgChartSig, OrgChartCategory } from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { getErrorMessage } from '@/utils/error'
import { Settings, Pencil } from 'lucide-vue-next'

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

const roleBadgeVariant: Record<string, 'danger' | 'orange' | 'brand' | 'neutral' | 'purple'> = {
  ADMIN: 'danger',
  SUB_ADMIN: 'orange',
  MEMBER: 'brand',
}

async function fetchData() {
  loading.value = true
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

function handleAvatarError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
  const parent = img.parentElement
  if (parent) {
    const fallback = parent.querySelector('.avatar-fallback') as HTMLElement | null
    if (fallback) fallback.style.display = 'flex'
  }
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
      <section class="mb-12">
        <h2 class="text-2xl font-semibold text-foreground mb-6">{{ t('orgChart.sigs') }}</h2>

        <div v-if="data.sigs.length === 0" class="text-muted">{{ t('orgChart.noSigs') }}</div>

        <div class="space-y-6">
          <div
            v-for="sig in data.sigs"
            :key="sig.id"
            class="bg-surface border border-border rounded-xl p-6"
            :class="{ 'border-dashed border-muted/40': sig.override?.is_visible === false }"
          >
            <div class="flex items-start justify-between mb-3">
              <div>
                <div class="flex items-center gap-2">
                  <router-link
                    :to="`/sigs/${sig.id}`"
                    class="text-lg font-semibold text-brand-600 hover:text-brand-700 transition"
                  >
                    {{ sig.override?.custom_title || sig.name }}
                  </router-link>
                  <BaseBadge v-if="sig.override?.is_visible === false" variant="neutral" size="sm">
                    {{ t('orgChart.hidden') }}
                  </BaseBadge>
                </div>
                <p v-if="sig.org_chart_description" class="text-sm text-muted mt-1">
                  {{ sig.org_chart_description }}
                </p>
                <p v-else-if="sig.description" class="text-sm text-muted mt-1">
                  {{ sig.description }}
                </p>
                <span class="text-xs text-muted">
                  {{ sig.member_count }} {{ t('orgChart.memberCount') }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <button
                  v-if="canEditSigDesc(sig)"
                  class="p-1.5 text-muted hover:text-foreground transition rounded"
                  :title="t('orgChart.editDescription')"
                  @click="startEditSigDesc(sig)"
                >
                  <Pencil class="w-4 h-4" aria-hidden="true" />
                </button>
                <button
                  v-if="isSuperAdmin"
                  class="p-1.5 text-muted hover:text-foreground transition rounded"
                  :title="t('orgChart.editOverride')"
                  @click="startEditOverride('sig', sig.id, sig)"
                >
                  <Settings class="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            <!-- Inline override edit -->
            <div
              v-if="editingOverride?.type === 'sig' && editingOverride.id === sig.id"
              class="bg-surface-alt border border-border rounded-lg p-4 mb-4"
            >
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                <div>
                  <label class="text-xs font-medium text-muted">{{
                    t('orgChart.customTitle')
                  }}</label>
                  <input
                    v-model="overrideForm.custom_title"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                    maxlength="200"
                  />
                </div>
                <div>
                  <label class="text-xs font-medium text-muted">{{
                    t('orgChart.displayOrder')
                  }}</label>
                  <input
                    v-model.number="overrideForm.display_order"
                    type="number"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                  />
                </div>
                <div class="flex items-end gap-2">
                  <label class="flex items-center gap-2 text-sm text-foreground">
                    <input v-model="overrideForm.is_visible" type="checkbox" />
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
            <div
              v-if="editingSigDesc === sig.id"
              class="bg-surface-alt border border-border rounded-lg p-4 mb-4"
            >
              <label class="text-xs font-medium text-muted">{{
                t('orgChart.sigDescription')
              }}</label>
              <textarea
                v-model="sigDescForm"
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

            <!-- Members -->
            <div class="flex flex-wrap gap-4 mt-4">
              <div
                v-for="member in sig.members"
                :key="member.user_id"
                class="flex items-center gap-3 bg-surface-alt border border-border rounded-lg px-4 py-3"
              >
                <router-link :to="`/users/${member.user_id}`" class="shrink-0">
                  <div class="relative w-10 h-10">
                    <img
                      v-if="member.avatar_url"
                      :src="member.avatar_url"
                      :alt="member.display_name"
                      class="w-10 h-10 rounded-full object-cover border border-border"
                      @error="handleAvatarError"
                    />
                    <div
                      class="avatar-fallback w-10 h-10 rounded-full bg-brand-100 text-brand-700 items-center justify-center text-sm font-semibold absolute inset-0"
                      :style="{ display: member.avatar_url ? 'none' : 'flex' }"
                    >
                      {{ member.display_name.charAt(0).toUpperCase() }}
                    </div>
                  </div>
                </router-link>
                <div class="min-w-0">
                  <router-link
                    :to="`/users/${member.user_id}`"
                    class="text-sm font-medium text-foreground hover:text-brand-600 transition truncate block"
                  >
                    {{ member.display_name }}
                  </router-link>
                  <div class="flex items-center gap-2 mt-0.5">
                    <BaseBadge
                      :variant="roleBadgeVariant[member.role] || 'neutral'"
                      size="sm"
                    >
                      {{ member.role.replace('_', ' ') }}
                    </BaseBadge>
                  </div>
                  <p v-if="member.org_chart_bio" class="text-xs text-muted mt-1 line-clamp-2">
                    {{ member.org_chart_bio }}
                  </p>
                </div>
                <button
                  v-if="canEditMyBio(sig) && member.user_id === auth.user?.id"
                  class="p-1 text-muted hover:text-foreground transition"
                  :title="t('orgChart.editBio')"
                  @click="startEditBio(sig.id, member.org_chart_bio)"
                >
                  <Pencil class="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            </div>

            <!-- Inline bio edit -->
            <div
              v-if="editingBio?.sigId === sig.id"
              class="bg-surface-alt border border-border rounded-lg p-4 mt-3"
            >
              <label class="text-xs font-medium text-muted">{{ t('orgChart.myBio') }}</label>
              <textarea
                v-model="bioForm"
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
                <div class="relative w-6 h-6">
                  <img
                    v-if="cat.creator_avatar_url"
                    :src="cat.creator_avatar_url"
                    :alt="cat.creator_display_name"
                    class="w-6 h-6 rounded-full object-cover"
                    @error="handleAvatarError"
                  />
                  <div
                    class="avatar-fallback w-6 h-6 rounded-full bg-brand-100 text-brand-700 items-center justify-center text-xs font-semibold absolute inset-0"
                    :style="{ display: cat.creator_avatar_url ? 'none' : 'flex' }"
                  >
                    {{ cat.creator_display_name.charAt(0).toUpperCase() }}
                  </div>
                </div>
              </router-link>
              <span class="text-xs text-muted">
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
                  <label class="text-xs font-medium text-muted">{{
                    t('orgChart.customTitle')
                  }}</label>
                  <input
                    v-model="overrideForm.custom_title"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                    maxlength="200"
                  />
                </div>
                <div>
                  <label class="text-xs font-medium text-muted">{{
                    t('orgChart.displayOrder')
                  }}</label>
                  <input
                    v-model.number="overrideForm.display_order"
                    type="number"
                    class="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded bg-surface text-foreground"
                  />
                </div>
                <label class="flex items-center gap-2 text-sm text-foreground">
                  <input v-model="overrideForm.is_visible" type="checkbox" />
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
