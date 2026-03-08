import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { updateProfile } from '@/api/users'
import { SUPPORTED_LOCALES, LOCALE_OPTIONS, type SupportedLocale } from '@/locales'

export function useLocale() {
  const { locale, t } = useI18n({ useScope: 'global' })
  const auth = useAuthStore()

  const currentLocale = computed(() => locale.value as SupportedLocale)

  async function setLocale(lang: SupportedLocale) {
    locale.value = lang
    document.documentElement.lang = lang

    // Guest users: change locale for current session only, no persistence
    if (!auth.isAuthenticated || auth.isGuest) return

    localStorage.setItem('locale', lang)
    try {
      await updateProfile({ preferred_language: lang })
    } catch {
      // Local change already applied — DB write failure is non-blocking
    }
  }

  /** Called after login/profile fetch to sync locale from DB */
  function syncFromProfile() {
    const lang = auth.user?.preferred_language
    if (lang && SUPPORTED_LOCALES.includes(lang as SupportedLocale)) {
      locale.value = lang
      localStorage.setItem('locale', lang)
      document.documentElement.lang = lang
    }
  }

  return { t, currentLocale, localeOptions: LOCALE_OPTIONS, setLocale, syncFromProfile }
}
