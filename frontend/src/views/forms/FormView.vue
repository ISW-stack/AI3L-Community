<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/composables/api'
import { useAuthStore } from '@/stores/auth'

interface QuestionOption {
  id: string
  label: string
}

interface Question {
  id: string
  type: string
  label: string
  required: boolean
  placeholder?: string
  max_length?: number
  options?: QuestionOption[]
  min?: number
  max?: number
  labels?: Record<string, string>
  allowed_types?: string[]
  max_size_mb?: number
}

interface FormData {
  id: string
  sig_id: string
  title: string
  description: string | null
  banner_url: string | null
  deadline: string | null
  max_respondents: number | null
  questions: Question[]
  is_schema_locked: boolean
  response_count: number
  is_active: boolean
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
  user_is_sig_admin: boolean
}

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

// CSV export state
const exporting = ref(false)
const exportStatus = ref('')
let exportPollTimer: ReturnType<typeof setInterval> | null = null

const canEdit = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin || auth.user?.id === form.value.created_by
})

const canExport = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin
})

async function fetchForm() {
  loading.value = true
  try {
    const { data } = await api.get(`/forms/${formId.value}`)
    form.value = data
    // Initialize answers
    for (const q of data.questions) {
      if (q.type === 'multiple_choice') {
        answers.value[q.id] = []
      } else {
        answers.value[q.id] = q.type === 'rating' ? null : ''
      }
    }
  } catch {
    error.value = 'Failed to load form.'
  } finally {
    loading.value = false
  }
}

function validateAnswers(): string | null {
  if (!form.value) return 'Form not loaded.'
  for (const q of form.value.questions) {
    const val = answers.value[q.id]
    if (q.required) {
      if (val === null || val === undefined || val === '') return `"${q.label}" is required.`
      if (Array.isArray(val) && val.length === 0) return `"${q.label}" is required.`
    }
    if (val === null || val === undefined || val === '' || (Array.isArray(val) && val.length === 0)) continue
    if ((q.type === 'text' || q.type === 'textarea') && q.max_length && typeof val === 'string' && val.length > q.max_length) {
      return `"${q.label}" exceeds maximum length of ${q.max_length}.`
    }
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
    // Clean answers: remove empty strings and null for non-required
    const cleanAnswers: Record<string, any> = {}
    for (const [key, val] of Object.entries(answers.value)) {
      if (val !== null && val !== undefined && val !== '' && !(Array.isArray(val) && val.length === 0)) {
        cleanAnswers[key] = val
      }
    }
    await api.post(`/forms/${formId.value}/submit`, { answers: cleanAnswers })
    submitted.value = true
    message.value = 'Your response has been submitted successfully!'
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to submit response.'
  } finally {
    submitting.value = false
  }
}

async function handleFileUpload(questionId: string, event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post('/files/upload/editor', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    answers.value[questionId] = { key: data.key || data.url, filename: file.name }
  } catch {
    error.value = 'Failed to upload file.'
  }
}

function toggleMultipleChoice(questionId: string, optionId: string) {
  const arr = answers.value[questionId] as string[]
  const idx = arr.indexOf(optionId)
  if (idx === -1) {
    arr.push(optionId)
  } else {
    arr.splice(idx, 1)
  }
}

function ratingRange(q: Question): number[] {
  const min = q.min ?? 1
  const max = q.max ?? 5
  const range: number[] = []
  for (let i = min; i <= max; i++) range.push(i)
  return range
}

// CSV export
async function startExport() {
  exporting.value = true
  exportStatus.value = 'Starting export...'
  try {
    const { data } = await api.post(`/forms/${formId.value}/export`)
    const taskId = data.task_id
    pollExportStatus(taskId)
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to start export.'
    exporting.value = false
    exportStatus.value = ''
  }
}

function pollExportStatus(taskId: string) {
  let attempts = 0
  exportPollTimer = setInterval(async () => {
    attempts++
    if (attempts > 30) {
      clearInterval(exportPollTimer!)
      exportPollTimer = null
      exporting.value = false
      exportStatus.value = ''
      error.value = 'Export timed out. Please try again.'
      return
    }
    try {
      const { data } = await api.get(`/tasks/${taskId}/status`)
      exportStatus.value = `Status: ${data.status}`
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
        error.value = 'Export failed. Please try again.'
      }
    } catch {
      // Continue polling
    }
  }, 2000)
}

onMounted(() => fetchForm())

