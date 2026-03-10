import { describe, it, expect } from 'vitest'
import { extractMentions } from '../html'

describe('extractMentions', () => {
  it('returns empty array when no mentions', () => {
    expect(extractMentions('Hello world')).toEqual([])
  })

  it('extracts a single mention', () => {
    expect(extractMentions('Hello @alice!')).toEqual(['alice'])
  })

  it('extracts multiple mentions', () => {
    const result = extractMentions('Hey @alice and @bob, see this')
    expect(result).toContain('alice')
    expect(result).toContain('bob')
    expect(result).toHaveLength(2)
  })

  it('deduplicates repeated mentions', () => {
    expect(extractMentions('@alice and @alice again')).toEqual(['alice'])
  })

  it('handles hyphenated usernames', () => {
    expect(extractMentions('Hi @alice-smith')).toEqual(['alice-smith'])
  })

  it('handles mention at start of string', () => {
    expect(extractMentions('@bob hello')).toEqual(['bob'])
  })

  it('does not capture email addresses as mentions', () => {
    const result = extractMentions('email test@example.com here')
    expect(result).not.toContain('example.com')
  })
})
