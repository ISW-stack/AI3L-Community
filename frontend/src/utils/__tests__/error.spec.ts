import { describe, it, expect } from 'vitest'
import { getErrorMessage } from '../error'

describe('getErrorMessage', () => {
  it('returns string detail directly', () => {
    const error = { response: { data: { detail: 'Failed to update' } } }
    expect(getErrorMessage(error)).toBe('Failed to update')
  })

  it('returns detail.message from object detail', () => {
    const error = {
      response: { data: { detail: { message: 'Validation failed', code: 'INVALID' } } },
    }
    expect(getErrorMessage(error)).toBe('Validation failed')
  })

  it('returns fallback when no response', () => {
    const error = new Error('network error')
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('returns fallback when detail is null', () => {
    const error = { response: { data: { detail: null } } }
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('returns fallback when detail is undefined', () => {
    const error = { response: { data: {} } }
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('returns fallback for non-object errors — string', () => {
    expect(getErrorMessage('something went wrong')).toBe('An unexpected error occurred.')
  })

  it('returns fallback for non-object errors — number', () => {
    expect(getErrorMessage(42)).toBe('An unexpected error occurred.')
  })

  it('returns fallback for non-object errors — null', () => {
    expect(getErrorMessage(null)).toBe('An unexpected error occurred.')
  })

  it('returns custom fallback message when passed as string', () => {
    expect(getErrorMessage({}, 'Custom fallback')).toBe('Custom fallback')
  })

  it('handles detail object without message field', () => {
    const error = { response: { data: { detail: { code: 'ERR_001' } } } }
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('handles detail object with empty message', () => {
    const error = { response: { data: { detail: { message: '' } } } }
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('handles nested null response.data', () => {
    const error = { response: { data: null } }
    expect(getErrorMessage(error)).toBe('An unexpected error occurred.')
  })

  it('translates error code when t function is provided', () => {
    const error = {
      response: {
        data: { detail: { code: 'AUTH_010', message: 'Invalid username or password.' } },
      },
    }
    const t = (key: string) => (key === 'errors.AUTH_010' ? 'Translated message' : key)
    expect(getErrorMessage(error, t)).toBe('Translated message')
  })

  it('falls back to message when t returns untranslated key', () => {
    const error = {
      response: { data: { detail: { code: 'UNKNOWN_CODE', message: 'Some error' } } },
    }
    const t = (key: string) => key // returns key unchanged (no translation found)
    expect(getErrorMessage(error, t)).toBe('Some error')
  })

  it('does not translate when t is not provided even if code exists', () => {
    const error = {
      response: { data: { detail: { code: 'AUTH_005', message: 'Invalid captcha.' } } },
    }
    expect(getErrorMessage(error)).toBe('Invalid captcha.')
  })

  it('translates error_code field (alternative field name)', () => {
    const error = {
      response: { data: { detail: { error_code: 'AUTH_010', message: 'Fallback message' } } },
    }
    const t = (key: string) => (key === 'errors.AUTH_010' ? 'Translated via error_code' : key)
    expect(getErrorMessage(error, t)).toBe('Translated via error_code')
  })

  it('uses fallbackKey with t function when no detail', () => {
    const error = new Error('network')
    const t = (key: string) =>
      key === 'auth.loginFailed' ? 'Login failed. Please try again.' : key
    expect(getErrorMessage(error, t, 'auth.loginFailed')).toBe('Login failed. Please try again.')
  })

  it('falls back to t(fallbackKey) when detail.code has no translation', () => {
    const error = {
      response: { data: { detail: { code: 'UNKNOWN', message: '' } } },
    }
    const t = (key: string) => (key === 'auth.loginFailed' ? 'Login failed.' : key)
    expect(getErrorMessage(error, t, 'auth.loginFailed')).toBe('Login failed.')
  })
})
