<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/composables/api'

interface QuestionOption {
  id: string
  label: string
}

interface Question {
  id: string
  type: string
  label: string
  required: boolean
  placeholder: string
  max_length: number | null
  options: QuestionOption[]
  min: number | null
  max: number | null
  labels: Record<string, string> | null
  allowed_types: string[]
  max_size_mb: number | null
}

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
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const error = ref('')

function createQuestion(): Question {
  return {
    id: crypto.randomUUID(),
    type: 'text',
    label: '',
    required: true,
    placeholder: '',
    max_length: null,
    options: [],
    min: 1,
    max: 5,
    labels: null,
    allowed_types: [],
    max_size_mb: null,
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
  question.options.push({ id: crypto.randomUUID(), label: '' })
}

function removeOption(question: Question, optIndex: number) {
  question.options.splice(optIndex, 1)
}

async function uploadBanner(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post('/files/upload/editor', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    bannerUrl.value = data.url
  } catch {
    error.value = 'Failed to upload banner image.'
  }
}

async function fetchForm() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/forms/${formId.value}`)
    title.value = data.title
    description.value = data.description || ''
    bannerUrl.value = data.banner_url || ''
    deadline.value = data.deadline ? data.deadline.slice(0, 16) : ''
    maxRespondents.value = data.max_respondents
    isSchemaLocked.value = data.is_schema_locked
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
    if (['single_choice', 'multiple_choice', 'dropdown'].includes(q.type) && q.options.length < 2) {
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
    }

    if (isEdit.value) {
      if (!isSchemaLocked.value) {
        payload.questions = questions.value.map(serializeQuestion)
      }
      await api.put(`/forms/${formId.value}`, payload)
      message.value = 'Form updated successfully.'
    } else {
      payload.questions = questions.value.map(serializeQuestion)
      const { data } = await api.post(`/sigs/${sigId.value}/forms`, payload)
      message.value = 'Form created successfully.'
      router.replace(`/forms/${data.id}`)
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to save form.'
  } finally {
    saving.value = false
  }
}

function serializeQuestion(q: Question) {
  const base: any = {
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
    base.options = q.options.filter(o => o.label.trim()).map(o => ({
      id: o.id,
      label: o.label.trim(),
    }))
  }
  if (q.type === 'rating') {
    base.min = q.min ?? 1
    base.max = q.max ?? 5
  }
  if (q.type === 'file_upload') {
    if (q.allowed_types.length > 0) base.allowed_types = q.allowed_types
    if (q.max_size_mb) base.max_size_mb = q.max_size_mb
  }
  return base
}

onMounted(() => {
  if (isEdit.value) {
    fetchForm()
  } else {
    addQuestion()
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-8 px-4">
    <div class="mb-6">
      <button @click="router.back()" class="text-sm text-blue-600 hover:underline">&larr; Back</button>
    </div>

    <h1 class="text-2xl font-bold text-gray-900 mb-6">
      {{ isEdit ? 'Edit Form' : 'Create Form' }}
    </h1>

    <div v-if="loading" class="text-center text-gray-400 py-12">Loading...</div>

    <template v-else>
      <div v-if="message" class="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 mb-4 text-sm">
        {{ message }}
      </div>
      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
        {{ error }}
      </div>

      <!-- Form Header -->
      <div class="bg-white rounded-xl shadow p-6 mb-6 space-y-4">
        <!-- Banner -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Banner Image</label>
          <div v-if="bannerUrl" class="mb-2">
            <img :src="bannerUrl" alt="Banner" class="w-full h-40 object-cover rounded-lg" />
          </div>
          <input type="file" accept="image/png,image/jpeg,image/webp" @change="uploadBanner"
            class="text-sm text-gray-500" />
        </div>

        <!-- Title -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Title *</label>
          <input v-model="title" type="text" maxlength="300" placeholder="Form title"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <!-- Description -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea v-model="description" rows="3" placeholder="Optional description"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
        </div>

        <!-- Deadline + Max Respondents -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Deadline</label>
            <input v-model="deadline" type="datetime-local"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Max Respondents</label>
            <input v-model.number="maxRespondents" type="number" min="1" placeholder="Unlimited"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
      </div>

      <!-- Questions -->
      <div class="mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-semibold text-gray-900">Questions</h2>
          <button v-if="!isSchemaLocked" @click="addQuestion"
            class="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition">
            + Add Question
          </button>
        </div>

        <div v-if="isSchemaLocked"
          class="bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-lg p-3 mb-4 text-sm">
          Questions are locked because responses have been submitted. You can still edit title, description, and
          deadline.
        </div>

        <div class="space-y-4">
          <div v-for="(q, i) in questions" :key="q.id"
            class="bg-white rounded-xl shadow p-5 border-l-4"
            :class="isSchemaLocked ? 'border-gray-300 opacity-75' : 'border-blue-500'">

            <!-- Question header -->
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-medium text-gray-500">Question {{ i + 1 }}</span>
              <div v-if="!isSchemaLocked" class="flex items-center gap-1">
                <button @click="moveQuestion(i, -1)" :disabled="i === 0"
                  class="text-gray-400 hover:text-gray-600 disabled:opacity-30 px-1" title="Move up">
                  &uarr;
                </button>
                <button @click="moveQuestion(i, 1)" :disabled="i === questions.length - 1"
                  class="text-gray-400 hover:text-gray-600 disabled:opacity-30 px-1" title="Move down">
                  &darr;
                </button>
                <button @click="removeQuestion(i)"
                  class="text-red-400 hover:text-red-600 px-1 ml-2" title="Remove">
                  &times;
                </button>
              </div>
            </div>

            <!-- Type + Label -->
            <div class="grid grid-cols-3 gap-3 mb-3">
              <div>
                <label class="block text-xs text-gray-500 mb-1">Type</label>
                <select v-model="q.type" :disabled="isSchemaLocked"
                  class="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option v-for="t in QUESTION_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div class="col-span-2">
                <label class="block text-xs text-gray-500 mb-1">Label *</label>
                <input v-model="q.label" :disabled="isSchemaLocked" type="text" placeholder="Question text"
                  class="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>

            <!-- Required toggle -->
            <label class="flex items-center gap-2 text-sm text-gray-600 mb-3">
              <input type="checkbox" v-model="q.required" :disabled="isSchemaLocked" class="rounded" />
              Required
            </label>

            <!-- Type-specific fields -->
            <!-- Text / Textarea -->
            <div v-if="q.type === 'text' || q.type === 'textarea'" class="space-y-2">
              <input v-model="q.placeholder" :disabled="isSchemaLocked" type="text" placeholder="Placeholder text"
                class="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Max length:</label>
                <input v-model.number="q.max_length" :disabled="isSchemaLocked" type="number" min="1"
                  placeholder="No limit"
                  class="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              </div>
            </div>

            <!-- Choice types -->
            <div v-if="['single_choice', 'multiple_choice', 'dropdown'].includes(q.type)" class="space-y-2">
              <div v-for="(opt, oi) in q.options" :key="opt.id" class="flex items-center gap-2">
                <input v-model="opt.label" :disabled="isSchemaLocked" type="text"
                  :placeholder="`Option ${oi + 1}`"
                  class="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
                <button v-if="!isSchemaLocked" @click="removeOption(q, oi)"
                  class="text-red-400 hover:text-red-600 text-sm">&times;</button>
              </div>
              <button v-if="!isSchemaLocked" @click="addOption(q)"
                class="text-sm text-blue-600 hover:underline">+ Add option</button>
            </div>

            <!-- Rating -->
            <div v-if="q.type === 'rating'" class="flex items-center gap-4">
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Min:</label>
                <input v-model.number="q.min" :disabled="isSchemaLocked" type="number"
                  class="w-16 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Max:</label>
                <input v-model.number="q.max" :disabled="isSchemaLocked" type="number"
                  class="w-16 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              </div>
            </div>

            <!-- File upload -->
            <div v-if="q.type === 'file_upload'" class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Allowed types (comma separated):</label>
                <input :value="q.allowed_types.join(', ')"
                  @input="q.allowed_types = ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean)"
                  :disabled="isSchemaLocked" type="text" placeholder="pdf, docx, png"
                  class="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Max size (MB):</label>
                <input v-model.number="q.max_size_mb" :disabled="isSchemaLocked" type="number" min="1"
                  placeholder="No limit"
                  class="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Save button -->
      <div class="flex justify-end">
        <button @click="saveForm" :disabled="saving"
          class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
          {{ saving ? 'Saving...' : (isEdit ? 'Update Form' : 'Create Form') }}
        </button>
      </div>
    </template>
  </div>
</template>
