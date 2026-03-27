import { describe, it, expect } from 'vitest'
import { linkify } from '../linkify'

describe('linkify', () => {
  it('returns plain text when no URLs', () => {
    expect(linkify('hello world')).toEqual([{ text: 'hello world', isUrl: false }])
  })

  it('detects a single URL', () => {
    expect(linkify('https://example.com')).toEqual([{ text: 'https://example.com', isUrl: true }])
  })

  it('detects URL with surrounding text', () => {
    const result = linkify('Visit https://example.com for info')
    expect(result).toEqual([
      { text: 'Visit ', isUrl: false },
      { text: 'https://example.com', isUrl: true },
      { text: ' for info', isUrl: false },
    ])
  })

  it('detects multiple URLs', () => {
    const result = linkify('Go to https://a.com and http://b.com ok')
    expect(result).toEqual([
      { text: 'Go to ', isUrl: false },
      { text: 'https://a.com', isUrl: true },
      { text: ' and ', isUrl: false },
      { text: 'http://b.com', isUrl: true },
      { text: ' ok', isUrl: false },
    ])
  })

  it('strips trailing punctuation from URLs', () => {
    const result = linkify('See https://example.com.')
    expect(result).toEqual([
      { text: 'See ', isUrl: false },
      { text: 'https://example.com', isUrl: true },
      { text: '.', isUrl: false },
    ])
  })

  it('handles URL with path and query params', () => {
    const result = linkify('Check https://example.com/path?q=1&b=2#section here')
    expect(result).toEqual([
      { text: 'Check ', isUrl: false },
      { text: 'https://example.com/path?q=1&b=2#section', isUrl: true },
      { text: ' here', isUrl: false },
    ])
  })

  it('handles Wikipedia-style URLs with parens', () => {
    const result = linkify('See https://en.wikipedia.org/wiki/AI_(disambiguation) for details')
    expect(result).toEqual([
      { text: 'See ', isUrl: false },
      { text: 'https://en.wikipedia.org/wiki/AI_(disambiguation)', isUrl: true },
      { text: ' for details', isUrl: false },
    ])
  })

  it('strips trailing paren when unmatched', () => {
    const result = linkify('(https://example.com)')
    expect(result[0]).toEqual({ text: '(', isUrl: false })
    expect(result[1]).toEqual({ text: 'https://example.com', isUrl: true })
    const rest = result.slice(2).map((s) => s.text).join('')
    expect(rest).toBe(')')
  })

  it('handles empty string', () => {
    expect(linkify('')).toEqual([{ text: '', isUrl: false }])
  })

  it('handles URL at start of text', () => {
    const result = linkify('https://example.com is great')
    expect(result).toEqual([
      { text: 'https://example.com', isUrl: true },
      { text: ' is great', isUrl: false },
    ])
  })

  it('strips trailing comma', () => {
    const result = linkify('Visit https://example.com, then continue')
    expect(result[0]).toEqual({ text: 'Visit ', isUrl: false })
    expect(result[1]).toEqual({ text: 'https://example.com', isUrl: true })
    // Remaining segments contain ", then continue" (may be split)
    const rest = result.slice(2).map((s) => s.text).join('')
    expect(rest).toBe(', then continue')
  })
})
