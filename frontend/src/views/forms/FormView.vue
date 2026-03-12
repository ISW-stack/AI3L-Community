<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'
import type { Question, FormData } from '@/types'
import { getForm, submitForm as apiSubmitForm, exportForm } from '@/api/forms'
import { getTaskStatus } from '@/api/tasks'
import { uploadEditorFile } from '@/api/files'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formId = computed(() => route.params.formId as string)
const form = ref<FormData | null>(null)
const answers = ref<Record<string, any>>({})
const loading = ref(true)
const submitting = ref(false)
const submitted = ref(false)
const message = ref('')
const error = ref('')
const exporting = ref(false)
const exportStatus = ref('')
let exportPollTimer: ReturnType<typeof setInterval> | null = null
let isUnmounted = false

const canEdit = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin || auth.user?.id === form.value.created_by
})
const canExport = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin
})
const formShareUrl = computed(() => `${window.location.origin}/forms/${formId.value}`)

async function fetchForm() {
  loading.value = true
  try {
    const data = await getForm(formId.value)
    form.value = data
    for (const q of data.questions) {
      answers.value[q.id] = q.type === 'multiple_choice' ? [] : q.type === 'rating' ? null : ''
    }
  } catch {
    error.value = t('forms.view.loadError')
  } finally {
    loading.value = false
  }
}

function validateAnswers(): string | null {
  if (!form.value) return t('forms.view.loadError')
  for (const q of form.value.questions) {
    const val = answers.value[q.id]
    if (q.required) {
      if (val === null || val === undefined || val === '')
        return `"${q.label}" ${t('common.required').toLowerCase()}.`
      if (Array.isArray(val) && val.length === 0)
        return `"${q.label}" ${t('common.required').toLowerCase()}.`
    }
    if (val === null || val === undefined || val === '' || (Array.isArray(val) && val.length === 0))
      continue
    if (
      (q.type === 'text' || q.type === 'textarea') &&
      q.max_length &&
      typeof val === 'string' &&
      val.length > q.max_length
    )
      return `"${q.label}" exceeds maximum length of ${q.max_length}.`
  }
  return null
}

async function submitForm() {
  error.value = ''
  const validationError = validateAnswers()
  if (validationError) {
    error.value = validationError
    return
  }
  submitting.value = true
  try {
    const cleanAnswers: Record<string, any> = {}
    for (const [key, val] of Object.entries(answers.value)) {
      if (
        val !== null &&
        val !== undefined &&
        val !== '' &&
        !(Array.isArray(val) && val.length === 0)
      )
        cleanAnswers[key] = val
    }

    // Upload any pending files before submitting
    for (const [key, val] of Object.entries(cleanAnswers)) {
      if (val instanceof File) {
        const data = await uploadEditorFile(val)
        cleanAnswers[key] = { key: data.key || data.url, filename: val.name }
      }
    }

    await apiSubmitForm(formId.value, cleanAnswers)
    submitted.value = true
    message.value = t('forms.view.successMessage')
  } catch (e: unknown) {
    if (
      e != null &&
      typeof e === 'object' &&
      'response' in e &&
      (e as { response?: { status?: number } }).response?.status === 409
    ) {
      submitted.value = true
      message.value = 'You have already submitted a response to this form.'
    } else {
      error.value = getErrorMessage(e, t('forms.view.submitError'))
    }
  } finally {
    submitting.value = false
  }
}

function handleFileUpload(questionId: string, event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  // Store the raw File; it will be uploaded during submitForm()
  answers.value[questionId] = file
}

function isFileObject(val: unknown): val is File {
  return val instanceof File
}

function getFileName(val: unknown): string {
  if (val instanceof File) return val.name
  if (val && typeof val === 'object' && 'filename' in val)
    return (val as { filename: string }).filename
  return ''
}

function toggleMultipleChoice(questionId: string, optionId: string) {
  if (!Array.isArray(answers.value[questionId])) {
    answers.value[questionId] = []
  }
  const arr = answers.value[questionId] as string[]
  const idx = arr.indexOf(optionId)
  if (idx === -1) arr.push(optionId)
  else arr.splice(idx, 1)
}

function ratingRange(q: Question): number[] {
  const min = q.min ?? 1
  const max = q.max ?? 5
  const range: number[] = []
  for (let i = min; i <= max; i++) range.push(i)
  return range
}

async function startExport() {
  exporting.value = true
  exportStatus.value = t('forms.view.exportStarting')
  try {
    const data = await exportForm(formId.value)
    pollExportStatus(data.task_id)
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('forms.view.exportError'))
    exporting.value = false
    exportStatus.value = ''
  }
}

function pollExportStatus(taskId: string) {
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
      exporting.value = false
      exportStatus.value = ''
      error.value = t('forms.view.exportTimeout')
      return
    }
    try {
      const data = await getTaskStatus(taskId)
      exportStatus.value = `${t('forms.view.exportStatus')} ${data.status}`
      if (data.status === 'SUCCESS' && data.download_url) {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exporting.value = false
        exportStatus.value = ''
        window.open(data.download_url, '_blank')
      } else if (data.status === 'FAILURE') {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exporting.value = false
        exportStatus.value = ''
        error.value = t('forms.view.exportFailed')
      }
    } catch {
      /* continue */
    }
  }, 2000)
}

