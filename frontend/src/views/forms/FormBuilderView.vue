<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Question } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { getForm, createForm, updateForm } from '@/api/forms'
import { uploadEditorFile } from '@/api/files'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import TiptapEditor from '@/components/TiptapEditor.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()

const QUESTION_TYPES = [
  { value: 'text', key: 'forms.builder.questionType.shortText' },
  { value: 'textarea', key: 'forms.builder.questionType.longText' },
  { value: 'single_choice', key: 'forms.builder.questionType.singleChoice' },
  { value: 'multiple_choice', key: 'forms.builder.questionType.multipleChoice' },
  { value: 'dropdown', key: 'forms.builder.questionType.dropdown' },
  { value: 'rating', key: 'forms.builder.questionType.rating' },
  { value: 'file_upload', key: 'forms.builder.questionType.fileUpload' },
]

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.formId)
const formId = computed(() => route.params.formId as string)
const sigId = computed(() => route.params.sigId as string)

const title = ref('')
const description = ref('')
const bannerUrl = ref('')
const deadline = ref('')
const maxRespondents = ref<number | null>(null)
const questions = ref<Question[]>([])
const isSchemaLocked = ref(false)
const allowNonMembers = ref(false)
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const error = ref('')
const showPreview = ref(false)

const hasInvalidRating = computed(() =>
  questions.value.some((q) => q.type === 'rating' && (q.min ?? 1) >= (q.max ?? 5)),
)

const minDeadline = computed(() => {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 16)
})

function createQuestion(): Question {
  return {
    id: crypto.randomUUID(),
    type: 'text',
    label: '',
    required: true,
    placeholder: '',
    max_length: undefined,
    options: [],
    min: 1,
    max: 5,
    labels: undefined,
    allowed_types: [],
    max_size_mb: undefined,
  }
}

function addQuestion() {
  questions.value.push(createQuestion())
}
function removeQuestion(index: number) {
  questions.value.splice(index, 1)
}
function moveQuestion(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= questions.value.length) return
  const temp = questions.value[index]
  questions.value[index] = questions.value[target]
  questions.value[target] = temp
}
function addOption(question: Question) {
  if (!question.options) question.options = []
  question.options.push({ id: crypto.randomUUID(), label: '' })
}
function removeOption(question: Question, optIndex: number) {
  question.options?.splice(optIndex, 1)
}
function updateAllowedTypes(question: Question, event: Event) {
  question.allowed_types = (event.target as HTMLInputElement).value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

async function uploadBanner(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const data = await uploadEditorFile(file)
    bannerUrl.value = data.url
  } catch {
    error.value = t('forms.builder.uploadBannerError')
  }
}

async function fetchForm() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const data = await getForm(formId.value)
    title.value = data.title
    description.value = data.description || ''
    bannerUrl.value = data.banner_url || ''
    deadline.value = data.deadline ? data.deadline.slice(0, 16) : ''
    maxRespondents.value = data.max_respondents
    isSchemaLocked.value = data.is_schema_locked
    allowNonMembers.value = data.allow_non_members ?? false
    questions.value = data.questions.map((q: Question) => ({
      id: q.id,
      type: q.type,
      label: q.label || '',
      required: q.required ?? true,
      placeholder: q.placeholder || '',
      max_length: q.max_length ?? undefined,
      options: q.options || [],
      min: q.min ?? 1,
      max: q.max ?? 5,
      labels: q.labels ?? undefined,
      allowed_types: q.allowed_types || [],
      max_size_mb: q.max_size_mb ?? undefined,
    }))
  } catch {
    error.value = t('forms.builder.loadError')
  } finally {
    loading.value = false
  }
}

function serializeQuestion(q: Question) {
  const base: Record<string, unknown> = {
    id: q.id,
    type: q.type,
    label: q.label.trim(),
    required: q.required,
  }
  if (q.type === 'text' || q.type === 'textarea') {
    if (q.placeholder) base.placeholder = q.placeholder
    if (q.max_length) base.max_length = q.max_length
  }
  if (['single_choice', 'multiple_choice', 'dropdown'].includes(q.type)) {
    base.options = (q.options ?? [])
      .filter((o) => o.label.trim())
      .map((o) => ({ id: o.id, label: o.label.trim() }))
  }
  if (q.type === 'rating') {
    base.min = q.min ?? 1
    base.max = q.max ?? 5
  }
  if (q.type === 'file_upload') {
    if ((q.allowed_types?.length ?? 0) > 0) base.allowed_types = q.allowed_types
    if (q.max_size_mb) base.max_size_mb = q.max_size_mb
  }
  return base
}

