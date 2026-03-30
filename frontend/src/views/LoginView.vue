<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
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
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()

const username = ref('')
const password = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const captchaError = ref(false)
const mathMode = ref(false)
const lastError = ref<unknown>(null)
const errorVersion = ref(0)
watch(currentLocale, () => {
  errorVersion.value++
})
const error = computed(() => {
  // Re-evaluate when locale changes (errorVersion increments on locale switch)
  void errorVersion.value
  if (!lastError.value) return ''
  return getErrorMessage(lastError.value, t, 'auth.loginFailed')
})
const loading = ref(false)
const showPassword = ref(false)

function togglePassword() {
  showPassword.value = !showPassword.value
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

async function handleLogin() {
  lastError.value = null
  loading.value = true
  try {
    await auth.login(username.value, password.value, captchaId.value, captchaCode.value)
    const redirect = (route.query.redirect as string) || '/'
    let safeRedirect = '/'
    try {
      const url = new URL(redirect, window.location.origin)
      if (url.origin === window.location.origin) {
        safeRedirect = url.pathname + url.search + url.hash
      }
    } catch {
      // invalid URL, use default
    }
    router.push(safeRedirect)
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
  <div class="flex min-h-[70vh] relative">
    <div class="fixed top-20 right-4 z-40 lg:absolute lg:top-4 lg:right-4">
      <select
        name="locale"
        :value="currentLocale"
        class="text-sm bg-surface/80 backdrop-blur-sm border border-border rounded-lg px-2.5 py-1.5 text-foreground shadow-sm"
        @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
      >
        <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>
    <!-- Left branding panel (desktop only) -->
    <div
      class="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700 rounded-l-lg items-center justify-center p-12 relative overflow-hidden"
    >
      <!-- Decorative shapes -->
      <div class="absolute top-10 left-10 w-32 h-32 bg-white/5 rounded-full blur-xl"></div>
      <div class="absolute bottom-20 right-10 w-48 h-48 bg-white/5 rounded-full blur-2xl"></div>
      <div class="absolute top-1/2 left-1/4 w-20 h-20 bg-brand-400/10 rounded-lg rotate-12"></div>
      <div class="absolute bottom-10 left-20 w-16 h-16 bg-brand-300/10 rounded-full"></div>
      <div
        class="absolute top-20 right-20 w-24 h-24 border border-white/10 rounded-lg rotate-45"
      ></div>

      <div class="text-center text-white relative z-10">
        <img src="/images/logo.png" alt="AI3L" class="w-72 mx-auto mb-6 drop-shadow-lg" />
        <h2 class="text-3xl font-bold mb-3">{{ t('branding.title') }}</h2>
        <p class="text-brand-200 text-lg">{{ t('branding.tagline') }}</p>
        <p class="text-brand-300 mt-4 text-sm max-w-sm mx-auto leading-relaxed">
          {{ t('branding.description') }}
        </p>
      </div>
    </div>
    <!-- Right form panel -->
    <div class="flex-1 flex items-center justify-center p-3 sm:p-4">
      <BaseCard padding="lg" class="w-full max-w-md shadow-lg login-card-enter">
        <h1 class="text-2xl font-bold text-center text-foreground mb-6">
          {{ t('auth.loginTitle') }}
        </h1>

        <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <BaseInput
            id="input-username"
            v-model="username"
            :label="t('auth.username')"
            :placeholder="t('auth.username')"
            autocomplete="username"
            required
          />
          <div class="relative">
            <BaseInput
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :label="t('auth.password')"
              :placeholder="t('auth.passwordPlaceholder')"
              autocomplete="current-password"
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

          <div>
            <label for="login-captcha" class="block text-sm font-medium text-foreground mb-1">{{
              t('auth.captcha')
            }}</label>
            <div v-if="captchaError" class="text-danger-600 text-sm mb-2">
              {{ t('auth.captchaLoadError') }}
              <button type="button" class="ml-2 underline text-brand-600" @click="loadCaptcha">
                {{ t('auth.captchaRetry') }}
              </button>
            </div>
            <div class="flex gap-3 items-center">
              <BaseInput
                id="login-captcha"
                v-model="captchaCode"
                name="captcha"
                :maxlength="mathMode ? 6 : 4"
                autocomplete="off"
                :placeholder="mathMode ? t('auth.captchaMathPlaceholder') : t('auth.captchaPlaceholder')"
                class="flex-1"
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

          <BaseButton type="submit" size="full" :loading="loading" :disabled="loading">
            {{ loading ? t('auth.loginLoading') : t('auth.loginButton') }}
          </BaseButton>
        </form>

        <div class="mt-6 pt-6 border-t border-border text-center text-sm text-muted space-y-3">
          <p>
            {{ t('auth.noAccount') }}
            <router-link to="/register" class="text-brand-600 font-medium hover:underline">{{
              t('auth.noAccountLink')
            }}</router-link>
          </p>
          <p>
            {{ t('auth.browseAsGuest') }}
            <router-link to="/guest" class="text-brand-600 font-medium hover:underline">{{
              t('auth.browseAsGuestLink')
            }}</router-link>
          </p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<style scoped>
@keyframes loginCardEnter {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-card-enter {
  animation: loginCardEnter 0.4s ease-out;
}
</style>
