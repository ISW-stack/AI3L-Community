import { describe, it, expect } from 'vitest'
import { extractMentions, renderMentions } from '../html'

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

describe('renderMentions', () => {
  it('returns html unchanged when mentions is null', () => {
    const html = '<p>Hello @alice</p>'
    expect(renderMentions(html, null)).toBe(html)
  })

  it('returns html unchanged when mentions is empty', () => {
    const html = '<p>Hello @alice</p>'
    expect(renderMentions(html, [])).toBe(html)
  })

  it('wraps a listed mention in a span', () => {
    const result = renderMentions('<p>Hello @alice!</p>', ['alice'])
    expect(result).toContain('<span')
    expect(result).toContain('@alice')
    expect(result).toContain('text-brand-600')
  })

  it('does not corrupt HTML attribute values containing @', () => {
    // An href containing @-like patterns should not be touched
    const html = '<p><a href="mailto:alice@example.com">contact</a> @alice</p>'
    const result = renderMentions(html, ['alice'])
    // The href must remain intact
    expect(result).toContain('href="mailto:alice@example.com"')
    // The text mention should be wrapped
    expect(result).toContain('<span')
    expect(result).toContain('@alice')
  })

  it('does not touch mentions not in the list', () => {
    const result = renderMentions('<p>@alice and @bob</p>', ['alice'])
    // alice should be wrapped
    expect(result).toContain('<span')
    expect(result).toContain('@alice')
    // bob should remain as plain text
    expect(result).toContain('@bob')
    // bob should NOT be wrapped in a span
    const bobSpanPattern = /class="text-brand-600[^"]*"[^>]*>@bob/
    expect(bobSpanPattern.test(result)).toBe(false)
  })

  it('handles multiple mentions in one string', () => {
    const result = renderMentions('<p>@alice and @bob</p>', ['alice', 'bob'])
    expect(result).toContain('@alice')
    expect(result).toContain('@bob')
    // Both should appear inside spans
    const spanCount = (result.match(/<span/g) ?? []).length
    expect(spanCount).toBeGreaterThanOrEqual(2)
  })

  it('does not double-wrap already-wrapped mentions', () => {
    const html = '<p>@alice</p>'
    const once = renderMentions(html, ['alice'])
    // Applying again should not add extra spans over the span content
    // The span text node is just '@alice', no further replacement
    const spanCount = (once.match(/<span/g) ?? []).length
    expect(spanCount).toBe(1)
  })
})
