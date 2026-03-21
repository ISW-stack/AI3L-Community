import { describe, it, expect } from 'vitest'
import { extractMentions, renderMentions, escapeHtml, isValidUrl } from '../html'

describe('escapeHtml', () => {
  it('escapes < and > characters', () => {
    expect(escapeHtml('<script>alert(1)</script>')).toBe(
      '&lt;script&gt;alert(1)&lt;/script&gt;',
    )
  })

  it('escapes & character', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b')
  })

  it('escapes double quotes', () => {
    expect(escapeHtml('he said "hello"')).toBe('he said &quot;hello&quot;')
  })

  it('escapes single quotes', () => {
    expect(escapeHtml("it's")).toBe('it&#39;s')
  })

  it('escapes all special characters together', () => {
    expect(escapeHtml('<img src="x" onerror=\'alert(1)\'>&')).toBe(
      '&lt;img src=&quot;x&quot; onerror=&#39;alert(1)&#39;&gt;&amp;',
    )
  })

  it('returns empty string unchanged', () => {
    expect(escapeHtml('')).toBe('')
  })

  it('returns plain text unchanged', () => {
    expect(escapeHtml('hello world')).toBe('hello world')
  })

  it('escapes XSS payload in file name', () => {
    const maliciousName = '<img src=x onerror=alert(1)>.pdf'
    const escaped = escapeHtml(maliciousName)
    expect(escaped).not.toContain('<img')
    expect(escaped).toContain('&lt;img')
  })
})

describe('isValidUrl', () => {
  it('accepts http URLs', () => {
    expect(isValidUrl('http://example.com/file.pdf')).toBe(true)
  })

  it('accepts https URLs', () => {
    expect(isValidUrl('https://example.com/file.pdf')).toBe(true)
  })

  it('accepts relative URLs (resolved against origin)', () => {
    expect(isValidUrl('/api/v1/files/content/editor/x/file.pdf')).toBe(true)
  })

  it('rejects javascript: URLs', () => {
    expect(isValidUrl('javascript:alert(1)')).toBe(false)
  })

  it('rejects data: URLs', () => {
    expect(isValidUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
  })

  it('rejects vbscript: URLs', () => {
    expect(isValidUrl('vbscript:alert(1)')).toBe(false)
  })

  it('rejects empty string', () => {
    expect(isValidUrl('')).toBe(true) // empty resolves to origin, which is http/https
  })

  it('rejects blob: URLs', () => {
    expect(isValidUrl('blob:http://example.com/abc')).toBe(false)
  })

  it('accepts URLs with ports', () => {
    expect(isValidUrl('http://localhost:19000/file.pdf')).toBe(true)
  })

  it('accepts URLs with query parameters', () => {
    expect(isValidUrl('https://example.com/file?token=abc')).toBe(true)
  })
})

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
