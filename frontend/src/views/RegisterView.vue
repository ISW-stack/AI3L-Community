<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getCaptcha } from '@/api/auth'
import { Eye, EyeOff } from 'lucide-vue-next'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import { getErrorMessage } from '@/utils/error'
import { useLocale } from '@/composables/useLocale'
import type { SupportedLocale } from '@/locales'

const { t, currentLocale, localeOptions, setLocale } = useLocale()

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const inviteCode = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const captchaError = ref(false)
const mathMode = ref(false)
const lastError = ref<unknown>(null)
const error = computed(() => {
  void currentLocale.value
  if (!lastError.value) return ''
  if (typeof lastError.value === 'string') return t(lastError.value)
  return getErrorMessage(lastError.value, t, 'auth.registerFailed')
})
const loading = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

function togglePassword() {
  showPassword.value = !showPassword.value
}

function toggleConfirmPassword() {
  showConfirmPassword.value = !showConfirmPassword.value
}

async function loadCaptcha() {
  captchaError.value = false
  try {
    const data = await getCaptcha(mathMode.value ? 'math' : undefined)
    captchaId.value = data.captcha_id
    captchaImage.value = data.image_base64
    captchaCode.value = ''
  } catch (e: unknown) {
    captchaError.value = true
    toast.show(getErrorMessage(e, t('auth.captchaLoadError')), 'error')
  }
}

function toggleMathMode() {
  mathMode.value = !mathMode.value
  loadCaptcha()
}

const passwordChecks = computed(() => ({
  length: password.value.length >= 8,
  upper: /[A-Z]/.test(password.value),
  lower: /[a-z]/.test(password.value),
  digit: /[0-9]/.test(password.value),
  special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?\/~]/.test(password.value),
}))

const passwordValid = computed(
  () =>
    passwordChecks.value.length &&
    passwordChecks.value.upper &&
    passwordChecks.value.lower &&
    passwordChecks.value.digit &&
    passwordChecks.value.special,
)

const passwordsMatch = computed(
  () => password.value === confirmPassword.value && password.value.length > 0,
)

// Username validation: 3-50 chars, alphanumeric + underscore + hyphen + dot + @ (mirrors backend)
const USERNAME_RE = /^[a-zA-Z0-9_.@-]+$/
const usernameValid = computed(() => {
  const u = username.value
  if (u.length === 0) return true // Don't show error for empty (required handles it)
  return u.length >= 3 && u.length <= 50 && USERNAME_RE.test(u)
})
const usernameError = computed(() => {
  const u = username.value
  if (u.length === 0) return ''
  if (u.length < 3) return t('auth.usernameMinLength')
  if (u.length > 50) return t('auth.usernameMaxLength')
  if (!USERNAME_RE.test(u)) return t('auth.usernameFormat')
  return ''
})

async function handleRegister() {
  if (!usernameValid.value) {
    lastError.value = 'auth.usernameInvalid'
    return
  }
  if (!passwordValid.value) {
    lastError.value = 'auth.passwordInvalid'
    return
  }
  if (!passwordsMatch.value) {
    lastError.value = 'auth.passwordMismatch'
    return
  }

  lastError.value = null
  loading.value = true
  try {
    await auth.register(
      username.value,
      password.value,
      displayName.value,
      inviteCode.value,
      captchaId.value,
      captchaCode.value,
    )
    router.push('/')
  } catch (e: unknown) {
    lastError.value = e
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCaptcha()
})
</script>

