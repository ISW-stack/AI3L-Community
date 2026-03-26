import { type Ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { updateProfile } from '@/api/users'
import {
  i18n,
  loadLocaleMessages,
  SUPPORTED_LOCALES,
  LOCALE_OPTIONS,
  type SupportedLocale,
} from '@/locales'

function applyLocaleToDocument(lang: string) {
  document.documentElement.lang = lang
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
}

export async function syncLocaleFromProfile(preferredLanguage: string | undefined) {
  if (preferredLanguage && SUPPORTED_LOCALES.includes(preferredLanguage as SupportedLocale)) {
    await loadLocaleMessages(preferredLanguage)
    const locale = i18n.global.locale as unknown as Ref<string>
    locale.value = preferredLanguage
    localStorage.setItem('locale', preferredLanguage)
    applyLocaleToDocument(preferredLanguage)
  }
}

export function useLocale() {
  const { locale, t } = useI18n({ useScope: 'global' })
  const auth = useAuthStore()

  const currentLocale = computed(() => locale.value as SupportedLocale)

  async function setLocale(lang: SupportedLocale) {
    const previousLocale = locale.value
    await loadLocaleMessages(lang)
    locale.value = lang
    applyLocaleToDocument(lang)

    // Guest users: change locale for current session only, no persistence
    if (!auth.isAuthenticated || auth.isGuest) return

    try {
      await updateProfile({ preferred_language: lang })
      // Only persist to localStorage after API success
      localStorage.setItem('locale', lang)
    } catch {
      // Rollback UI to previous locale so it stays in sync with DB
      await loadLocaleMessages(previousLocale)
      locale.value = previousLocale
      applyLocaleToDocument(previousLocale)
    }
  }

  async function syncFromProfile() {
    await syncLocaleFromProfile(auth.user?.preferred_language)
  }

  return { t, currentLocale, localeOptions: LOCALE_OPTIONS, setLocale, syncFromProfile }
}
