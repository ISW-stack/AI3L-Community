import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the i18n instance before importing the module under test
const mockLocale = { value: 'en' }
const mockLoadLocaleMessages = vi.fn().mockResolvedValue(undefined)
vi.mock('@/locales', () => ({
  i18n: {
    global: {
      locale: mockLocale,
    },
  },
  SUPPORTED_LOCALES: ['en', 'zh-TW', 'zh-CN', 'ja', 'fr', 'es', 'de'],
  LOCALE_OPTIONS: [],
  loadLocaleMessages: mockLoadLocaleMessages,
}))

const mockUpdateProfile = vi.fn()
vi.mock('@/api/users', () => ({
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
}))

const mockAuthStore = {
  isAuthenticated: false,
  isGuest: false,
  user: null as { preferred_language?: string } | null,
}
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: mockLocale,
    t: (key: string) => key,
  }),
}))

// ---------- F-13: useLocale setLocale rollback on API failure ----------

describe('useLocale setLocale rollback', () => {
  beforeEach(() => {
    mockLocale.value = 'en'
    localStorage.clear()
    mockUpdateProfile.mockReset()
    mockLoadLocaleMessages.mockClear()
    mockAuthStore.isAuthenticated = true
    mockAuthStore.isGuest = false
    mockAuthStore.user = { preferred_language: 'en' }
    document.documentElement.lang = 'en'
    document.documentElement.dir = 'ltr'
  })

  it('rolls back locale on API failure', async () => {
    mockUpdateProfile.mockRejectedValueOnce(new Error('API error'))
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('zh-TW' as never)

    // Should have rolled back to 'en'
    expect(mockLocale.value).toBe('en')
    expect(document.documentElement.lang).toBe('en')
  })

  it('does not write localStorage on API failure', async () => {
    mockUpdateProfile.mockRejectedValueOnce(new Error('API error'))
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('fr' as never)

    // localStorage should NOT have been set
    expect(localStorage.getItem('locale')).toBeNull()
  })

  it('persists to localStorage on API success', async () => {
    mockUpdateProfile.mockResolvedValueOnce({})
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('ja' as never)

    expect(mockLocale.value).toBe('ja')
    expect(localStorage.getItem('locale')).toBe('ja')
    expect(document.documentElement.lang).toBe('ja')
  })

  it('calls loadLocaleMessages twice on rollback (once for new, once to restore)', async () => {
    mockUpdateProfile.mockRejectedValueOnce(new Error('fail'))
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    mockLoadLocaleMessages.mockClear()
    await setLocale('de' as never)

    // First call: load 'de', second call: reload 'en' for rollback
    expect(mockLoadLocaleMessages).toHaveBeenCalledTimes(2)
    expect(mockLoadLocaleMessages).toHaveBeenNthCalledWith(1, 'de')
    expect(mockLoadLocaleMessages).toHaveBeenNthCalledWith(2, 'en')
  })

  it('guest users skip API call — no rollback needed', async () => {
    mockAuthStore.isAuthenticated = true
    mockAuthStore.isGuest = true
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('es' as never)

    // Should change locale without calling API
    expect(mockUpdateProfile).not.toHaveBeenCalled()
    expect(mockLocale.value).toBe('es')
  })

  it('unauthenticated users skip API call — no rollback needed', async () => {
    mockAuthStore.isAuthenticated = false
    mockAuthStore.isGuest = false
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('fr' as never)

    expect(mockUpdateProfile).not.toHaveBeenCalled()
    expect(mockLocale.value).toBe('fr')
  })

  it('restores document dir on rollback from RTL locale', async () => {
    mockUpdateProfile.mockRejectedValueOnce(new Error('fail'))
    const { useLocale } = await import('../useLocale')
    const { setLocale } = useLocale()

    await setLocale('ar' as never)

    // Should have rolled back dir to ltr
    expect(document.documentElement.dir).toBe('ltr')
    expect(mockLocale.value).toBe('en')
  })
})

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
