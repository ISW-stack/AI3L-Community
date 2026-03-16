import { describe, it, expect, vi } from 'vitest'
import { getErrorMessage } from '../error'

describe('getErrorMessage', () => {
  const t = vi.fn((key: string) => key)

  it('returns string detail directly', () => {
    const error = { response: { data: { detail: 'Failed to update' } } }
    expect(getErrorMessage(error, t)).toBe('Failed to update')
  })

  it('returns detail.message from object detail', () => {
    const error = {
      response: { data: { detail: { message: 'Validation failed', code: 'INVALID' } } },
    }
    expect(getErrorMessage(error, t)).toBe('Validation failed')
  })

  it('returns translation key for error_code', () => {
    const error = {
      response: { data: { detail: { error_code: 'invalid_credentials' } } },
    }
    // Mock t to return a different value for the specific key we want to find
    // We use mockImplementation instead of mockImplementationOnce because t is called
    // first for the fallback key in getErrorMessage.
    t.mockImplementation((key: string) =>
      key === 'auth.errors.invalid_credentials' ? 'Invalid Credentials' : key,
    )
    expect(getErrorMessage(error, t)).toBe('Invalid Credentials')
    expect(t).toHaveBeenCalledWith('auth.errors.invalid_credentials')
    // Reset implementation to not affect other tests
    t.mockImplementation((key: string) => key)
  })

  it('returns fallback when no response', () => {
    const error = new Error('network error')
    expect(getErrorMessage(error, t, 'common.unknownError')).toBe('common.unknownError')
  })

  it('returns fallback when detail is null', () => {
    const error = { response: { data: { detail: null } } }
    expect(getErrorMessage(error, t, 'common.unknownError')).toBe('common.unknownError')
  })

  it('returns fallback for non-object errors — string', () => {
    expect(getErrorMessage('something went wrong', t, 'common.unknownError')).toBe(
      'common.unknownError',
    )
  })

  it('returns custom fallback key', () => {
    expect(getErrorMessage({}, t, 'Custom fallback')).toBe('Custom fallback')
  })

  it('handles detail object without message or error_code field', () => {
    const error = { response: { data: { detail: { code: 'ERR_001' } } } }
    expect(getErrorMessage(error, t, 'common.unknownError')).toBe('common.unknownError')
  })
})
