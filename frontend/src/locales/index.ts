import { createI18n } from 'vue-i18n'
import en from './en'
import zhTW from './zhTW'
import zhCN from './zhCN'
import ja from './ja'
import fr from './fr'
import es from './es'
import de from './de'

export const SUPPORTED_LOCALES = ['en', 'zh-TW', 'zh-CN', 'ja', 'fr', 'es', 'de'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const LOCALE_OPTIONS: { value: SupportedLocale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
]

function detectInitialLocale(): SupportedLocale {
  const saved = localStorage.getItem('locale')
  if (saved && SUPPORTED_LOCALES.includes(saved as SupportedLocale)) {
    return saved as SupportedLocale
  }
  const browserLang = navigator.language
  if (browserLang.startsWith('zh')) {
    return browserLang.includes('TW') || browserLang.includes('HK') ? 'zh-TW' : 'zh-CN'
  }
  if (browserLang.startsWith('ja')) return 'ja'
  if (browserLang.startsWith('fr')) return 'fr'
  if (browserLang.startsWith('es')) return 'es'
  if (browserLang.startsWith('de')) return 'de'
  return 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-TW': zhTW,
    'zh-CN': zhCN,
    ja,
    fr,
    es,
    de,
  },
  missing: (_locale, key) => {
    if (import.meta.env.DEV) {
      console.warn(`[i18n] Missing key: "${key}"`)
    }
  },
})
