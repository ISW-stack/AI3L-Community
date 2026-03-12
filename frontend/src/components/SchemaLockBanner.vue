<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  responseCount: number
  formId: string
}>()

const emit = defineEmits<{
  viewResponses: []
}>()

const { t } = useI18n()

function handleViewResponses() {
  emit('viewResponses')
}
</script>

<template>
  <div
    class="bg-amber-50 border border-amber-300 rounded-lg p-4 mb-4"
    role="alert"
    aria-label="Schema locked warning"
  >
    <div class="flex items-start gap-3">
      <svg
        class="w-5 h-5 text-amber-600 shrink-0 mt-0.5"
        fill="currentColor"
        viewBox="0 0 20 20"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z"
          clip-rule="evenodd"
        />
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-amber-800">
          {{ t('forms.builder.schemaLockBanner.message', { count: responseCount }) }}
        </p>
        <button
          class="mt-2 text-sm font-medium text-amber-700 hover:text-amber-900 underline"
          aria-label="View responses"
          @click="handleViewResponses"
        >
          {{ t('forms.builder.schemaLockBanner.viewResponses') }}
        </button>
      </div>
    </div>
  </div>
</template>