async function saveForm() {
  error.value = ''
  message.value = ''
  if (!title.value.trim()) {
    error.value = t('forms.builder.validation.titleRequired')
    return
  }
  if (deadline.value && new Date(deadline.value) <= new Date()) {
    error.value = 'Deadline must be in the future.'
    return
  }
  if (questions.value.length === 0) {
    error.value = t('forms.builder.validation.questionRequired')
    return
  }
  for (const q of questions.value) {
    if (!q.label.trim()) {
      error.value = t('forms.builder.validation.labelRequired')
      return
    }
    if (
      ['single_choice', 'multiple_choice', 'dropdown'].includes(q.type) &&
      (q.options?.length ?? 0) < 2
    ) {
      error.value = t('forms.builder.validation.optionsRequired', { label: q.label })
      return
    }
    if (q.type === 'rating' && (q.min ?? 1) >= (q.max ?? 5)) {
      error.value = t('forms.builder.validation.ratingError', { label: q.label })
      return
    }
  }
  saving.value = true
  try {
    const payload: {
      title: string
      description: string | null
      banner_url: string | null
      deadline: string | null
      max_respondents: number | null
      allow_non_members: boolean
      questions?: unknown[]
    } = {
      title: title.value.trim(),
      description: description.value.trim() || null,
      banner_url: bannerUrl.value.trim() || null,
      deadline: deadline.value ? new Date(deadline.value).toISOString() : null,
      max_respondents: maxRespondents.value || null,
      allow_non_members: allowNonMembers.value,
    }
    if (isEdit.value) {
      if (!isSchemaLocked.value) payload.questions = questions.value.map(serializeQuestion)
      await updateForm(formId.value, payload)
      message.value = t('forms.builder.updateSuccess')
    } else {
      const serialized = questions.value.map(serializeQuestion)
      const data = await createForm(sigId.value, { ...payload, questions: serialized })
      message.value = t('forms.builder.successMessage')
      router.replace(`/forms/${data.id}`)
    }
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('forms.builder.saveError'))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (isEdit.value) fetchForm()
  else addQuestion()
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="mb-6">
      <button @click="router.back()" class="text-sm text-brand-600 hover:underline">
        &larr; {{ t('forms.builder.backBtn') }}
      </button>
    </div>

    <h1 class="text-2xl font-bold text-foreground mb-6">
      {{ isEdit ? t('forms.builder.editTitle') : t('forms.builder.createTitle') }}
    </h1>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <template v-else>
      <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>
      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <BaseCard padding="lg" class="mb-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.bannerLabel')
          }}</label>
          <div v-if="bannerUrl" class="mb-2">
            <img
              :src="bannerUrl"
              alt="Banner"
              loading="lazy"
              class="w-full h-40 object-cover rounded-lg"
              width="768"
              height="160"
            />
          </div>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="uploadBanner"
            class="text-sm text-muted"
          />
        </div>
        <BaseInput
          v-model="title"
          :label="t('forms.builder.titleLabel')"
          :placeholder="t('forms.builder.titlePlaceholder')"
        />
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.descLabel')
          }}</label>
          <TiptapEditor v-model="description" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.deadlineLabel')
            }}</label>
            <input
              v-model="deadline"
              type="datetime-local"
              :min="minDeadline"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.maxRespondentsLabel')
            }}</label>
            <input
              v-model.number="maxRespondents"
              type="number"
              min="1"
              :placeholder="t('forms.builder.maxRespondentsPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm text-foreground mt-4">
          <input type="checkbox" v-model="allowNonMembers" class="rounded" />
          {{ t('forms.builder.allowNonMembers') }}
        </label>
        <p class="text-xs text-muted mt-1">
          {{ t('forms.builder.allowNonMembersHint') }}
        </p>
      </BaseCard>

      <div class="mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold text-foreground">
            {{ t('forms.builder.questionsTitle') }}
          </h2>
          <BaseButton v-if="!isSchemaLocked" size="sm" @click="addQuestion">{{
            t('forms.builder.addQuestionBtn')
          }}</BaseButton>
        </div>

        <BaseAlert v-if="isSchemaLocked" type="warning" class="mb-4">{{
          t('forms.builder.schemaLockedWarning')
        }}</BaseAlert>

        <div class="space-y-4">
          <div
            v-for="(q, i) in questions"
            :key="q.id"
            class="bg-surface rounded-lg shadow p-5 border-l-4"
            :class="isSchemaLocked ? 'border-gray-300 opacity-75' : 'border-brand-500'"
          >
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-medium text-muted"
                >{{ t('forms.builder.questionLabel') }} {{ i + 1 }}</span
              >
              <div v-if="!isSchemaLocked" class="flex items-center gap-1">
                <button
                  @click="moveQuestion(i, -1)"
                  :disabled="i === 0"
                  class="text-muted hover:text-foreground disabled:opacity-30 px-1"
                >
                  &uarr;
                </button>
                <button
                  @click="moveQuestion(i, 1)"
                  :disabled="i === questions.length - 1"
                  class="text-muted hover:text-foreground disabled:opacity-30 px-1"
                >
                  &darr;
                </button>
                <button
                  @click="removeQuestion(i)"
                  class="text-danger-500 hover:text-danger-600 px-1 ml-2"
                >
                  &times;
                </button>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
              <div>
                <label class="block text-xs text-muted mb-1">{{
                  t('forms.builder.typeLabel')
                }}</label>
                <select
                  v-model="q.type"
                  :disabled="isSchemaLocked"
                  class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option v-for="qt in QUESTION_TYPES" :key="qt.value" :value="qt.value">
                    {{ t(qt.key) }}
                  </option>
                </select>
              </div>
              <div class="sm:col-span-2">
                <label class="block text-xs text-muted mb-1">{{
                  t('forms.builder.labelRequired')
                }}</label>
                <input
                  v-model="q.label"
                  :disabled="isSchemaLocked"
                  type="text"
                  :placeholder="t('forms.builder.labelPlaceholder')"
                  class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            <label class="flex items-center gap-2 text-sm text-foreground mb-3">
              <input
                type="checkbox"
                v-model="q.required"
                :disabled="isSchemaLocked"
                class="rounded"
              />
              {{ t('forms.builder.requiredCheckbox') }}
            </label>

            <div v-if="q.type === 'text' || q.type === 'textarea'" class="space-y-2">
              <input
                v-model="q.placeholder"
                :disabled="isSchemaLocked"
                type="text"
                :placeholder="t('forms.builder.placeholderLabel')"
                class="w-full border border-border rounded-lg px-2 py-1.5 text-sm"
              />
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">{{ t('forms.builder.maxLengthLabel') }}</label>
                <input
                  v-model.number="q.max_length"
                  :disabled="isSchemaLocked"
                  type="number"
                  min="1"
                  :placeholder="t('forms.builder.maxLengthPlaceholder')"
                  class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
            </div>

            <div
              v-if="['single_choice', 'multiple_choice', 'dropdown'].includes(q.type)"
              class="space-y-2"
            >
              <div v-for="(opt, oi) in q.options" :key="opt.id" class="flex items-center gap-2">
                <input
                  v-model="opt.label"
                  :disabled="isSchemaLocked"
                  type="text"
                  :placeholder="`Option ${oi + 1}`"
                  class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
                <button
                  v-if="!isSchemaLocked"
                  @click="removeOption(q, oi)"
                  class="text-danger-500 hover:text-danger-600 text-sm"
                >
                  &times;
                </button>
              </div>
              <button
                v-if="!isSchemaLocked"
                @click="addOption(q)"
                class="text-sm text-brand-600 hover:underline"
              >
                {{ t('forms.builder.addOptionBtn') }}
              </button>
            </div>

            <div v-if="q.type === 'rating'">
              <div class="flex items-center gap-4">
                <div class="flex items-center gap-2">
                  <label class="text-xs text-muted">{{ t('forms.builder.minLabel') }}</label
                  ><input
                    v-model.number="q.min"
                    :disabled="isSchemaLocked"
                    type="number"
                    class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                  />
                </div>
                <div class="flex items-center gap-2">
                  <label class="text-xs text-muted">{{ t('forms.builder.maxLabel') }}</label
                  ><input
                    v-model.number="q.max"
                    :disabled="isSchemaLocked"
                    type="number"
                    class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                  />
                </div>
              </div>
              <p v-if="(q.min ?? 1) >= (q.max ?? 5)" class="text-sm text-danger-600 mt-1">
                {{ t('forms.builder.minMaxError') }}
              </p>
            </div>

            <div v-if="q.type === 'file_upload'" class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">{{ t('forms.builder.allowedTypesLabel') }}</label>
                <input
                  :value="(q.allowed_types ?? []).join(', ')"
                  @input="updateAllowedTypes(q, $event)"
                  :disabled="isSchemaLocked"
                  type="text"
                  :placeholder="t('forms.builder.allowedTypesPlaceholder')"
                  class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">{{ t('forms.builder.maxSizeLabel') }}</label>
                <input
                  v-model.number="q.max_size_mb"
                  :disabled="isSchemaLocked"
                  type="number"
                  min="1"
                  :placeholder="t('forms.builder.maxSizePlaceholder')"
                  class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" size="lg" @click="showPreview = true">{{
          t('forms.builder.previewBtn')
        }}</BaseButton>
        <BaseButton size="lg" :loading="saving" :disabled="hasInvalidRating" @click="saveForm">{{
          isEdit ? t('forms.builder.updateBtn') : t('forms.builder.createBtn')
        }}</BaseButton>
      </div>
    </template>

    <!-- Preview modal -->
    <BaseModal v-model="showPreview" :title="title || t('forms.builder.createTitle')" size="xl">
      <div class="space-y-4">
        <BaseAlert type="info" class="text-center">
          {{ t('forms.builder.previewMode') }}
        </BaseAlert>
        <div v-if="bannerUrl" class="rounded-lg overflow-hidden">
          <img
            :src="bannerUrl"
            alt="Banner"
            loading="lazy"
            class="w-full h-32 object-cover"
            width="768"
            height="128"
          />
        </div>
        <div
          v-if="description"
          class="prose prose-sm max-w-none text-muted"
          v-html="description"
        ></div>

        <div
          v-for="(q, i) in questions"
          :key="q.id"
          class="bg-surface-alt rounded-lg p-4 border border-border"
        >
          <p class="text-sm font-medium text-foreground mb-2">
            {{ i + 1 }}. {{ q.label || t('forms.builder.untitledQuestion') }}
            <span v-if="q.required" class="text-danger-500">*</span>
          </p>

          <!-- Text -->
          <input
            v-if="q.type === 'text'"
            type="text"
            disabled
            :placeholder="q.placeholder || t('forms.builder.shortTextPlaceholder')"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
          />

          <!-- Textarea -->
          <textarea
            v-else-if="q.type === 'textarea'"
            disabled
            :placeholder="q.placeholder || t('forms.builder.longTextPlaceholder')"
            :rows="3"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
          />

          <!-- Single choice -->
          <div v-else-if="q.type === 'single_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input type="radio" disabled class="text-brand-600" />
              {{ opt.label || 'Option' }}
            </label>
          </div>

          <!-- Multiple choice -->
          <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input type="checkbox" disabled class="rounded" />
              {{ opt.label || 'Option' }}
            </label>
          </div>

          <!-- Dropdown -->
          <select
            v-else-if="q.type === 'dropdown'"
            disabled
            class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
          >
            <option value="">{{ t('forms.builder.selectPlaceholder') }}</option>
            <option v-for="opt in q.options" :key="opt.id">{{ opt.label }}</option>
          </select>

          <!-- Rating -->
          <div v-else-if="q.type === 'rating'" class="flex gap-2">
            <button
              v-for="n in (q.max ?? 5) - (q.min ?? 1) + 1"
              :key="n"
              disabled
              class="w-8 h-8 rounded bg-surface border border-border text-sm text-muted"
            >
              {{ (q.min ?? 1) + n - 1 }}
            </button>
          </div>

          <!-- File upload -->
          <div v-else-if="q.type === 'file_upload'" class="text-sm text-muted opacity-60">
            <input type="file" disabled />
          </div>
        </div>

        <EmptyState v-if="questions.length === 0" :message="t('forms.builder.noQuestionsAdded')" />
      </div>
    </BaseModal>
  </div>
</template>