onUnmounted(() => {
  if (exportPollTimer) {
    clearInterval(exportPollTimer)
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-8 px-4">
    <div class="mb-6">
      <button @click="router.back()" class="text-sm text-blue-600 hover:underline">&larr; Back</button>
    </div>

    <div v-if="loading" class="text-center text-gray-400 py-12">Loading...</div>

    <div v-else-if="!form" class="text-center py-12">
      <p class="text-gray-500 mb-4">Form not found.</p>
    </div>

    <template v-else>
      <!-- Banner -->
      <div v-if="form.banner_url" class="mb-6">
        <img :src="form.banner_url" alt="Form banner" class="w-full h-48 object-cover rounded-xl" />
      </div>

      <!-- Header -->
      <div class="bg-white rounded-xl shadow p-6 mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ form.title }}</h1>
            <p v-if="form.description" class="text-sm text-gray-600 mb-3">{{ form.description }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="form.is_active"
              class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
            <span v-else
              class="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">Closed</span>
          </div>
        </div>
        <div class="flex items-center gap-4 text-xs text-gray-400 mt-2">
          <span>By {{ form.created_by_name }}</span>
          <span>{{ form.response_count }} response(s)</span>
          <span v-if="form.deadline">Deadline: {{ new Date(form.deadline).toLocaleString() }}</span>
          <span v-if="form.max_respondents">Max: {{ form.max_respondents }}</span>
        </div>

        <!-- Admin actions -->
        <div v-if="auth.isAuthenticated" class="flex items-center gap-2 mt-4">
          <router-link v-if="canEdit" :to="`/forms/${form.id}/edit`"
            class="text-sm text-blue-600 hover:underline">Edit form</router-link>
          <button v-if="canExport" @click="startExport" :disabled="exporting"
            class="text-sm bg-gray-100 text-gray-700 px-3 py-1 rounded-lg hover:bg-gray-200 transition disabled:opacity-50">
            {{ exporting ? 'Exporting...' : 'Export CSV' }}
          </button>
          <span v-if="exportStatus" class="text-xs text-gray-500">{{ exportStatus }}</span>
        </div>
      </div>

      <!-- Closed banner -->
      <div v-if="!form.is_active"
        class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-6 text-sm text-center">
        This form is closed and no longer accepting responses.
      </div>

      <!-- Success message -->
      <div v-if="submitted"
        class="bg-green-50 border border-green-200 text-green-700 rounded-lg p-4 mb-6 text-sm text-center">
        {{ message }}
      </div>

      <!-- Error message -->
      <div v-if="error"
        class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
        {{ error }}
      </div>

      <!-- Questions -->
      <div v-if="!submitted && form.is_active && auth.isAuthenticated && !auth.isGuest" class="space-y-4">
        <div v-for="q in form.questions" :key="q.id" class="bg-white rounded-xl shadow p-5">
          <label class="block text-sm font-medium text-gray-900 mb-2">
            {{ q.label }}
            <span v-if="q.required" class="text-red-500">*</span>
          </label>

          <!-- Text -->
          <input v-if="q.type === 'text'" v-model="answers[q.id]" type="text"
            :placeholder="q.placeholder || ''" :maxlength="q.max_length || undefined"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />

          <!-- Textarea -->
          <textarea v-else-if="q.type === 'textarea'" v-model="answers[q.id]" rows="4"
            :placeholder="q.placeholder || ''" :maxlength="q.max_length || undefined"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>

          <!-- Single Choice -->
          <div v-else-if="q.type === 'single_choice'" class="space-y-2">
            <label v-for="opt in q.options" :key="opt.id" class="flex items-center gap-2 text-sm text-gray-700">
              <input type="radio" :name="q.id" :value="opt.id" v-model="answers[q.id]"
                class="text-blue-600" />
              {{ opt.label }}
            </label>
          </div>

          <!-- Multiple Choice -->
          <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
            <label v-for="opt in q.options" :key="opt.id" class="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" :value="opt.id"
                :checked="(answers[q.id] as string[]).includes(opt.id)"
                @change="toggleMultipleChoice(q.id, opt.id)"
                class="rounded text-blue-600" />
              {{ opt.label }}
            </label>
          </div>

          <!-- Dropdown -->
          <select v-else-if="q.type === 'dropdown'" v-model="answers[q.id]"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Select an option</option>
            <option v-for="opt in q.options" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>

          <!-- Rating -->
          <div v-else-if="q.type === 'rating'" class="flex items-center gap-1">
            <button v-for="n in ratingRange(q)" :key="n" @click="answers[q.id] = n" type="button"
              class="w-10 h-10 rounded-lg text-sm font-medium transition"
              :class="answers[q.id] === n ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'">
              {{ n }}
            </button>
          </div>

          <!-- File Upload -->
          <div v-else-if="q.type === 'file_upload'">
            <input type="file" @change="handleFileUpload(q.id, $event)" class="text-sm text-gray-500" />
            <p v-if="answers[q.id]?.filename" class="text-xs text-green-600 mt-1">
              Uploaded: {{ answers[q.id].filename }}
            </p>
            <p v-if="q.allowed_types && q.allowed_types.length" class="text-xs text-gray-400 mt-1">
              Allowed: {{ q.allowed_types.join(', ') }}
            </p>
          </div>

          <!-- Character count for text fields -->
          <p v-if="(q.type === 'text' || q.type === 'textarea') && q.max_length"
            class="text-xs text-gray-400 mt-1 text-right">
            {{ (answers[q.id] as string)?.length || 0 }} / {{ q.max_length }}
          </p>
        </div>

        <!-- Submit button -->
        <div class="flex justify-end pt-4">
          <button @click="submitForm" :disabled="submitting"
            class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-50">
            {{ submitting ? 'Submitting...' : 'Submit' }}
          </button>
        </div>
      </div>

      <!-- Not authenticated message -->
      <div v-if="!auth.isAuthenticated && form.is_active"
        class="bg-gray-50 border border-gray-200 text-gray-600 rounded-lg p-4 text-sm text-center">
        Please <router-link to="/login" class="text-blue-600 hover:underline">log in</router-link> to submit a response.
      </div>
    </template>
  </div>
</template>
