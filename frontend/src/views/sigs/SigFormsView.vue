<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, inject, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getSigForms } from '@/api/sigs'
import { deleteForm as deleteFormApi, listFormResponses, getForm, exportForm } from '@/api/forms'
import { getTaskStatus } from '@/api/tasks'
import { getErrorMessage } from '@/utils/error'
import type { SigForm, FormResponse, Question, Sig } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const toastStore = useToastStore()

const sigId = computed(() => route.params.id as string)
const sig = inject<Ref<Sig | null>>('sig', ref(null))
const userSigRole = inject<Ref<string | null>>('userSigRole', ref(null))

const forms = ref<SigForm[]>([])
const total = ref(0)
const loading = ref(true)

const canCreateForm = computed(() => {
  if (auth.isAdmin) return true
  // If user is ADMIN or SUB_ADMIN in this SIG
  return userSigRole?.value === 'ADMIN' || userSigRole?.value === 'SUB_ADMIN'
})

async function fetchForms() {
  loading.value = true
  try {
    const data = await getSigForms(sigId.value)
    forms.value = data.forms
    total.value = data.total
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

// Form deletion
const showFormDeleteConfirm = ref(false)
const formToDelete = ref<string | null>(null)

function confirmDeleteForm(formId: string) {
  formToDelete.value = formId
  showFormDeleteConfirm.value = true
}

async function handleDeleteForm() {
  if (!formToDelete.value) return
  try {
    await deleteFormApi(formToDelete.value)
    await fetchForms()
    toastStore.show(t('sigs.forms.deleteSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.deleteError')), 'error')
  } finally {
    showFormDeleteConfirm.value = false
    formToDelete.value = null
  }
}

// Form response viewing
const showResponsesModal = ref(false)
const responsesFormId = ref('')
const responsesFormTitle = ref('')
const responses = ref<FormResponse[]>([])
const responsesPage = ref(1)
const responsesTotalPages = ref(1)
const responsesLoading = ref(false)
const responsesQuestions = ref<Question[]>([])

function resolveQuestionLabel(questionId: string): string {
  const q = responsesQuestions.value.find((q) => q.id === questionId)
  return q?.label || questionId
}

function resolveAnswerValue(questionId: string, value: unknown): string {
  const q = responsesQuestions.value.find((q) => q.id === questionId)
  if (!q) return String(value ?? '(None)')

  const optionMap = new Map((q.options || []).map((o) => [o.id, o.label]))

  if (Array.isArray(value)) {
    return value.map((v) => optionMap.get(String(v)) ?? String(v)).join(', ') || '(None)'
  }
  if (typeof value === 'string' && optionMap.has(value)) {
    return optionMap.get(value)!
  }
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>
    if (obj.filename) return String(obj.filename)
    return JSON.stringify(value)
  }
  return String(value ?? '(None)')
}

async function fetchResponses(formId: string, title: string, page = 1) {
  responsesFormId.value = formId
  responsesFormTitle.value = title
  responsesPage.value = page
  responsesLoading.value = true
  showResponsesModal.value = true
  try {
    const [formData, respData] = await Promise.all([
      page === 1 ? getForm(formId) : Promise.resolve(null),
      listFormResponses(formId, page),
    ])
    if (formData) {
      responsesQuestions.value = formData.questions
    }
    responses.value = respData.responses || []
    const totalResp = respData.total || 0
    responsesTotalPages.value = Math.ceil(totalResp / 20) || 1
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.fetchResponsesError')), 'error')
  } finally {
    responsesLoading.value = false
  }
}

// Form CSV export
const exportingFormId = ref<string | null>(null)
let exportPollTimer: ReturnType<typeof setInterval> | null = null
let isUnmounted = false

async function startExport(formId: string) {
  exportingFormId.value = formId
  try {
    const data = await exportForm(formId)
    pollExportStatus(formId, data.task_id)
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('forms.view.exportError')), 'error')
    exportingFormId.value = null
  }
}

function pollExportStatus(formId: string, taskId: string) {
  let attempts = 0
  exportPollTimer = setInterval(async () => {
    if (isUnmounted) {
      clearInterval(exportPollTimer!)
      exportPollTimer = null
      return
    }
    attempts++
    if (attempts > 30) {
      clearInterval(exportPollTimer!)
      exportPollTimer = null
      exportingFormId.value = null
      toastStore.show(t('forms.view.exportTimeout'), 'error')
      return
    }
    try {
      const data = await getTaskStatus(taskId)
      if (data.status === 'SUCCESS' && data.download_url) {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exportingFormId.value = null
        window.open(data.download_url, '_blank')
      } else if (data.status === 'FAILURE') {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exportingFormId.value = null
        toastStore.show(t('forms.view.exportFailed'), 'error')
      }
    } catch {
      /* continue polling */
    }
  }, 2000)
}

onMounted(fetchForms)
onUnmounted(() => {
  isUnmounted = true
  if (exportPollTimer) clearInterval(exportPollTimer)
})
</script>

