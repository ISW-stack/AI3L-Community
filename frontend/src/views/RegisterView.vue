<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseCard from '@/components/base/BaseCard.vue'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const inviteCode = ref('')
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

const passwordChecks = computed(() => ({
  length: password.value.length >= 8,
  upper: /[A-Z]/.test(password.value),
  lower: /[a-z]/.test(password.value),
  digit: /[0-9]/.test(password.value),
}))

const passwordValid = computed(
  () => passwordChecks.value.length && passwordChecks.value.upper && passwordChecks.value.lower && passwordChecks.value.digit,
)

const passwordsMatch = computed(() => password.value === confirmPassword.value && password.value.length > 0)

async function handleRegister() {
  if (!passwordValid.value) {
    error.value = 'Password does not meet the security requirements.'
    return
  }
  if (!passwordsMatch.value) {
    error.value = 'Passwords do not match.'
    return
  }

  error.value = ''
  loading.value = true
  try {
    await auth.register(username.value, password.value, displayName.value, inviteCode.value, captchaId.value, captchaCode.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Registration failed. Please try again.'
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
      <h1 class="text-2xl font-bold text-center text-foreground mb-6">Create an Account</h1>

      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <BaseInput v-model="username" label="Username" placeholder="3-50 characters" required />
        <BaseInput v-model="displayName" label="Display Name" required />
        <BaseInput v-model="inviteCode" label="Invite Code" placeholder="Enter your invite code" required />

        <div>
          <BaseInput v-model="password" type="password" label="Password" required />
          <ul class="mt-2 text-xs space-y-1" aria-live="polite">
            <li :class="passwordChecks.length ? 'text-success-600' : 'text-muted'">At least 8 characters</li>
            <li :class="passwordChecks.upper ? 'text-success-600' : 'text-muted'">Contains an uppercase letter</li>
            <li :class="passwordChecks.lower ? 'text-success-600' : 'text-muted'">Contains a lowercase letter</li>
            <li :class="passwordChecks.digit ? 'text-success-600' : 'text-muted'">Contains a digit</li>
          </ul>
        </div>

        <div>
          <BaseInput v-model="confirmPassword" type="password" label="Confirm Password" required />
          <p v-if="confirmPassword && !passwordsMatch" class="text-danger-500 text-xs mt-1">Passwords do not match</p>
        </div>

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

        <BaseButton type="submit" size="full" :loading="loading" :disabled="loading || !passwordValid || !passwordsMatch">
          {{ loading ? 'Signing up...' : 'Sign Up' }}
        </BaseButton>
      </form>

      <p class="mt-6 text-center text-sm text-muted">
        Already have an account?
        <router-link to="/login" class="text-brand-600 hover:underline">Log In</router-link>
      </p>
    </BaseCard>
  </div>
</template>
