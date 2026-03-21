import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the i18n instance before importing the module under test
const mockLocale = { value: 'en' }
vi.mock('@/locales', () => ({
  i18n: {
    global: {
      locale: mockLocale,
    },
  },
  SUPPORTED_LOCALES: ['en', 'zh-TW', 'zh-CN', 'ja', 'fr', 'es', 'de'],
  LOCALE_OPTIONS: [],
  loadLocaleMessages: vi.fn().mockResolvedValue(undefined),
}))

describe('syncLocaleFromProfile', () => {
  beforeEach(() => {
    mockLocale.value = 'en'
    localStorage.clear()
  })

  it('should set locale when given a valid preferred_language', async () => {
    const { syncLocaleFromProfile } = await import('../useLocale')

    await syncLocaleFromProfile('zh-TW')

    expect(mockLocale.value).toBe('zh-TW')
    expect(localStorage.getItem('locale')).toBe('zh-TW')
    expect(document.documentElement.lang).toBe('zh-TW')
  })

  it('should not change locale when given undefined', async () => {
    const { syncLocaleFromProfile } = await import('../useLocale')

    await syncLocaleFromProfile(undefined)

    expect(mockLocale.value).toBe('en')
    expect(localStorage.getItem('locale')).toBeNull()
  })

  it('should not change locale when given an unsupported language', async () => {
    const { syncLocaleFromProfile } = await import('../useLocale')

    await syncLocaleFromProfile('ko')

    expect(mockLocale.value).toBe('en')
    expect(localStorage.getItem('locale')).toBeNull()
  })

  it('should not change locale when given empty string', async () => {
    const { syncLocaleFromProfile } = await import('../useLocale')

    await syncLocaleFromProfile('')

    expect(mockLocale.value).toBe('en')
  })

  it('should work without Vue component context (the whole point of the fix)', async () => {
    // This test verifies the function doesn't call useI18n()
    // which would throw outside a component setup context
    const { syncLocaleFromProfile } = await import('../useLocale')

    await expect(syncLocaleFromProfile('ja')).resolves.not.toThrow()
    expect(mockLocale.value).toBe('ja')
  })
})
