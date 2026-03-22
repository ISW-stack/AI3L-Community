<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { formatDateTime } from '@/utils/date'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/auth'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useFormExport } from '@/composables/useFormExport'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'
import BackToTop from '@/components/BackToTop.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formId = computed(() => route.params.formId as string)

const {
  form,
  answers,
  loading,
  submitting,
  submitted,
  error,
  message,
  sigName,
  previousResponse,
  validationErrors,
  highlightedQuestions,
  dragOverQuestions,
  filePreviews,
  uploadingFiles,
  draftRestored,
  canEdit,
  canExport,
  totalQuestions,
  answeredCount,
  progressPercent,
  showForm,
  loadForm,
  submitForm,
  handleFileUpload,
  handleDrop,
  handleDragOver,
  handleDragLeave,
  triggerFileInput,
  removeFile,
  toggleMultipleChoice,
  ratingRange,
  ratingCount,
  selectRating,
  onTextInput,
  onSelectChange,
  onRadioChange,
  getDisplayAnswer,
  getResponseAnswers,
  handleClearDraft,
  goBackToSig,
  setQuestionRef,
  isFileObject,
  getFileName,
  formatFileSize,
} = useFormSubmit({ formId, auth, router, t })

const { exportStatus, exportStatusMessage, startExport } = useFormExport({
  onError: (msg) => {
    error.value = msg
  },
})

const formShareUrl = computed(() => `${window.location.origin}/forms/${formId.value}`)

function handleStartExport() {
  startExport(formId.value, {
    starting: t('forms.view.exportStarting'),
    statusPrefix: t('forms.view.exportStatus'),
    timeout: t('forms.view.exportTimeout'),
    failed: t('forms.view.exportFailed'),
    error: t('forms.view.exportError'),
  })
}

const touched = reactive<Record<string, boolean>>({})

function handleBlur(questionId: string, required: boolean | undefined) {
  touched[questionId] = true
  // Inline validation is handled by the template condition
  // (touched && required && !answers[q.id]) — see data-testid="inline-validation-error"
  void required
}

