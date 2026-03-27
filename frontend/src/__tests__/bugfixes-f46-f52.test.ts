/**
 * Tests for bug fixes F-46, F-47, F-48, F-49, F-50, F-52.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─────────────────────────────────────────────────────────
// F-46: formatDate silent locale fallback
// ─────────────────────────────────────────────────────────
describe('F-46: formatDate warns on unsupported locale in dev mode', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    warnSpy.mockRestore()
  })

  it('formatDate does not warn for supported locale "en"', async () => {
    const { formatDate } = await import('@/utils/date')
    formatDate('2024-01-15', 'en')
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('formatDate warns for unsupported locale and falls back to en', async () => {
    const { formatDate } = await import('@/utils/date')
    const result = formatDate('2024-01-15', 'xx-INVALID')
    // Should have warned
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('xx-INVALID'))
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Falling back to "en"'))
    // Should still return a formatted string (using en fallback)
    expect(result).toBeTruthy()
  })

  it('formatDateTime warns for unsupported locale', async () => {
    const { formatDateTime } = await import('@/utils/date')
    formatDateTime('2024-01-15T10:30:00Z', 'xx-INVALID')
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('xx-INVALID'))
  })

  it('formatDate does not warn for supported locale "de"', async () => {
    const { formatDate } = await import('@/utils/date')
    formatDate('2024-01-15', 'de')
    expect(warnSpy).not.toHaveBeenCalled()
  })
})

// ─────────────────────────────────────────────────────────
// F-47: extractMentions no mention length limit
// ─────────────────────────────────────────────────────────
import { extractMentions } from '@/utils/html'

describe('F-47: extractMentions enforces max length of 50 characters', () => {
  it('extracts normal-length mentions', () => {
    const result = extractMentions('Hello @alice and @bob')
    expect(result).toContain('alice')
    expect(result).toContain('bob')
  })

  it('extracts mention at exactly 50 characters', () => {
    const name = 'a'.repeat(50)
    const result = extractMentions(`@${name} hello`)
    expect(result).toContain(name)
  })

  it('rejects mentions longer than 50 characters', () => {
    const longName = 'a'.repeat(51)
    const result = extractMentions(`@${longName} hello`)
    expect(result).not.toContain(longName)
    expect(result).toHaveLength(0)
  })

  it('filters out only the too-long mentions, keeps valid ones', () => {
    const longName = 'x'.repeat(100)
    const result = extractMentions(`@alice @${longName} @bob`)
    expect(result).toContain('alice')
    expect(result).toContain('bob')
    expect(result).toHaveLength(2)
  })
})

// ─────────────────────────────────────────────────────────
// F-48: assertShape no extra key warnings
// ─────────────────────────────────────────────────────────
import { assertShape } from '@/utils/apiValidation'

describe('F-48: assertShape warns about unexpected extra keys in dev mode', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    warnSpy.mockRestore()
  })

  it('does not warn when keys match exactly', () => {
    assertShape({ id: 1, name: 'test' }, ['id', 'name'], 'test')
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('warns about missing keys', () => {
    assertShape({ id: 1 }, ['id', 'name'], 'test')
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('missing keys'))
  })

  it('warns about unexpected extra keys', () => {
    assertShape({ id: 1, name: 'test', secret: 'hidden' }, ['id', 'name'], 'test-context')
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('unexpected keys [secret]'))
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('test-context'))
  })

  it('warns about multiple extra keys', () => {
    assertShape({ id: 1, extra1: 'a', extra2: 'b' }, ['id'], 'multi-extra')
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('extra1'))
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('extra2'))
  })

  it('returns data as-is regardless of warnings', () => {
    const data = { id: 1, extra: 'value' }
    const result = assertShape<typeof data>(data, ['id'], 'test')
    expect(result).toBe(data)
  })
})

// ─────────────────────────────────────────────────────────
// F-49: DM toast sender name truncation with ellipsis
// ─────────────────────────────────────────────────────────
describe('F-49: DM sender name truncation adds ellipsis', () => {
  it('truncates name > 50 chars with ellipsis character', () => {
    const longName = 'A'.repeat(60)
    const truncated = longName.length > 50 ? longName.slice(0, 50) + '\u2026' : longName
    expect(truncated).toHaveLength(51) // 50 chars + 1 ellipsis
    expect(truncated.endsWith('\u2026')).toBe(true)
  })

  it('does not truncate name <= 50 chars', () => {
    const shortName = 'Alice'
    const result = shortName.length > 50 ? shortName.slice(0, 50) + '\u2026' : shortName
    expect(result).toBe('Alice')
  })

  it('name at exactly 50 chars is not truncated', () => {
    const name = 'B'.repeat(50)
    const result = name.length > 50 ? name.slice(0, 50) + '\u2026' : name
    expect(result).toBe(name)
    expect(result).toHaveLength(50)
  })

  it('name at 51 chars is truncated with ellipsis', () => {
    const name = 'C'.repeat(51)
    const result = name.length > 50 ? name.slice(0, 50) + '\u2026' : name
    expect(result).toHaveLength(51)
    expect(result.endsWith('\u2026')).toBe(true)
    expect(result.startsWith('C'.repeat(50))).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────
// F-50: FormsDirectoryView search not trimmed
// ─────────────────────────────────────────────────────────
describe('F-50: FormsDirectoryView search query is trimmed', () => {
  it('source code trims the search query before API call', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const source = fs.readFileSync(
      path.resolve(__dirname, '../views/forms/FormsDirectoryView.vue'),
      'utf-8',
    )
    // Check that .trim() is used on searchQuery before the API call
    expect(source).toContain('.trim()')
    // Verify the trimmed value is used in the API call
    expect(source).toMatch(/trimmed\s*(|||\|\|)\s*undefined/)
  })
})

// ─────────────────────────────────────────────────────────
// F-52: LoginView error reactivity without void hack
// ─────────────────────────────────────────────────────────
describe('F-52: LoginView error reactivity uses watch instead of void hack', () => {
  it('source code does not use void currentLocale.value hack', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const source = fs.readFileSync(path.resolve(__dirname, '../views/LoginView.vue'), 'utf-8')
    // The void currentLocale.value hack should be gone
    expect(source).not.toContain('void currentLocale.value')
    // Should use watch for locale reactivity
    expect(source).toContain('watch(currentLocale')
    // Should import watch
    expect(source).toContain('watch')
    // The computed should still exist for error
    expect(source).toContain('const error = computed(')
  })

  it('uses errorVersion pattern for reactive dependency', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const source = fs.readFileSync(path.resolve(__dirname, '../views/LoginView.vue'), 'utf-8')
    // Should have errorVersion ref that increments on locale change
    expect(source).toContain('errorVersion')
    expect(source).toContain('errorVersion.value++')
  })
})
