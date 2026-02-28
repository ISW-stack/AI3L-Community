<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'

const router = useRouter()
const auth = useAuthStore()

const inviteCode = ref('')
const displayName = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const error = ref('')
const loading = ref(false)

async function loadCaptcha() {
  const { data } = await api.get('/auth/captcha')
  captchaId.value = data.captcha_id
  captchaImage.value = data.image_base64
  captchaCode.value = ''
}

async function handleGuestLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.guestLogin(inviteCode.value, displayName.value, captchaId.value, captchaCode.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Guest login failed. Please try again.'
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

loadCaptcha()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md bg-white rounded-xl shadow-lg p-8">
      <h1 class="text-2xl font-bold text-center text-gray-900 mb-2">Guest Access</h1>
      <p class="text-center text-sm text-gray-500 mb-6">
        Guests can browse public content. Sessions last 45 minutes. Max 30 concurrent guests.
      </p>

      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleGuestLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Invite Code</label>
          <input
            v-model="inviteCode"
            type="text"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            placeholder="Enter your invite code"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
          <input
            v-model="displayName"
            type="text"
            required
            maxlength="100"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            placeholder="Enter a display name"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Captcha</label>
          <div class="flex gap-3 items-center">
            <input
              v-model="captchaCode"
              type="text"
              required
              maxlength="4"
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder="Enter captcha code"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              alt="captcha"
              class="h-10 rounded cursor-pointer"
              @click="loadCaptcha"
              title="Click to refresh captcha"
            />
          </div>
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-gray-700 text-white py-2.5 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {{ loading ? 'Entering...' : 'Enter as Guest' }}
        </button>
      </form>

      <div class="mt-6 text-center text-sm text-gray-500 space-y-2">
        <p>
          Want full access?
          <router-link to="/register" class="text-blue-600 hover:underline">Sign Up</router-link>
        </p>
        <p>
          Already have an account?
          <router-link to="/login" class="text-blue-600 hover:underline">Log In</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