<template>
  <div class="space-y-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        { label: sig?.name || '...', to: `/sigs/${sigId}` },
        { label: t('breadcrumb.forms') },
      ]"
    />
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-foreground">
        {{ t('sigs.forms.title') }} ({{ total }})
      </h2>
      <router-link v-if="canCreateForm" :to="`/sigs/${sigId}/forms/new`">
        <BaseButton size="md">{{ t('sigs.forms.createBtn') }}</BaseButton>
      </router-link>
    </div>

    <!-- Content -->
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2">
      <SkeletonLoader v-for="i in 2" :key="i" variant="card" :lines="3" />
    </div>

    <EmptyState
      v-else-if="forms.length === 0"
      :title="t('sigs.forms.emptyTitle')"
      :message="t('sigs.forms.emptyMessage')"
    />

    <div v-else class="grid gap-4 sm:grid-cols-2">
      <BaseCard
        v-for="f in forms"
        :key="f.id"
        class="h-full group hover:border-brand-300 transition-all flex flex-col"
      >
        <div class="flex items-start justify-between mb-3">
          <router-link
            :to="`/forms/${f.id}`"
            class="font-bold text-foreground group-hover:text-brand-600 transition-colors leading-tight"
          >
            {{ f.title }}
          </router-link>
          <BaseBadge :variant="f.is_active ? 'success' : 'neutral'" size="sm" class="shrink-0 ml-2">
            {{ f.is_active ? t('common.active') : t('common.closed') }}
          </BaseBadge>
        </div>

        <p v-if="f.description" class="text-xs text-muted mb-4 line-clamp-3">
          {{ f.description }}
        </p>

        <div class="mt-auto space-y-2">
          <div
            class="flex items-center flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted font-medium uppercase tracking-tight"
          >
            <span class="flex items-center gap-1"
              >{{ f.response_count }} {{ t('sigs.forms.responses') }}</span
            >
            <span v-if="f.deadline"
              >{{ t('sigs.forms.ends') }} {{ new Date(f.deadline).toLocaleDateString() }}</span
            >
            <span>{{ t('common.by') }} {{ f.created_by_name || 'Admin' }}</span>
          </div>

          <div
            v-if="f.user_is_sig_admin || auth.isAdmin"
            class="flex items-center gap-4 pt-3 mt-2 border-t border-border"
          >
            <router-link
              :to="`/forms/${f.id}/edit`"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
            >
              {{ t('sigs.forms.editBtn') }}
            </router-link>
            <button
              @click="fetchResponses(f.id, f.title)"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
            >
              {{ t('sigs.forms.responsesBtn') }}
            </button>
            <button
              @click="startExport(f.id)"
              :disabled="exportingFormId !== null"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ exportingFormId === f.id ? t('forms.view.exportStarting') : t('forms.view.exportCSVBtn') }}
            </button>
            <button
              v-if="f.created_by === auth.user?.id || auth.isAdmin"
              @click="confirmDeleteForm(f.id)"
              class="text-xs text-danger-600 hover:text-danger-700 font-medium hover:underline ml-auto"
            >
              {{ t('sigs.forms.deleteBtn') }}
            </button>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- Modals -->
    <BaseModal
      v-model="showFormDeleteConfirm"
      :title="t('sigs.forms.deleteConfirm.title')"
      size="sm"
    >
      <p class="text-sm text-muted mb-4 leading-relaxed">
        {{ t('sigs.forms.deleteConfirm.message') }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showFormDeleteConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="handleDeleteForm">{{
          t('sigs.forms.deleteConfirm.confirmBtn')
        }}</BaseButton>
      </template>
    </BaseModal>

    <BaseModal
      v-model="showResponsesModal"
      :title="`${t('sigs.forms.responsesBtn')}: ${responsesFormTitle}`"
      size="xl"
    >
      <div v-if="responsesLoading" class="py-12 flex justify-center">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
      <EmptyState v-else-if="responses.length === 0" :message="t('sigs.forms.noResponses')" />
      <div v-else class="max-h-[70vh] overflow-y-auto pr-2 space-y-4">
        <div
          v-for="resp in responses"
          :key="resp.id"
          class="border border-border rounded-lg p-5 bg-surface-alt/30"
        >
          <div class="flex items-center justify-between mb-4 pb-2 border-b border-border/50">
            <span class="font-bold text-foreground">{{ resp.display_name }}</span>
            <span class="text-[10px] text-muted font-mono">{{
              new Date(resp.created_at).toLocaleString()
            }}</span>
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div v-for="(value, key) in resp.answers" :key="key" class="space-y-1">
              <div class="text-[10px] font-bold text-muted uppercase tracking-wider">
                {{ resolveQuestionLabel(String(key)) }}
              </div>
              <div class="text-sm text-foreground">
                {{ resolveAnswerValue(String(key), value) }}
              </div>
            </div>
          </div>
        </div>

        <BasePagination
          v-if="responsesTotalPages > 1"
          :current-page="responsesPage"
          :total-pages="responsesTotalPages"
          class="mt-6 pt-4 border-t border-border"
          @update:current-page="
            (p: number) => fetchResponses(responsesFormId, responsesFormTitle, p)
          "
        />
      </div>
    </BaseModal>
  </div>
</template>
