import { describe, it, expect } from 'vitest'
import en from '@/locales/en'
import zhTW from '@/locales/zhTW'
import zhCN from '@/locales/zhCN'
import ja from '@/locales/ja'
import ko from '@/locales/ko'
import fr from '@/locales/fr'
import es from '@/locales/es'
import de from '@/locales/de'
import ar from '@/locales/ar'
import pt from '@/locales/pt'
import ru from '@/locales/ru'
import hi from '@/locales/hi'
import localeId from '@/locales/id'
import localeIt from '@/locales/it'
import vi from '@/locales/vi'
import tr from '@/locales/tr'
import nan from '@/locales/nan'

function extractKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      keys.push(...extractKeys(v as Record<string, unknown>, fullKey))
    } else {
      keys.push(fullKey)
    }
  }
  return keys
}

const enKeys = extractKeys(en)

const locales: Record<string, Record<string, unknown>> = {
  'zh-TW': zhTW as unknown as Record<string, unknown>,
  'zh-CN': zhCN as unknown as Record<string, unknown>,
  ja: ja as unknown as Record<string, unknown>,
  ko: ko as unknown as Record<string, unknown>,
  fr: fr as unknown as Record<string, unknown>,
  es: es as unknown as Record<string, unknown>,
  de: de as unknown as Record<string, unknown>,
  ar: ar as unknown as Record<string, unknown>,
  pt: pt as unknown as Record<string, unknown>,
  ru: ru as unknown as Record<string, unknown>,
  hi: hi as unknown as Record<string, unknown>,
  id: localeId as unknown as Record<string, unknown>,
  it: localeIt as unknown as Record<string, unknown>,
  vi: vi as unknown as Record<string, unknown>,
  tr: tr as unknown as Record<string, unknown>,
  nan: nan as unknown as Record<string, unknown>,
}

describe('i18n completeness', () => {
  it('en.ts has all expected top-level sections', () => {
    const topSections = [
      'branding',
      'common',
      'language',
      'auth',
      'privacy',
      'nav',
      'footer',
      'home',
      'forum',
      'post',
      'share',
      'editor',
      'sigs',
      'forms',
      'profile',
      'userProfile',
      'notifications',
      'about',
      'admin',
      'errors',
    ]
    for (const section of topSections) {
      expect(en).toHaveProperty(section)
    }
  })

  for (const [name, messages] of Object.entries(locales)) {
    it(`${name} has all keys from en`, () => {
      const localeKeys = new Set(extractKeys(messages))
      const missing = enKeys.filter((k) => !localeKeys.has(k))
      expect(missing, `Missing keys in ${name}: ${missing.join(', ')}`).toEqual([])
    })
  }
})
