import { createI18n } from 'vue-i18n'
import en from './en'

export const SUPPORTED_LOCALES = [
  'en',
  'zh-TW',
  'zh-CN',
  'ja',
  'fr',
  'es',
  'de',
  'ar',
  'pt',
  'ru',
  'hi',
  'ko',
  'id',
  'it',
  'vi',
  'tr',
  'nan',
] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const LOCALE_OPTIONS: { value: SupportedLocale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'ar', label: 'العربية' },
  { value: 'pt', label: 'Português' },
  { value: 'ru', label: 'Русский' },
  { value: 'hi', label: 'हिन्दी' },
  { value: 'ko', label: '한국어' },
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'it', label: 'Italiano' },
  { value: 'vi', label: 'Tiếng Việt' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'nan', label: '台語' },
]

export interface LocaleGroup {
  id: string
  labelKey: string
  locales: SupportedLocale[]
}

export const LOCALE_GROUPS: LocaleGroup[] = [
  {
    id: 'europe',
    labelKey: 'language.region.europe',
    locales: ['fr', 'es', 'de', 'pt', 'it', 'ru', 'tr'],
  },
  {
    id: 'eastAsia',
    labelKey: 'language.region.eastAsia',
    locales: ['zh-TW', 'zh-CN', 'ja', 'ko', 'nan'],
  },
  {
    id: 'southSoutheastAsia',
    labelKey: 'language.region.southSoutheastAsia',
    locales: ['hi', 'id', 'vi'],
  },
  {
    id: 'arabWorld',
    labelKey: 'language.region.arabWorld',
    locales: ['ar'],
  },
]

function detectInitialLocale(): SupportedLocale {
  const saved = localStorage.getItem('locale')
  if (saved && SUPPORTED_LOCALES.includes(saved as SupportedLocale)) {
    return saved as SupportedLocale
  }
  const browserLang = navigator.language
  if (browserLang.toLowerCase().startsWith('zh')) {
    if (browserLang.includes('TW') || browserLang.includes('HK') || browserLang.includes('Hant')) {
      return 'zh-TW'
    }
    return 'zh-CN'
  }
  if (browserLang.startsWith('ja')) return 'ja'
  if (browserLang.startsWith('fr')) return 'fr'
  if (browserLang.startsWith('es')) return 'es'
  if (browserLang.startsWith('de')) return 'de'
  if (browserLang.startsWith('ar')) return 'ar'
  if (browserLang.startsWith('pt')) return 'pt'
  if (browserLang.startsWith('ru')) return 'ru'
  if (browserLang.startsWith('hi')) return 'hi'
  if (browserLang.startsWith('ko')) return 'ko'
  if (browserLang.startsWith('id')) return 'id'
  if (browserLang.startsWith('it')) return 'it'
  if (browserLang.startsWith('vi')) return 'vi'
  if (browserLang.startsWith('tr')) return 'tr'
  if (browserLang.startsWith('nan')) return 'nan'
  return 'en'
}

type LocaleMessages = typeof en

// Lazy locale loaders — each returns a dynamic import
const localeLoaders: Record<string, () => Promise<{ default: LocaleMessages }>> = {
  'zh-TW': () => import('./zhTW'),
  'zh-CN': () => import('./zhCN'),
  ja: () => import('./ja'),
  fr: () => import('./fr'),
  es: () => import('./es'),
  de: () => import('./de'),
  ar: () => import('./ar'),
  pt: () => import('./pt'),
  ru: () => import('./ru'),
  hi: () => import('./hi'),
  ko: () => import('./ko'),
  id: () => import('./id'),
  it: () => import('./it'),
  vi: () => import('./vi'),
  tr: () => import('./tr'),
  nan: () => import('./nan'),
}

// Aliases that share the same locale file
const localeAliases: Record<string, string> = {
  zh: 'zh-TW',
  'zh-HK': 'zh-TW',
  'zh-hans': 'zh-CN',
}

const loadedLocales = new Set<string>(['en'])
// In-flight map prevents duplicate network requests for the same locale
const inFlight = new Map<string, Promise<void>>()

export function loadLocaleMessages(locale: string): Promise<void> {
  const resolved = localeAliases[locale] ?? locale
  if (loadedLocales.has(resolved)) {
    return Promise.resolve()
  }
  if (inFlight.has(resolved)) {
    return inFlight.get(resolved)!
  }
  const loader = localeLoaders[resolved]
  if (!loader) return Promise.resolve()
  const promise = loader().then((messages) => {
    i18n.global.setLocaleMessage(resolved, messages.default)
    loadedLocales.add(resolved)
    inFlight.delete(resolved)
    // Set aliases pointing to this locale
    for (const [alias, target] of Object.entries(localeAliases)) {
      if (target === resolved) {
        i18n.global.setLocaleMessage(alias, messages.default)
      }
    }
  })
  inFlight.set(resolved, promise)
  return promise
}

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'en',
  messages: { en },
  silentFallbackWarn: !import.meta.env.DEV,
  silentTranslationWarn: !import.meta.env.DEV,
})
