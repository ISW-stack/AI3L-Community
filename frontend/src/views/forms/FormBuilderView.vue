<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Question } from '@/types'
import { getForm, createForm, updateForm } from '@/api/forms'
import { uploadEditorFile } from '@/api/files'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const QUESTION_TYPES = [
  { value: 'text', label: 'Short Text' },
  { value: 'textarea', label: 'Long Text' },
  { value: 'single_choice', label: 'Single Choice' },
  { value: 'multiple_choice', label: 'Multiple Choice' },
  { value: 'dropdown', label: 'Dropdown' },
  { value: 'rating', label: 'Rating' },
  { value: 'file_upload', label: 'File Upload' },
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

async function uploadBanner(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const data = await uploadEditorFile(file)
    bannerUrl.value = data.url
  } catch {
    error.value = 'Failed to upload banner image.'
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
    questions.value = data.questions.map((q: any) => ({
      id: q.id,
      type: q.type,
      label: q.label || '',
      required: q.required ?? true,
      placeholder: q.placeholder || '',
      max_length: q.max_length ?? null,
      options: q.options || [],
      min: q.min ?? 1,
      max: q.max ?? 5,
      labels: q.labels ?? null,
      allowed_types: q.allowed_types || [],
      max_size_mb: q.max_size_mb ?? null,
    }))
  } catch {
    error.value = 'Failed to load form.'
  } finally {
    loading.value = false
  }
}

