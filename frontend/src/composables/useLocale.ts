import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { updateProfile } from '@/api/users'
import { i18n, SUPPORTED_LOCALES, LOCALE_OPTIONS, type SupportedLocale } from '@/locales'

/**
 * Sync locale from user profile (DB preferred_language).
 * Safe to call outside component setup — uses the global i18n instance directly.
 */
export function syncLocaleFromProfile(preferredLanguage: string | undefined) {
  if (preferredLanguage && SUPPORTED_LOCALES.includes(preferredLanguage as SupportedLocale)) {
    i18n.global.locale.value = preferredLanguage
    localStorage.setItem('locale', preferredLanguage)
    document.documentElement.lang = preferredLanguage
  }
}

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
    syncLocaleFromProfile(auth.user?.preferred_language)
  }

  return { t, currentLocale, localeOptions: LOCALE_OPTIONS, setLocale, syncFromProfile }
}
