/**
 * Tests for centralized DOMPurify config and mXSS prevention.
 *
 * CR-01: mXSS via unsanitized contentSegments after DOM round-trip
 * CR-02: html.ts renderMentions now uses centralized sanitizeHtml
 * M-12: Centralized DOMPurify configuration
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sanitizeHtml, addLinkSafety, sanitizePreviewHtml, SANITIZE_CONFIG } from '@/utils/sanitize'

// ────────────────────────────────────────────────────────────────
// sanitizeHtml — basic sanitization
// ────────────────────────────────────────────────────────────────

describe('sanitizeHtml', () => {
  it('strips script tags', () => {
    const input = '<p>Hello</p><script>alert("xss")</script>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('<script')
    expect(result).not.toContain('alert')
    expect(result).toContain('<p>Hello</p>')
  })

  it('strips onerror and onload attributes', () => {
    const input = '<img src="x" onerror="alert(1)"><div onload="alert(2)">text</div>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('onerror')
    expect(result).not.toContain('onload')
    expect(result).not.toContain('alert')
  })

  it('strips onclick and onmouseover attributes', () => {
    const input = '<a href="#" onclick="alert(1)">click</a><span onmouseover="alert(2)">hover</span>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('onclick')
    expect(result).not.toContain('onmouseover')
  })

  it('strips javascript: URLs from href', () => {
    const input = '<a href="javascript:alert(1)">link</a>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('javascript:')
  })

  it('strips iframe and object tags', () => {
    const input = '<iframe src="evil.com"></iframe><object data="evil.swf"></object>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('<iframe')
    expect(result).not.toContain('<object')
  })

  it('strips style tags', () => {
    const input = '<style>body{display:none}</style><p>text</p>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('<style')
    expect(result).toContain('<p>text</p>')
  })

  it('preserves allowed tags (p, a, img, table, strong, em, etc.)', () => {
    const input =
      '<p><strong>Bold</strong> and <em>italic</em></p>' +
      '<a href="https://example.com">link</a>' +
      '<img src="https://example.com/img.png" alt="pic">' +
      '<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Cell</td></tr></tbody></table>'
    const result = sanitizeHtml(input)
    expect(result).toContain('<p>')
    expect(result).toContain('<strong>')
    expect(result).toContain('<em>')
    expect(result).toContain('<a ')
    expect(result).toContain('href="https://example.com"')
    expect(result).toContain('<img ')
    expect(result).toContain('<table>')
    expect(result).toContain('<th>')
    expect(result).toContain('<td>')
  })

  it('preserves allowed attributes (href, src, alt, class, data-type, data-mention, data-id)', () => {
    const input =
      '<a href="https://x.com" class="link" title="t">text</a>' +
      '<span data-type="mention" data-mention="user1" data-id="123">@user1</span>'
    const result = sanitizeHtml(input)
    expect(result).toContain('href="https://x.com"')
    expect(result).toContain('class="link"')
    expect(result).toContain('title="t"')
    expect(result).toContain('data-type="mention"')
    expect(result).toContain('data-mention="user1"')
    expect(result).toContain('data-id="123"')
  })

  it('strips disallowed data-* attributes when ALLOW_DATA_ATTR is false', () => {
    const input = '<div data-custom="evil" data-type="mention">text</div>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('data-custom')
    // data-type IS allowed explicitly
    expect(result).toContain('data-type="mention"')
  })

  it('preserves heading tags', () => {
    const input = '<h1>Title</h1><h2>Sub</h2><h3>Sub2</h3>'
    const result = sanitizeHtml(input)
    expect(result).toContain('<h1>')
    expect(result).toContain('<h2>')
    expect(result).toContain('<h3>')
  })

  it('preserves list tags', () => {
    const input = '<ul><li>one</li><li>two</li></ul><ol><li>a</li></ol>'
    const result = sanitizeHtml(input)
    expect(result).toContain('<ul>')
    expect(result).toContain('<ol>')
    expect(result).toContain('<li>')
  })

  it('preserves blockquote and pre/code', () => {
    const input = '<blockquote>quote</blockquote><pre><code>code</code></pre>'
    const result = sanitizeHtml(input)
    expect(result).toContain('<blockquote>')
    expect(result).toContain('<pre>')
    expect(result).toContain('<code>')
  })
})

// ────────────────────────────────────────────────────────────────
// FORCE_BODY mXSS prevention
// ────────────────────────────────────────────────────────────────

describe('sanitizeHtml FORCE_BODY mXSS prevention', () => {
  it('prevents mXSS via math/mtext/table mutation (classic mXSS vector)', () => {
    // This is a well-known mXSS payload that exploits parser context switching
    // between HTML and MathML/SVG namespaces
    const mxssPayload =
      '<math><mtext><table><mglyph><style><!--</style>' +
      '<img src=x onerror=alert(1)>'
    const result = sanitizeHtml(mxssPayload)
    expect(result).not.toContain('onerror')
    expect(result).not.toContain('alert')
    expect(result).not.toContain('<mglyph')
    expect(result).not.toContain('<math')
  })

  it('prevents mXSS via SVG foreignObject', () => {
    const payload =
      '<svg><foreignObject><div><style><!--</style>' +
      '<img src=x onerror=alert(1)></div></foreignObject></svg>'
    const result = sanitizeHtml(payload)
    expect(result).not.toContain('onerror')
    expect(result).not.toContain('alert')
    expect(result).not.toContain('<svg')
  })

  it('prevents mXSS via noscript reinterpretation', () => {
    const payload = '<noscript><img src=x onerror=alert(1)></noscript>'
    const result = sanitizeHtml(payload)
    expect(result).not.toContain('onerror')
    expect(result).not.toContain('alert')
  })

  it('FORCE_BODY is set in the config', () => {
    expect(SANITIZE_CONFIG.FORCE_BODY).toBe(true)
  })

  it('ALLOW_DATA_ATTR is disabled in the config', () => {
    expect(SANITIZE_CONFIG.ALLOW_DATA_ATTR).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────
// addLinkSafety
// ────────────────────────────────────────────────────────────────

describe('addLinkSafety', () => {
  it('adds rel="noopener noreferrer" and target="_blank" to external links', () => {
    const input = '<a href="https://example.com">External</a>'
    const result = addLinkSafety(input)
    expect(result).toContain('rel="noopener noreferrer"')
    expect(result).toContain('target="_blank"')
  })

  it('adds safety attributes to http:// links', () => {
    const input = '<a href="http://example.com">HTTP</a>'
    const result = addLinkSafety(input)
    expect(result).toContain('rel="noopener noreferrer"')
    expect(result).toContain('target="_blank"')
  })

  it('does not modify relative links', () => {
    const input = '<a href="/forum/123">Internal</a>'
    const result = addLinkSafety(input)
    expect(result).not.toContain('rel=')
    expect(result).not.toContain('target=')
  })

  it('does not modify anchor-only links', () => {
    const input = '<a href="#section">Anchor</a>'
    const result = addLinkSafety(input)
    expect(result).not.toContain('rel=')
    expect(result).not.toContain('target=')
  })

  it('does not modify links without href', () => {
    const input = '<a>No href</a>'
    const result = addLinkSafety(input)
    expect(result).not.toContain('rel=')
  })

  it('handles multiple links correctly', () => {
    const input =
      '<a href="https://a.com">A</a>' +
      '<a href="/local">B</a>' +
      '<a href="http://c.com">C</a>'
    const result = addLinkSafety(input)
    // External links get safety attributes
    expect(result).toMatch(/href="https:\/\/a\.com"[^>]*rel="noopener noreferrer"/)
    expect(result).toMatch(/href="http:\/\/c\.com"[^>]*rel="noopener noreferrer"/)
    // Internal link remains unchanged (check no rel near /local)
    const localLink = result.match(/<a href="\/local"[^>]*>/)
    expect(localLink).toBeTruthy()
    expect(localLink![0]).not.toContain('rel=')
  })

  it('preserves non-link HTML content', () => {
    const input = '<p>Hello</p><a href="https://x.com">link</a><p>world</p>'
    const result = addLinkSafety(input)
    expect(result).toContain('<p>Hello</p>')
    expect(result).toContain('<p>world</p>')
  })
})

// ────────────────────────────────────────────────────────────────
// sanitizePreviewHtml
// ────────────────────────────────────────────────────────────────

describe('sanitizePreviewHtml', () => {
  it('strips images and links but keeps basic formatting', () => {
    const input =
      '<p><strong>Bold</strong></p><img src="x.png"><a href="http://x.com">link</a>'
    const result = sanitizePreviewHtml(input)
    expect(result).toContain('<p>')
    expect(result).toContain('<strong>')
    expect(result).not.toContain('<img')
    expect(result).not.toContain('<a ')
  })

  it('strips all attributes', () => {
    const input = '<p class="big" id="main">text</p>'
    const result = sanitizePreviewHtml(input)
    expect(result).not.toContain('class=')
    expect(result).not.toContain('id=')
    expect(result).toContain('<p>text</p>')
  })

  it('strips script tags', () => {
    const input = '<p>text</p><script>alert(1)</script>'
    const result = sanitizePreviewHtml(input)
    expect(result).not.toContain('<script')
  })

  it('replaces tables with [table] placeholder instead of flattening cell text', () => {
    const input =
      '<p>Before</p>' +
      '<table><thead><tr><th>Name</th><th>Score</th></tr></thead>' +
      '<tbody><tr><td>Alice</td><td>100</td></tr></tbody></table>' +
      '<p>After</p>'
    const result = sanitizePreviewHtml(input)
    // Table cell text should NOT appear as flat text
    expect(result).not.toContain('Alice')
    expect(result).not.toContain('Score')
    // Placeholder should be present
    expect(result).toContain('[table]')
    // Surrounding content preserved
    expect(result).toContain('Before')
    expect(result).toContain('After')
  })

  it('handles multiple tables', () => {
    const input =
      '<table><tr><td>A</td></tr></table>' +
      '<p>gap</p>' +
      '<table><tr><td>B</td></tr></table>'
    const result = sanitizePreviewHtml(input)
    const matches = result.match(/\[table\]/g)
    expect(matches).toHaveLength(2)
    expect(result).toContain('gap')
  })
})

// ────────────────────────────────────────────────────────────────
// CR-01: contentSegments integration — re-sanitization after DOM manipulation
// ────────────────────────────────────────────────────────────────

describe('CR-01: contentSegments re-sanitizes after DOM round-trip', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('calls sanitizeHtml on initial content and on each HTML segment', async () => {
    const sanitizeCalls: string[] = []

    // Mock @/utils/sanitize to track calls
    vi.doMock('@/utils/sanitize', () => ({
      sanitizeHtml: vi.fn((html: string) => {
        sanitizeCalls.push(html)
        return html.replace(/<script[^>]*>.*?<\/script>/gi, '').replace(/on\w+="[^"]*"/gi, '')
      }),
      addLinkSafety: vi.fn((html: string) => html),
    }))

    vi.doMock('vue', async () => {
      const actual = await vi.importActual<typeof import('vue')>('vue')
      return {
        ...actual,
        onMounted: vi.fn(),
        onUnmounted: vi.fn(),
      }
    })
    vi.doMock('vue-router', async () => {
      const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
      return { ...actual, onBeforeRouteLeave: vi.fn() }
    })
    vi.doMock('@/api/posts', () => ({
      getPost: vi.fn(),
      updatePost: vi.fn(),
      deletePost: vi.fn(),
      getPostHistory: vi.fn(),
      togglePinPost: vi.fn(),
      togglePostReaction: vi.fn(),
    }))
    vi.doMock('@/api/comments', () => ({
      listComments: vi.fn(),
      createComment: vi.fn(),
      deleteComment: vi.fn(),
      updateComment: vi.fn(),
      toggleReaction: vi.fn(),
    }))
    vi.doMock('@/api/reports', () => ({ createReport: vi.fn() }))
    vi.doMock('@/api/files', () => ({ getFileScanStatus: vi.fn() }))
    vi.doMock('@/api/coauthors', () => ({ listCoAuthors: vi.fn() }))
    vi.doMock('@/api/citations', () => ({
      getCitedBy: vi.fn(),
      getCiting: vi.fn(),
    }))
    vi.doMock('@/stores/toast', () => ({
      useToastStore: () => ({ show: vi.fn() }),
    }))
    vi.doMock('@/locales', () => ({
      i18n: { global: { locale: { value: 'en' } } },
    }))

    const { ref, computed } = await import('vue')
    const { usePostDetail } = await import('@/composables/usePostDetail')

    const postId = ref('post-1')
    const detail = usePostDetail({
      postId,
      auth: {
        user: { id: 'user-1' },
        isAdmin: false,
        isAuthenticated: true,
        isGuest: false,
      },
      router: { push: vi.fn() },
    })

    // Set post with content containing a SIG card link
    detail.post.value = {
      id: 'post-1',
      title: 'Test',
      content:
        '<p>Before</p><a href="/sigs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">SIG Link</a><p>After</p>',
      author: { id: 'user-1', display_name: 'Test', avatar_url: '' },
      sig_id: null,
      sig_name: null,
      type: 'discussion',
      keywords: [],
      is_pinned: false,
      allow_comments: true,
      view_count: 0,
      comment_count: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
      version: 1,
      reaction_counts: null,
      user_reactions: null,
    } as any

    const segments = detail.contentSegments.value

    // Should have 3 segments: html (Before), sig-card, html (After)
    expect(segments.length).toBe(3)
    expect(segments[0].type).toBe('html')
    expect(segments[1].type).toBe('sig-card')
    expect(segments[2].type).toBe('html')

    // sanitizeHtml should have been called:
    // 1. Initial sanitization of post.content
    // 2+. Re-sanitization of each HTML segment fragment (not the whole innerHTML,
    //     because DOMPurify would strip the \x00 null-byte card markers)
    expect(sanitizeCalls.length).toBeGreaterThanOrEqual(2)
  })

  it('sanitizes mXSS payload injected via DOM round-trip', async () => {
    vi.doMock('@/utils/sanitize', () => ({
      sanitizeHtml: vi.fn((html: string) => {
        // Simulate DOMPurify stripping dangerous content
        return html
          .replace(/<script[^>]*>.*?<\/script>/gi, '')
          .replace(/on\w+="[^"]*"/gi, '')
          .replace(/<img[^>]*onerror[^>]*>/gi, '')
      }),
      addLinkSafety: vi.fn((html: string) => html),
    }))

    vi.doMock('vue', async () => {
      const actual = await vi.importActual<typeof import('vue')>('vue')
      return {
        ...actual,
        onMounted: vi.fn(),
        onUnmounted: vi.fn(),
      }
    })
    vi.doMock('vue-router', async () => {
      const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
      return { ...actual, onBeforeRouteLeave: vi.fn() }
    })
    vi.doMock('@/api/posts', () => ({
      getPost: vi.fn(),
      updatePost: vi.fn(),
      deletePost: vi.fn(),
      getPostHistory: vi.fn(),
      togglePinPost: vi.fn(),
      togglePostReaction: vi.fn(),
    }))
    vi.doMock('@/api/comments', () => ({
      listComments: vi.fn(),
      createComment: vi.fn(),
      deleteComment: vi.fn(),
      updateComment: vi.fn(),
      toggleReaction: vi.fn(),
    }))
    vi.doMock('@/api/reports', () => ({ createReport: vi.fn() }))
    vi.doMock('@/api/files', () => ({ getFileScanStatus: vi.fn() }))
    vi.doMock('@/api/coauthors', () => ({ listCoAuthors: vi.fn() }))
    vi.doMock('@/api/citations', () => ({
      getCitedBy: vi.fn(),
      getCiting: vi.fn(),
    }))
    vi.doMock('@/stores/toast', () => ({
      useToastStore: () => ({ show: vi.fn() }),
    }))
    vi.doMock('@/locales', () => ({
      i18n: { global: { locale: { value: 'en' } } },
    }))

    const { ref } = await import('vue')
    const { usePostDetail } = await import('@/composables/usePostDetail')

    const postId = ref('post-2')
    const detail = usePostDetail({
      postId,
      auth: {
        user: { id: 'user-1' },
        isAdmin: false,
        isAuthenticated: true,
        isGuest: false,
      },
      router: { push: vi.fn() },
    })

    // Post with no card links — goes through sanitize only path
    detail.post.value = {
      id: 'post-2',
      title: 'Test',
      content: '<p>Safe content <img src=x onerror="alert(1)"></p>',
      author: { id: 'user-1', display_name: 'Test', avatar_url: '' },
      sig_id: null,
      sig_name: null,
      type: 'discussion',
      keywords: [],
      is_pinned: false,
      allow_comments: true,
      view_count: 0,
      comment_count: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
      version: 1,
      reaction_counts: null,
      user_reactions: null,
    } as any

    const segments = detail.contentSegments.value
    expect(segments.length).toBe(1)
    // The sanitizer mock strips onerror, so no alert in output
    expect(segments[0].content).not.toContain('onerror')
  })
})

// ────────────────────────────────────────────────────────────────
// CR-02: html.ts renderMentions uses centralized sanitizeHtml
// ────────────────────────────────────────────────────────────────

describe('CR-02: renderMentions uses centralized sanitizeHtml', () => {
  it('sanitizes output after DOM manipulation in renderMentions', async () => {
    // Import the real renderMentions — it now uses sanitizeHtml from @/utils/sanitize
    const { renderMentions } = await import('@/utils/html')

    const html = '<p>Hello @admin and @user</p>'
    const result = renderMentions(html, ['admin', 'user'])

    // Should contain mention spans
    expect(result).toContain('text-brand-600')
    expect(result).toContain('@admin')
    expect(result).toContain('@user')

    // Should not contain script injection
    const xssInput = '<p>Hello @admin</p><script>alert(1)</script>'
    const xssResult = renderMentions(xssInput, ['admin'])
    expect(xssResult).not.toContain('<script')
  })
})