function serializeQuestion(q: Question) {
  const base: any = { id: q.id, type: q.type, label: q.label.trim(), required: q.required }
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
    error.value = 'Title is required.'
    return
  }
  if (questions.value.length === 0) {
    error.value = 'At least one question is required.'
    return
  }
  for (const q of questions.value) {
    if (!q.label.trim()) {
      error.value = 'All questions must have a label.'
      return
    }
    if (
      ['single_choice', 'multiple_choice', 'dropdown'].includes(q.type) &&
      (q.options?.length ?? 0) < 2
    ) {
      error.value = `Question "${q.label}" needs at least 2 options.`
      return
    }
  }
  saving.value = true
  try {
    const payload: any = {
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
      message.value = 'Form updated successfully.'
    } else {
      payload.questions = questions.value.map(serializeQuestion)
      const data = await createForm(sigId.value, payload)
      message.value = 'Form created successfully.'
      router.replace(`/forms/${data.id}`)
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to save form.'
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
        &larr; Back
      </button>
    </div>

    <h1 class="text-2xl font-bold text-foreground mb-6">
      {{ isEdit ? 'Edit Form' : 'Create Form' }}
    </h1>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <template v-else>
      <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>
      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <BaseCard padding="lg" class="mb-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">Banner Image</label>
          <div v-if="bannerUrl" class="mb-2">
            <img :src="bannerUrl" alt="Banner" class="w-full h-40 object-cover rounded-lg" />
          </div>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="uploadBanner"
            class="text-sm text-muted"
          />
        </div>
        <BaseInput v-model="title" label="Title *" placeholder="Form title" />
        <BaseTextarea
          v-model="description"
          label="Description"
          placeholder="Optional description"
          :rows="3"
        />
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">Deadline</label>
            <input
              v-model="deadline"
              type="datetime-local"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">Max Respondents</label>
            <input
              v-model.number="maxRespondents"
              type="number"
              min="1"
              placeholder="Unlimited"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm text-foreground mt-4">
          <input type="checkbox" v-model="allowNonMembers" class="rounded" />
          Allow non-SIG members to submit this form
        </label>
        <p class="text-xs text-muted mt-1">
          When enabled, any authenticated user can fill out this form.
        </p>
      </BaseCard>

      <div class="mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold text-foreground">Questions</h2>
          <BaseButton v-if="!isSchemaLocked" size="sm" @click="addQuestion"
            >+ Add Question</BaseButton
          >
        </div>

        <BaseAlert v-if="isSchemaLocked" type="warning" class="mb-4"
          >Questions are locked because responses have been submitted. You can still edit title,
          description, and deadline.</BaseAlert
        >

        <div class="space-y-4">
          <div
            v-for="(q, i) in questions"
            :key="q.id"
            class="bg-surface rounded-lg shadow p-5 border-l-4"
            :class="isSchemaLocked ? 'border-gray-300 opacity-75' : 'border-brand-500'"
          >
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-medium text-muted">Question {{ i + 1 }}</span>
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
                <label class="block text-xs text-muted mb-1">Type</label>
                <select
                  v-model="q.type"
                  :disabled="isSchemaLocked"
                  class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option v-for="t in QUESTION_TYPES" :key="t.value" :value="t.value">
                    {{ t.label }}
                  </option>
                </select>
              </div>
              <div class="sm:col-span-2">
                <label class="block text-xs text-muted mb-1">Label *</label>
                <input
                  v-model="q.label"
                  :disabled="isSchemaLocked"
                  type="text"
                  placeholder="Question text"
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
              Required
            </label>

            <div v-if="q.type === 'text' || q.type === 'textarea'" class="space-y-2">
              <input
                v-model="q.placeholder"
                :disabled="isSchemaLocked"
                type="text"
                placeholder="Placeholder text"
                class="w-full border border-border rounded-lg px-2 py-1.5 text-sm"
              />
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">Max length:</label>
                <input
                  v-model.number="q.max_length"
                  :disabled="isSchemaLocked"
                  type="number"
                  min="1"
                  placeholder="No limit"
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
                + Add option
              </button>
            </div>

            <div v-if="q.type === 'rating'" class="flex items-center gap-4">
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">Min:</label
                ><input
                  v-model.number="q.min"
                  :disabled="isSchemaLocked"
                  type="number"
                  class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">Max:</label
                ><input
                  v-model.number="q.max"
                  :disabled="isSchemaLocked"
                  type="number"
                  class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
            </div>

            <div v-if="q.type === 'file_upload'" class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">Allowed types:</label>
                <input
                  :value="(q.allowed_types ?? []).join(', ')"
                  @input="
                    q.allowed_types = ($event.target as HTMLInputElement).value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  "
                  :disabled="isSchemaLocked"
                  type="text"
                  placeholder="pdf, docx, png"
                  class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-muted">Max size (MB):</label>
                <input
                  v-model.number="q.max_size_mb"
                  :disabled="isSchemaLocked"
                  type="number"
                  min="1"
                  placeholder="No limit"
                  class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" size="lg" @click="showPreview = true">Preview</BaseButton>
        <BaseButton size="lg" :loading="saving" @click="saveForm">{{
          isEdit ? 'Update Form' : 'Create Form'
        }}</BaseButton>
      </div>
    </template>

    <!-- Preview modal -->
    <BaseModal v-model="showPreview" :title="title || 'Untitled Form'" size="xl">
      <div class="space-y-4">
        <div v-if="bannerUrl" class="rounded-lg overflow-hidden">
          <img :src="bannerUrl" alt="Banner" class="w-full h-32 object-cover" />
        </div>
        <p v-if="description" class="text-sm text-muted">{{ description }}</p>

        <div
          v-for="(q, i) in questions"
          :key="q.id"
          class="bg-surface-alt rounded-lg p-4 border border-border"
        >
          <p class="text-sm font-medium text-foreground mb-2">
            {{ i + 1 }}. {{ q.label || 'Untitled question' }}
            <span v-if="q.required" class="text-danger-500">*</span>
          </p>

          <!-- Text -->
          <input
            v-if="q.type === 'text'"
            type="text"
            disabled
            :placeholder="q.placeholder || 'Short text answer'"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
          />

          <!-- Textarea -->
          <textarea
            v-else-if="q.type === 'textarea'"
            disabled
            :placeholder="q.placeholder || 'Long text answer'"
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
            <option value="">Select...</option>
            <option v-for="opt in q.options" :key="opt.id">{{ opt.label }}</option>
          </select>

          <!-- Rating -->
          <div v-else-if="q.type === 'rating'" class="flex gap-2">
            <button
              v-for="n in ((q.max ?? 5) - (q.min ?? 1) + 1)"
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

        <div v-if="questions.length === 0" class="text-sm text-muted text-center py-4">
          No questions added yet.
        </div>
      </div>
    </BaseModal>
  </div>
</template>
