<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
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

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value, captchaId.value, captchaCode.value)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed. Please try again.'
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
      <h1 class="text-2xl font-bold text-center text-gray-900 mb-6">Log In to AI3L Community</h1>

      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input
            v-model="username"
            type="text"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            placeholder="Enter your username"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            placeholder="Enter your password"
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
          class="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {{ loading ? 'Logging in...' : 'Log In' }}
        </button>
      </form>

      <div class="mt-6 text-center text-sm text-gray-500 space-y-2">
        <p>
          Don't have an account?
          <router-link to="/register" class="text-blue-600 hover:underline">Sign Up</router-link>
        </p>
        <p>
          Or browse as a
          <router-link to="/guest" class="text-blue-600 hover:underline">Guest</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
