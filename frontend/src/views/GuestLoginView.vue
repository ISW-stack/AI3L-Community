<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import { getErrorMessage } from '@/utils/error'

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
  const data = await getCaptcha()
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
  } catch (e: unknown) {
    error.value = getErrorMessage(e, 'Guest login failed. Please try again.')
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

loadCaptcha()
</script>

<template>
  <div class="flex min-h-[70vh]">
    <!-- Left branding panel (desktop only) -->
    <div
      class="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-brand-900 to-brand-700 rounded-l-lg items-center justify-center p-12"
    >
      <div class="text-center text-white">
        <h2 class="text-3xl font-bold mb-3">AI3L Community</h2>
        <p class="text-brand-200 text-lg">AI in Language Learning and Literacy</p>
        <p class="text-brand-300 mt-4 text-sm max-w-sm">
          Connect with researchers and educators advancing the future of AI-powered language
          learning.
        </p>
      </div>
    </div>
    <!-- Right form panel -->
    <div class="flex-1 flex items-center justify-center p-4">
      <BaseCard padding="lg" class="w-full max-w-md shadow-lg">
        <h1 class="text-2xl font-bold text-center text-foreground mb-2">Guest Access</h1>
        <p class="text-center text-sm text-muted mb-6">
          Guests can browse public content. Sessions last 45 minutes. Max 30 concurrent guests.
        </p>

        <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

        <form @submit.prevent="handleGuestLogin" class="space-y-4">
          <BaseInput
            v-model="inviteCode"
            label="Invite Code"
            placeholder="Enter your invite code"
            required
          />
          <BaseInput
            v-model="displayName"
            label="Display Name"
            placeholder="Enter a display name"
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

          <BaseButton
            type="submit"
            variant="secondary"
            size="full"
            :loading="loading"
            :disabled="loading"
          >
            {{ loading ? 'Entering...' : 'Enter as Guest' }}
          </BaseButton>
        </form>

        <div class="mt-6 text-center text-sm text-muted space-y-2">
          <p>
            Want full access?
            <router-link to="/register" class="text-brand-600 hover:underline">Sign Up</router-link>
          </p>
          <p>
            Already have an account?
            <router-link to="/login" class="text-brand-600 hover:underline">Log In</router-link>
          </p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
