<script setup lang="ts">
import { ref } from 'vue'
import api from '@/composables/api'

const emit = defineEmits<{ accepted: [] }>()
const submitting = ref(false)
const error = ref('')

async function acceptConsent() {
  submitting.value = true
  error.value = ''
  try {
    await api.post('/users/me/consent')
    emit('accepted')
  } catch {
    error.value = 'Failed to record consent. Please try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
    <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4">
      <h2 class="text-lg font-bold text-gray-900 mb-4">Privacy & Data Residency Consent</h2>
      <p class="text-sm text-gray-700 leading-relaxed mb-4">
        This platform stores your data on servers located in Hong Kong. By continuing,
        you consent to this data residency arrangement.
      </p>
      <p class="text-sm text-gray-500 mb-6">
        You must accept this agreement to continue using the platform.
      </p>
      <div v-if="error" class="text-sm text-red-600 mb-4">{{ error }}</div>
      <button
        @click="acceptConsent"
        :disabled="submitting"
        class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 transition disabled:opacity-50 font-medium"
      >
        {{ submitting ? 'Processing...' : 'I Agree' }}
      </button>
    </div>
  </div>
</template>