onMounted(() => fetchForm())
onUnmounted(() => {
  isUnmounted = true
  if (exportPollTimer) clearInterval(exportPollTimer)
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="mb-6">
      <button @click="router.back()" class="text-sm text-brand-600 hover:underline">
        &larr; {{ t('forms.view.backBtn') }}
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />
    <div v-else-if="!form" class="text-center py-12">
      <p class="text-muted mb-4">{{ t('forms.view.notFound') }}</p>
    </div>

    <template v-else>
      <div v-if="form.banner_url" class="mb-6">
        <img
          :src="form.banner_url"
          alt="Form banner"
          loading="lazy"
          class="w-full h-48 object-cover rounded-lg"
          width="768"
          height="192"
        />
      </div>

      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-foreground mb-2">{{ form.title }}</h1>
            <div
              v-if="form.description"
              class="prose prose-sm max-w-none text-muted mb-3"
              v-html="form.description"
            ></div>
          </div>
          <BaseBadge :variant="form.is_active ? 'success' : 'danger'">{{
            form.is_active ? t('common.active') : t('common.closed')
          }}</BaseBadge>
        </div>
        <div class="flex items-center gap-4 text-xs text-muted mt-2">
          <span>{{ t('common.by') }} {{ form.created_by_name }}</span>
          <span>{{ form.response_count }} {{ t('forms.view.response') }}</span>
          <span v-if="form.deadline"
            >{{ t('forms.view.deadline') }} {{ new Date(form.deadline).toLocaleString() }}</span
          >
          <span v-if="form.max_respondents"
            >{{ t('forms.view.max') }} {{ form.max_respondents }}</span
          >
        </div>
        <div v-if="auth.isAuthenticated" class="flex items-center gap-2 mt-4">
          <CopyShareLinkButton :url="formShareUrl" />
          <router-link
            v-if="canEdit"
            :to="`/forms/${form.id}/edit`"
            class="text-sm text-brand-600 hover:underline"
            >{{ t('forms.view.editFormBtn') }}</router-link
          >
          <BaseButton
            v-if="canExport"
            variant="secondary"
            size="sm"
            :loading="exporting"
            @click="startExport"
            >{{ t('forms.view.exportCSVBtn') }}</BaseButton
          >
          <span v-if="exportStatus" class="text-xs text-muted">{{ exportStatus }}</span>
        </div>
      </BaseCard>

      <BaseAlert v-if="!form.is_active" type="error" class="mb-6 text-center">{{
        t('forms.view.closedAlert')
      }}</BaseAlert>
      <BaseAlert v-if="submitted" type="success" class="mb-6 text-center">{{ message }}</BaseAlert>
      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <div
        v-if="!submitted && form.is_active && auth.isAuthenticated && !auth.isGuest"
        class="space-y-4"
      >
        <BaseCard v-for="q in form.questions" :key="q.id">
          <label class="block text-sm font-medium text-foreground mb-2">
            {{ q.label }}<span v-if="q.required" class="text-danger-500"> *</span>
          </label>

          <input
            v-if="q.type === 'text'"
            v-model="answers[q.id]"
            type="text"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
          />

          <textarea
            v-else-if="q.type === 'textarea'"
            v-model="answers[q.id]"
            rows="4"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
          ></textarea>

          <div v-else-if="q.type === 'single_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="radio"
                :name="formId + '-' + q.id"
                :value="opt.id"
                v-model="answers[q.id]"
                class="text-brand-600"
              />{{ opt.label }}
            </label>
          </div>

          <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                :value="opt.id"
                :checked="(answers[q.id] as string[]).includes(opt.id)"
                @change="toggleMultipleChoice(q.id, opt.id)"
                class="rounded text-brand-600"
              />{{ opt.label }}
            </label>
          </div>

          <select
            v-else-if="q.type === 'dropdown'"
            v-model="answers[q.id]"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
          >
            <option value="">{{ t('forms.view.selectOptionPlaceholder') }}</option>
            <option v-for="opt in q.options" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>

          <div v-else-if="q.type === 'rating'" class="flex items-center gap-1">
            <button
              v-for="n in ratingRange(q)"
              :key="n"
              @click="answers[q.id] = n"
              type="button"
              class="w-10 h-10 rounded-lg text-sm font-medium transition"
              :class="
                answers[q.id] === n
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface-alt text-muted hover:bg-gray-100'
              "
            >
              {{ n }}
            </button>
          </div>

          <div v-else-if="q.type === 'file_upload'">
            <input
              type="file"
              @change="handleFileUpload(q.id, $event)"
              class="text-sm text-muted"
            />
            <p
              v-if="isFileObject(answers[q.id]) || answers[q.id]?.filename"
              class="text-xs text-success-600 mt-1"
            >
              {{ t('forms.view.uploadedFile') }} {{ getFileName(answers[q.id]) }}
            </p>
            <p v-if="q.allowed_types && q.allowed_types.length" class="text-xs text-muted mt-1">
              {{ t('forms.view.allowedTypes') }} {{ q.allowed_types.join(', ') }}
            </p>
          </div>

          <p
            v-if="(q.type === 'text' || q.type === 'textarea') && q.max_length"
            class="text-xs text-muted mt-1 text-right"
          >
            {{ (answers[q.id] as string)?.length || 0 }} / {{ q.max_length }}
          </p>
        </BaseCard>

        <div class="flex justify-end pt-4">
          <BaseButton size="lg" :loading="submitting" @click="submitForm">{{
            t('forms.view.submitBtn')
          }}</BaseButton>
        </div>
      </div>

      <BaseAlert v-if="!auth.isAuthenticated && form.is_active" type="info" class="text-center">
        {{ t('forms.view.loginPrompt') }}
        <router-link to="/login" class="text-brand-600 hover:underline font-medium">{{
          t('forms.view.loginLink')
        }}</router-link>
        {{ t('forms.view.submitPromptSuffix') }}
      </BaseAlert>
    </template>
  </div>
</template>
