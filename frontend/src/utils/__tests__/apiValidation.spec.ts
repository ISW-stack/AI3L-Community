import { describe, it, expect, vi, beforeEach } from 'vitest'
import { assertShape } from '../apiValidation'

describe('assertShape', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns data as typed value', () => {
    const data = { id: 1, name: 'test' }
    const result = assertShape<{ id: number; name: string }>(data, ['id', 'name'], 'test')
    expect(result).toBe(data)
  })

  it('logs warning for missing keys in dev mode', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const data = { id: 1 }
    assertShape(data, ['id', 'name'], 'test')
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Missing key "name"'),
      data,
    )
  })

  it('does not throw for missing keys', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(() => assertShape({}, ['a', 'b'], 'ctx')).not.toThrow()
  })

  it('handles null/undefined data gracefully', () => {
    expect(() => assertShape(null, ['a'], 'ctx')).not.toThrow()
    expect(() => assertShape(undefined, ['a'], 'ctx')).not.toThrow()
  })

  it('returns non-object data unchanged', () => {
    const result = assertShape('hello', ['a'], 'ctx')
    expect(result).toBe('hello')
  })
})
