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
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })

  it('returns fallback when detail is null', () => {
    const error = { response: { data: { detail: null } } }
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })

  it('returns fallback when detail is undefined', () => {
    const error = { response: { data: {} } }
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })

  it('returns fallback for non-object errors — string', () => {
    expect(getErrorMessage('something went wrong')).toBe('An error occurred.')
  })

  it('returns fallback for non-object errors — number', () => {
    expect(getErrorMessage(42)).toBe('An error occurred.')
  })

  it('returns fallback for non-object errors — null', () => {
    expect(getErrorMessage(null)).toBe('An error occurred.')
  })

  it('returns custom fallback message', () => {
    expect(getErrorMessage({}, 'Custom fallback')).toBe('Custom fallback')
  })

  it('handles detail object without message field', () => {
    const error = { response: { data: { detail: { code: 'ERR_001' } } } }
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })

  it('handles detail object with empty message', () => {
    const error = { response: { data: { detail: { message: '' } } } }
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })

  it('handles nested null response.data', () => {
    const error = { response: { data: null } }
    expect(getErrorMessage(error)).toBe('An error occurred.')
  })
})
