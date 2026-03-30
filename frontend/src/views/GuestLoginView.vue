<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getCaptcha } from '@/api/auth'
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

const inviteCode = ref('')
const displayName = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const captchaError = ref(false)
const mathMode = ref(false)
const lastError = ref<unknown>(null)
const error = computed(() => {
  void currentLocale.value
  if (!lastError.value) return ''
  return getErrorMessage(lastError.value, t, 'auth.guestLoginFailed')
})
const loading = ref(false)

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

async function handleGuestLogin() {
  lastError.value = null
  loading.value = true
  try {
    await auth.guestLogin(inviteCode.value, displayName.value, captchaId.value, captchaCode.value)
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
        <h1 class="text-2xl font-bold text-center text-foreground mb-2">
          {{ t('auth.guestTitle') }}
        </h1>
        <p class="text-center text-sm text-muted mb-6">
          {{ t('auth.guestSubtitle') }}
        </p>

        <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

        <form @submit.prevent="handleGuestLogin" class="space-y-4">
          <BaseInput
            id="input-invite-code"
            v-model="inviteCode"
            :label="t('auth.inviteCode')"
            :placeholder="t('auth.inviteCodePlaceholder')"
            autocomplete="off"
            required
          />
          <BaseInput
            id="input-display-name"
            v-model="displayName"
            :label="t('auth.displayName')"
            :placeholder="t('auth.displayName')"
            autocomplete="nickname"
            required
          />

          <div>
            <label for="guest-captcha" class="block text-sm font-medium text-foreground mb-1">{{
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
                id="guest-captcha"
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
                class="h-10 rounded cursor-pointer"
                @click="loadCaptcha"
                :title="t('auth.captchaRefresh')"
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
            {{ loading ? t('auth.guestLoading') : t('auth.guestButton') }}
          </BaseButton>
        </form>

        <div class="mt-6 text-center text-sm text-muted space-y-2">
          <p>
            {{ t('auth.wantFullAccess') }}
            <router-link to="/register" class="text-brand-600 hover:underline">{{
              t('auth.wantFullAccessLink')
            }}</router-link>
          </p>
          <p>
            {{ t('auth.hasAccount') }}
            <router-link to="/login" class="text-brand-600 hover:underline">{{
              t('auth.hasAccountLink')
            }}</router-link>
          </p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
