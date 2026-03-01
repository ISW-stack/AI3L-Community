<script setup lang="ts">
import { ref } from 'vue'
import { acceptConsent as apiAcceptConsent } from '@/api/users'
import BaseButton from '@/components/base/BaseButton.vue'

const emit = defineEmits<{ accepted: [] }>()
const submitting = ref(false)
const error = ref('')

async function handleAcceptConsent() {
  submitting.value = true
  error.value = ''
  try {
    await apiAcceptConsent()
    emit('accepted')
  } catch {
    error.value = 'Failed to record consent. Please try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100] p-4"
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="consent-title"
    aria-describedby="consent-desc"
  >
    <div class="bg-surface rounded-lg shadow-xl p-6 w-full max-w-lg">
      <h2 id="consent-title" class="text-lg font-bold text-foreground mb-4">
        Privacy & Data Residency Consent
      </h2>
      <p id="consent-desc" class="text-sm text-foreground/80 leading-relaxed mb-4">
        This platform stores your data on servers located in Hong Kong. By continuing, you consent
        to this data residency arrangement.
      </p>
      <p class="text-sm text-muted mb-6">
        You must accept this agreement to continue using the platform.
      </p>
      <div v-if="error" class="text-sm text-danger-600 mb-4">{{ error }}</div>
      <BaseButton size="full" :loading="submitting" @click="handleAcceptConsent">
        I Agree
      </BaseButton>
    </div>
  </div>
</template>
