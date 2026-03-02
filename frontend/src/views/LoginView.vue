<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseCard from '@/components/base/BaseCard.vue'

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
  const data = await getCaptcha()
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
    const detail = e.response?.data?.detail
    error.value =
      typeof detail === 'object' && detail?.message
        ? detail.message
        : detail || 'Login failed. Please try again.'
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

loadCaptcha()
</script>

<template>
  <div class="flex items-center justify-center min-h-[70vh]">
    <BaseCard padding="lg" class="w-full max-w-md shadow-lg">
      <h1 class="text-2xl font-bold text-center text-foreground mb-6">Log In to AI3L Community</h1>

      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <BaseInput v-model="username" label="Username" placeholder="Enter your username" required />
        <BaseInput
          v-model="password"
          type="password"
          label="Password"
          placeholder="Enter your password"
          required
        />

        <div>
          <label class="block text-sm font-medium text-foreground mb-1">Captcha</label>
          <div class="flex gap-3 items-center">
            <input
              v-model="captchaCode"
              type="text"
              required
              maxlength="4"
              class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
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

        <BaseButton type="submit" size="full" :loading="loading" :disabled="loading">
          {{ loading ? 'Logging in...' : 'Log In' }}
        </BaseButton>
      </form>

      <div class="mt-6 text-center text-sm text-muted space-y-2">
        <p>
          Don't have an account?
          <router-link to="/register" class="text-brand-600 hover:underline">Sign Up</router-link>
        </p>
        <p>
          Or browse as a
          <router-link to="/guest" class="text-brand-600 hover:underline">Guest</router-link>
        </p>
      </div>
    </BaseCard>
  </div>
</template>