onMounted(() => loadForm())
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      v-if="form && !form.sig_id"
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.forms'), to: '/forms' },
        { label: form?.title || '...' },
      ]"
    />
    <BaseBreadcrumb
      v-else
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        {
          label: sigName || '...',
          to: form ? `/sigs/${form.sig_id}` : '/sigs',
        },
        {
          label: t('breadcrumb.forms'),
          to: form ? `/sigs/${form.sig_id}/forms` : '/sigs',
        },
        { label: form?.title || '...' },
      ]"
    />

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

      <!-- Feature 1: Progress Indicator -->
      <div
        v-if="showForm"
        class="sticky top-0 z-30 bg-surface/95 backdrop-blur-sm border-b border-border py-2 px-4 mb-4 rounded-lg shadow-sm"
      >
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <div class="w-full h-2 bg-surface-alt rounded-full overflow-hidden">
              <div
                class="h-full bg-brand-600 rounded-full transition-all duration-500 ease-out"
                :style="{ width: `${progressPercent}%` }"
                role="progressbar"
                :aria-valuenow="answeredCount"
                :aria-valuemin="0"
                :aria-valuemax="totalQuestions"
                :aria-label="
                  t('forms.view.progressLabel', { current: answeredCount, total: totalQuestions })
                "
              ></div>
            </div>
          </div>
          <span class="hidden sm:inline text-xs text-muted whitespace-nowrap">
            {{ t('forms.view.progressText', { current: answeredCount, total: totalQuestions }) }}
          </span>
          <span class="sm:hidden text-xs text-muted whitespace-nowrap">
            {{ answeredCount }}/{{ totalQuestions }}
          </span>
        </div>
      </div>

      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-foreground mb-2">{{ form.title }}</h1>
            <div
              v-if="form.description"
              class="prose prose-sm max-w-none text-muted mb-3"
              v-html="DOMPurify.sanitize(form.description)"
            ></div>
          </div>
          <BaseBadge :variant="form.is_active ? 'success' : 'danger'">{{
            form.is_active ? t('common.active') : t('common.closed')
          }}</BaseBadge>
        </div>
        <div class="flex items-center gap-x-4 gap-y-1 flex-wrap text-xs text-muted mt-2">
          <span>{{ t('common.by') }} {{ form.created_by_name }}</span>
          <span>{{ form.response_count }} {{ t('forms.view.response') }}</span>
          <span v-if="form.deadline"
            >{{ t('forms.view.deadline') }} {{ formatDateTime(form.deadline, locale) }}</span
          >
          <span v-if="form.max_respondents"
            >{{ t('forms.view.max') }} {{ form.max_respondents }}</span
          >
        </div>
        <div v-if="auth.isAuthenticated" class="flex items-center gap-2 flex-wrap mt-4">
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
            :loading="exportStatus === 'pending'"
            @click="handleStartExport"
            >{{ t('forms.view.exportCSVBtn') }}</BaseButton
          >
          <span v-if="exportStatusMessage" class="text-xs text-muted">{{
            exportStatusMessage
          }}</span>
        </div>
      </BaseCard>

      <BaseAlert v-if="!form.is_active" type="error" class="mb-6 text-center">{{
        t('forms.view.closedAlert')
      }}</BaseAlert>

      <!-- Feature 3: Draft restored info bar -->
      <BaseAlert
        v-if="draftRestored && showForm"
        type="info"
        dismissible
        class="mb-4"
        @dismiss="handleClearDraft"
      >
        <div class="flex items-center justify-between">
          <span>{{ t('forms.view.draftRestored') }}</span>
          <button
            type="button"
            class="text-xs text-brand-600 hover:underline ml-3 font-medium"
            @click="handleClearDraft"
          >
            {{ t('forms.view.clearDraft') }}
          </button>
        </div>
      </BaseAlert>

      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <!-- Feature 6: Read-only view of submitted / previous response -->
      <template v-if="submitted || previousResponse">
        <BaseAlert v-if="previousResponse && !submitted" type="info" class="mb-6 text-center">
          {{ t('forms.view.alreadySubmitted') }}
        </BaseAlert>
        <BaseAlert v-else-if="submitted" type="success" class="mb-6 text-center">
          {{ message }}
        </BaseAlert>

        <BaseCard padding="lg" class="mb-6">
          <h2 class="text-lg font-semibold text-foreground mb-4">
            {{ t('forms.view.responseSummary') }}
          </h2>
          <div class="divide-y divide-border">
            <div v-for="q in form.questions" :key="q.id" class="py-3">
              <div class="text-sm font-medium text-foreground mb-1">{{ q.label }}</div>
              <div class="text-sm text-muted">
                {{ getDisplayAnswer(q, getResponseAnswers()[q.id]) }}
              </div>
            </div>
          </div>
        </BaseCard>

        <div class="flex justify-center">
          <BaseButton variant="secondary" size="md" @click="goBackToSig">
            {{ t('forms.view.backToSig') }}
          </BaseButton>
        </div>
      </template>

      <!-- Form Questions -->
      <div v-if="showForm" class="space-y-4">
        <BaseCard
          v-for="q in form.questions"
          :key="q.id"
          :ref="(el) => setQuestionRef(q.id, el)"
          :class="[
            'transition-all duration-300',
            highlightedQuestions.has(q.id)
              ? 'ring-2 ring-danger-500 border-l-4 border-l-danger-500'
              : '',
          ]"
        >
          <component
            :is="['single_choice', 'multiple_choice', 'rating'].includes(q.type) ? 'p' : 'label'"
            :for="
              ['single_choice', 'multiple_choice', 'rating'].includes(q.type)
                ? undefined
                : q.type === 'file_upload'
                  ? 'file-input-' + q.id
                  : 'fv-q-' + q.id
            "
            class="block text-sm font-medium text-foreground mb-2"
          >
            {{ q.label
            }}<span v-if="q.required" aria-hidden="true" class="text-danger-500"> *</span>
          </component>

          <!-- Text input -->
          <input
            v-if="q.type === 'text'"
            :id="'fv-q-' + q.id"
            v-model="answers[q.id]"
            type="text"
            :name="'q-' + q.id"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @input="onTextInput(q.id)"
            @blur="handleBlur(q.id, q.required)"
          />

          <!-- Textarea -->
          <textarea
            v-else-if="q.type === 'textarea'"
            :id="'fv-q-' + q.id"
            v-model="answers[q.id]"
            rows="4"
            :name="'q-' + q.id"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @input="onTextInput(q.id)"
            @blur="handleBlur(q.id, q.required)"
          ></textarea>

          <!-- Single Choice -->
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
                @change="onRadioChange(q.id)"
              />{{ opt.label }}
            </label>
          </div>

          <!-- Multiple Choice -->
          <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                :name="'q-' + q.id"
                :value="opt.id"
                :checked="(answers[q.id] as string[]).includes(opt.id)"
                @change="toggleMultipleChoice(q.id, opt.id)"
                class="rounded text-brand-600"
              />{{ opt.label }}
            </label>
          </div>

          <!-- Dropdown -->
          <select
            v-else-if="q.type === 'dropdown'"
            :id="'fv-q-' + q.id"
            v-model="answers[q.id]"
            :name="'q-' + q.id"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @change="onSelectChange(q.id)"
            @blur="handleBlur(q.id, q.required)"
          >
            <option value="">{{ t('forms.view.selectOptionPlaceholder') }}</option>
            <option v-for="opt in q.options" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>

          <!-- Rating (Feature 5) -->
          <div v-else-if="q.type === 'rating'">
            <div class="flex items-center gap-2 flex-wrap" role="group" :aria-label="q.label">
              <span class="text-xs text-muted shrink-0">{{ q.labels?.min ?? q.min ?? 1 }}</span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="n in ratingRange(q)"
                  :key="n"
                  type="button"
                  @click="selectRating(q.id, n)"
                  :aria-label="t('accessibility.rateNOutOfM', { n, m: q.max ?? 5 })"
                  :aria-pressed="answers[q.id] === n"
                  class="rounded-lg text-sm font-medium transition"
                  :class="[
                    ratingCount(q) > 7 ? 'w-8 h-8 text-xs' : 'w-10 h-10',
                    answers[q.id] === n
                      ? 'bg-brand-600 text-white'
                      : 'bg-surface-alt text-muted hover:bg-surface-alt/80',
                  ]"
                >
                  {{ n }}
                </button>
              </div>
              <span class="text-xs text-muted shrink-0">{{ q.labels?.max ?? q.max ?? 5 }}</span>
            </div>
          </div>

          <!-- File Upload (Feature 4) -->
          <div v-else-if="q.type === 'file_upload'">
            <input
              :id="`file-input-${q.id}`"
              type="file"
              :name="'q-file-' + q.id"
              class="sr-only"
              :accept="q.allowed_types?.map((t) => `.${t}`).join(',') || undefined"
              @change="handleFileUpload(q.id, $event)"
            />

            <!-- Drop zone (no file selected) -->
            <div
              v-if="!isFileObject(answers[q.id]) && !answers[q.id]"
              class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors"
              :class="
                dragOverQuestions.has(q.id)
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-border hover:border-brand-400'
              "
              role="button"
              :aria-label="t('forms.view.dropZoneLabel')"
              tabindex="0"
              @click="triggerFileInput(q.id)"
              @drop="handleDrop(q.id, $event)"
              @dragover="handleDragOver(q.id, $event)"
              @dragleave="handleDragLeave(q.id)"
              @keydown.enter="triggerFileInput(q.id)"
              @keydown.space.prevent="triggerFileInput(q.id)"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="mx-auto h-8 w-8 text-muted mb-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p class="text-sm text-muted">{{ t('forms.view.dropZoneText') }}</p>
            </div>

            <!-- File selected: preview -->
            <div
              v-else-if="isFileObject(answers[q.id])"
              class="border border-border rounded-lg p-4"
            >
              <div class="flex items-center gap-3">
                <!-- Image preview thumbnail -->
                <img
                  v-if="filePreviews[q.id]"
                  :src="filePreviews[q.id]"
                  alt="Preview"
                  class="w-12 h-12 object-cover rounded"
                />
                <div
                  v-else
                  class="w-12 h-12 rounded bg-surface-alt flex items-center justify-center"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="h-6 w-6 text-muted"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-foreground truncate">
                    {{ getFileName(answers[q.id]) }}
                  </p>
                  <p class="text-xs text-muted">
                    {{ formatFileSize((answers[q.id] as File).size) }}
                  </p>
                </div>
                <button
                  type="button"
                  class="text-danger-500 hover:text-danger-700 text-sm font-medium"
                  :aria-label="t('forms.view.removeFile')"
                  @click="removeFile(q.id)"
                >
                  {{ t('forms.view.removeFile') }}
                </button>
              </div>
            </div>

            <!-- Upload spinner -->
            <div v-if="uploadingFiles.includes(q.id)" class="flex items-center gap-2 mt-2">
              <div
                class="animate-spin rounded-full h-4 w-4 border-2 border-brand-600 border-t-transparent"
              ></div>
              <span class="text-xs text-muted">{{ t('forms.view.uploading') }}</span>
            </div>

            <p v-if="q.allowed_types && q.allowed_types.length" class="text-xs text-muted mt-2">
              {{ t('forms.view.allowedTypes') }} {{ q.allowed_types.join(', ') }}
            </p>
            <p v-if="q.max_size_mb" class="text-xs text-muted mt-1">
              {{ t('forms.view.maxFileSize', { max: q.max_size_mb }) }}
            </p>
          </div>

          <!-- Character count for text fields -->
          <p
            v-if="(q.type === 'text' || q.type === 'textarea') && q.max_length"
            class="text-xs text-muted mt-1 text-right"
          >
            {{ (answers[q.id] as string)?.length || 0 }} / {{ q.max_length }}
          </p>

          <!-- Feature 2: Per-question validation error -->
          <p v-if="validationErrors[q.id]" class="text-xs text-danger-600 mt-1" role="alert">
            {{ validationErrors[q.id] }}
          </p>
          <!-- Inline validation on blur for required fields -->
          <p
            v-else-if="touched[q.id] && q.required && !answers[q.id]"
            class="text-sm text-danger-600 mt-1"
            data-testid="inline-validation-error"
          >
            {{ t('forms.view.fieldRequired') }}
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

    <!-- Feature 7: Back to Top -->
    <BackToTop />
  </div>
</template>