<template>
  <div class="flex min-h-[70vh]">
    <div class="fixed top-20 right-4 z-40">
      <select
        name="locale"
        :value="currentLocale"
        class="text-sm bg-transparent border border-border rounded px-2 py-1 text-foreground"
        @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
      >
        <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>
    <!-- Left branding panel (desktop only) -->
    <div
      class="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-brand-900 to-brand-700 rounded-l-lg items-center justify-center p-12"
    >
      <div class="text-center text-white">
        <img src="/images/logo.png" alt="AI3L" class="w-72 mx-auto mb-6" />
        <h2 class="text-3xl font-bold mb-3">{{ t('branding.title') }}</h2>
        <p class="text-brand-200 text-lg">{{ t('branding.tagline') }}</p>
        <p class="text-brand-300 mt-4 text-sm max-w-sm">
          {{ t('branding.description') }}
        </p>
      </div>
    </div>
    <!-- Right form panel -->
    <div class="flex-1 flex items-center justify-center p-4">
      <BaseCard padding="lg" class="w-full max-w-md shadow-lg">
        <h1 class="text-2xl font-bold text-center text-foreground mb-6">
          {{ t('auth.registerTitle') }}
        </h1>

        <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <div>
            <BaseInput
              id="input-username"
              v-model="username"
              :label="t('auth.username')"
              :placeholder="t('auth.usernameHelper')"
              autocomplete="username"
              required
            />
            <p v-if="usernameError" class="text-danger-500 text-xs mt-1">
              {{ usernameError }}
            </p>
          </div>
          <BaseInput
            id="input-display-name"
            v-model="displayName"
            :label="t('auth.displayName')"
            autocomplete="nickname"
            required
          />
          <BaseInput
            id="input-invite-code"
            v-model="inviteCode"
            :label="t('auth.inviteCode')"
            :placeholder="t('auth.inviteCodePlaceholder')"
            autocomplete="off"
            required
          />

          <div>
            <div class="relative">
              <BaseInput
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                :label="t('auth.password')"
                autocomplete="new-password"
                required
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 mt-3 text-muted hover:text-foreground"
                @click="togglePassword"
                :aria-label="showPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              >
                <component :is="showPassword ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>
            <ul class="mt-2 text-xs space-y-1" aria-live="polite">
              <li :class="passwordChecks.length ? 'text-success-600' : 'text-muted'">
                {{ t('auth.validation.length') }}
              </li>
              <li :class="passwordChecks.upper ? 'text-success-600' : 'text-muted'">
                {{ t('auth.validation.upper') }}
              </li>
              <li :class="passwordChecks.lower ? 'text-success-600' : 'text-muted'">
                {{ t('auth.validation.lower') }}
              </li>
              <li :class="passwordChecks.digit ? 'text-success-600' : 'text-muted'">
                {{ t('auth.validation.digit') }}
              </li>
              <li :class="passwordChecks.special ? 'text-success-600' : 'text-muted'">
                {{ t('auth.validation.special') }}
              </li>
            </ul>
          </div>

          <div>
            <div class="relative">
              <BaseInput
                v-model="confirmPassword"
                :type="showConfirmPassword ? 'text' : 'password'"
                :label="t('auth.confirmPassword')"
                autocomplete="new-password"
                required
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 mt-3 text-muted hover:text-foreground"
                @click="toggleConfirmPassword"
                :aria-label="showConfirmPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              >
                <component :is="showConfirmPassword ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>
            <p v-if="confirmPassword && !passwordsMatch" class="text-danger-500 text-xs mt-1">
              {{ t('auth.passwordMismatch') }}
            </p>
          </div>

          <div>
            <label for="register-captcha" class="block text-sm font-medium text-foreground mb-1">{{
              t('auth.captcha')
            }}</label>
            <div v-if="captchaError" class="text-danger-600 text-sm mb-2">
              {{ t('auth.captchaLoadError') }}
              <button type="button" class="ml-2 underline text-brand-600" @click="loadCaptcha">
                {{ t('auth.captchaRetry') }}
              </button>
            </div>
            <div class="flex gap-3 items-center">
              <input
                id="register-captcha"
                v-model="captchaCode"
                type="text"
                name="captcha"
                required
                :maxlength="mathMode ? 6 : 4"
                autocomplete="off"
                class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
                :placeholder="mathMode ? t('auth.captchaMathPlaceholder') : t('auth.captchaPlaceholder')"
              />
              <button
                type="button"
                class="flex-shrink-0 p-1.5 rounded-lg border border-border hover:bg-surface-hover transition-colors"
                :title="mathMode ? t('auth.captchaSwitchRegular') : t('auth.captchaSwitchMath')"
                @click="toggleMathMode"
              >
                <svg v-if="!mathMode" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="w-5 h-5 text-muted" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M7 4c-1.5 0-2.5 1.2-2.5 2.5S6 9 7 10c1 1 1.5 2.3 1.5 3.5S7.5 16 6 16" />
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="w-5 h-5 text-muted" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M7 8h10M7 12h10M7 16h10" />
                </svg>
              </button>
              <img
                v-if="captchaImage"
                :src="captchaImage"
                alt="captcha"
                class="h-10 w-auto max-w-[45%] min-w-0 object-contain rounded-lg cursor-pointer hover:opacity-80 transition-opacity ring-1 ring-border"
                @click="loadCaptcha"
                :title="t('auth.captchaRefresh')"
              />
            </div>
          </div>

          <BaseButton
            type="submit"
            size="full"
            :loading="loading"
            :disabled="loading || !passwordValid || !passwordsMatch || !usernameValid"
          >
            {{ loading ? t('auth.signUpLoading') : t('auth.signUpButton') }}
          </BaseButton>
        </form>

        <p class="mt-6 text-center text-sm text-muted">
          {{ t('auth.hasAccount') }}
          <router-link to="/login" class="text-brand-600 hover:underline">{{
            t('auth.hasAccountLink')
          }}</router-link>
        </p>
      </BaseCard>
    </div>
  </div>
</template>
