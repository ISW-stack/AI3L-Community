<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
const lastError = ref<unknown>(null)
const error = computed(() => {
  void currentLocale.value
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
    const data = await getCaptcha()
    captchaId.value = data.captcha_id
    captchaImage.value = data.image_base64
    captchaCode.value = ''
  } catch (e: unknown) {
    captchaError.value = true
    toast.show(getErrorMessage(e, t('auth.captchaLoadError')), 'error')
  }
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
        safeRedirect = url.pathname + url.search
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
  <div class="flex min-h-[70vh]">
    <div class="fixed top-20 right-4 z-40">
      <select
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
            <label class="block text-sm font-medium text-foreground mb-1">{{
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
                v-model="captchaCode"
                type="text"
                required
                maxlength="4"
                autocomplete="off"
                aria-label="Captcha"
                class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
                :placeholder="t('auth.captchaPlaceholder')"
              />
              <img
                v-if="captchaImage"
                :src="captchaImage"
                alt="captcha"
                class="h-10 rounded cursor-pointer"
                @click="loadCaptcha"
                :title="t('auth.captchaRefresh')"
              />
            </div>
          </div>

          <BaseButton type="submit" size="full" :loading="loading" :disabled="loading">
            {{ loading ? t('auth.loginLoading') : t('auth.loginButton') }}
          </BaseButton>
        </form>

        <div class="mt-6 text-center text-sm text-muted space-y-2">
          <p>
            {{ t('auth.noAccount') }}
            <router-link to="/register" class="text-brand-600 hover:underline">{{
              t('auth.noAccountLink')
            }}</router-link>
          </p>
          <p>
            {{ t('auth.browseAsGuest') }}
            <router-link to="/guest" class="text-brand-600 hover:underline">{{
              t('auth.browseAsGuestLink')
            }}</router-link>
          </p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
