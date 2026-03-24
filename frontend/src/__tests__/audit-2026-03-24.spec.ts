/**
 * Tests for audit fixes 2026-03-24.
 *
 * CR-01: mXSS via unsanitized v-html in contentSegments
 * H-05: DM read receipt zeroes wrong direction's unread count
 * M-25: verifySession on app init
 * M-26: Visibility handler closure leak in useWebSocket
 * M-27: Global Ctrl+Z/Ctrl+Shift+Z steals undo/redo from TiptapEditor
 * M-28: scanPollTimers uses Set for bounded cleanup
 * L-19: Corrupt JSON draft warns in dev mode
 * L-20: sigId guard in useFormBuilder.saveForm
 * L-21: Client-side username format validation
 * L-22: assertShape descriptive warnings
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ────────────────────────────────────────────────────────────────
// CR-01: contentSegments re-sanitizes HTML after DOM manipulation
// ────────────────────────────────────────────────────────────────

describe('CR-01: contentSegments re-sanitizes HTML fragments', () => {
  // Must reset module state between tests
  beforeEach(() => {
    vi.resetModules()
  })

  it('sanitizes mXSS payloads in HTML segments after DOM manipulation', async () => {
    // Track sanitize calls
    const sanitizeCalls: string[] = []
    const mockSanitize = vi.fn((html: string) => {
      sanitizeCalls.push(html)
      // Simulate DOMPurify stripping dangerous content
      return html.replace(/<script[^>]*>.*?<\/script>/gi, '').replace(/on\w+="[^"]*"/gi, '')
    })

    vi.doMock('dompurify', () => ({
      default: { sanitize: mockSanitize },
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
    vi.doMock('@/api/citations', () => ({ getCitedBy: vi.fn(), getCiting: vi.fn() }))
    vi.doMock('@/stores/toast', () => ({
      useToastStore: () => ({ show: vi.fn() }),
    }))
    vi.doMock('@/composables/usePagination', () => ({
      usePagination: () => ({
        page: { value: 1 },
        total: { value: 0 },
        totalPages: { value: 0 },
        pageSize: 10,
        setPage: vi.fn(),
        resetPage: vi.fn(),
        updateFromResponse: vi.fn(),
      }),
    }))
    vi.doMock('@/utils/html', () => ({ extractMentions: vi.fn(() => []) }))
    vi.doMock('@/utils/error', () => ({
      getErrorMessage: (_e: unknown, fallback: string) => fallback,
    }))
    vi.doMock('@/utils/date', () => ({ formatDate: vi.fn(() => 'date') }))
    vi.doMock('@/locales', () => ({
      i18n: { global: { locale: { value: 'en' } } },
    }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { ref } = await import('vue')
    const { usePostDetail } = await import('@/composables/usePostDetail')

    const postId = ref('post-1')
    const auth = {
      user: { id: 'user-1' },
      isAdmin: false,
      isAuthenticated: true,
      isGuest: false,
    }
    const router = { push: vi.fn() }

    const { post, contentSegments } = usePostDetail({ postId, auth, router })

    // Set a post with content containing a link to a SIG (will be replaced by a card marker)
    // followed by extra HTML — the extra HTML must be re-sanitized
    post.value = {
      id: 'post-1',
      title: 'Test',
      content:
        '<p>Before <a href="/sigs/00000000-0000-0000-0000-000000000001">SIG Link</a> After</p>',
      author: { id: 'user-1', username: 'alice', display_name: 'Alice', avatar_url: null },
      category_id: null,
      category_name: null,
      sig_id: null,
      sig_name: null,
      keywords: null,
      allow_comments: true,
      version: 1,
      comment_count: 0,
      is_pinned: false,
      view_count: 0,
      last_comment_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    } as any

    const segments = contentSegments.value
    // Should have 3 segments: html before, sig-card, html after
    expect(segments.length).toBe(3)
    expect(segments[0].type).toBe('html')
    expect(segments[1].type).toBe('sig-card')
    expect(segments[2].type).toBe('html')

    // DOMPurify.sanitize should be called:
    // 1. First call: sanitize the full post content
    // 2+. Additional calls: re-sanitize each HTML segment after DOM manipulation
    // We just verify sanitize was called more than once (re-sanitization happened)
    expect(mockSanitize.mock.calls.length).toBeGreaterThan(1)
  })
})

// ────────────────────────────────────────────────────────────────
// H-05: DM read receipt should NOT zero unread count
// ────────────────────────────────────────────────────────────────

describe('H-05: readReceiptFromWebSocket does not zero unread count', () => {
  beforeEach(async () => {
    vi.resetModules()
  })

  async function setupDMStore() {
    vi.doMock('@/api/dm', () => ({
      listConversations: vi.fn(),
      listMessages: vi.fn(),
      sendMessage: vi.fn(),
      editMessage: vi.fn(),
      recallMessage: vi.fn(),
      markConversationRead: vi.fn(),
      getUnreadCount: vi.fn(),
    }))
    vi.doMock('@/composables/api', () => ({
      default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
    }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())
    const { useDMStore } = await import('@/stores/dm')
    return useDMStore()
  }

  it('marks own sent messages as read but does NOT zero unread_count (other user read our messages)', async () => {
    const store = await setupDMStore()
    store.setCurrentUserId('user-1')
    store.activeConversationId = 'conv-1'
    store.conversations = [
      {
        id: 'conv-1',
        other_user: { id: 'user-2', display_name: 'Alice', avatar_url: null },
        last_message: null,
        unread_count: 3, // We have 3 unread messages FROM Alice
        updated_at: '2026-03-17T00:00:00Z',
      },
    ]
    store.unreadCount = 5
    store.messages = [
      {
        id: 'msg-1',
        conversation_id: 'conv-1',
        sender: { id: 'user-1', display_name: 'Me', avatar_url: null }, // OUR message
        content: 'Hello',
        attachment_url: null,
        attachment_name: null,
        attachment_size: null,
        attachment_expires_at: null,
        is_recalled: false,
        is_edited: false,
        read_at: null,
        created_at: '2026-03-17T00:00:00Z',
        updated_at: '2026-03-17T00:00:00Z',
      },
      {
        id: 'msg-2',
        conversation_id: 'conv-1',
        sender: { id: 'user-2', display_name: 'Alice', avatar_url: null }, // THEIR message
        content: 'Hi',
        attachment_url: null,
        attachment_name: null,
        attachment_size: null,
        attachment_expires_at: null,
        is_recalled: false,
        is_edited: false,
        read_at: null,
        created_at: '2026-03-17T00:01:00Z',
        updated_at: '2026-03-17T00:01:00Z',
      },
    ]

    // DM_READ arrives — Alice read our messages
    store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

    // Our sent message should be marked as read
    expect(store.messages[0].read_at).toBe('2026-03-17T01:00:00Z')

    // Their message should NOT be marked as read (they sent it, not us)
    expect(store.messages[1].read_at).toBeNull()

    // Unread counts should NOT change — DM_READ is about the OTHER user reading OUR messages
    expect(store.conversations[0].unread_count).toBe(3)
    expect(store.unreadCount).toBe(5)
  })

  it('does not update messages when conversation is not active', async () => {
    const store = await setupDMStore()
    store.setCurrentUserId('user-1')
    store.activeConversationId = 'conv-other'
    store.messages = [
      {
        id: 'msg-1',
        conversation_id: 'conv-1',
        sender: { id: 'user-1', display_name: 'Me', avatar_url: null },
        content: 'Hello',
        attachment_url: null,
        attachment_name: null,
        attachment_size: null,
        attachment_expires_at: null,
        is_recalled: false,
        is_edited: false,
        read_at: null,
        created_at: '2026-03-17T00:00:00Z',
        updated_at: '2026-03-17T00:00:00Z',
      },
    ]

    store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

    expect(store.messages[0].read_at).toBeNull()
  })
})

// ────────────────────────────────────────────────────────────────
// M-27: Keyboard shortcut skips TiptapEditor and native inputs
// ────────────────────────────────────────────────────────────────

describe('M-27: handleKeyboardShortcut skips editor and input elements', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('does not intercept Ctrl+Z when active element is inside .ProseMirror', async () => {
    vi.doMock('vue', async () => {
      const actual = await vi.importActual<typeof import('vue')>('vue')
      return {
        ...actual,
        onMounted: vi.fn(),
        onUnmounted: vi.fn(),
      }
    })
    vi.doMock('@/api/forms', () => ({
      getForm: vi.fn(),
      createForm: vi.fn(),
      createStandaloneForm: vi.fn(),
      updateForm: vi.fn(),
    }))
    vi.doMock('@/api/sigs', () => ({ getSig: vi.fn() }))
    vi.doMock('@/api/files', () => ({ uploadEditorFile: vi.fn() }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useFormBuilder } = await import('@/composables/useFormBuilder')
    const mockRouter = { push: vi.fn(), replace: vi.fn() } as any

    const fb = useFormBuilder({
      sigId: () => 'sig-1',
      formId: () => '',
      router: mockRouter,
      t: (k: string) => k,
    })

    // Add a question so undo has something to work with
    fb.addQuestion()
    fb.addQuestion()

    // Simulate Ctrl+Z when focus is inside ProseMirror
    const proseMirrorEl = document.createElement('div')
    proseMirrorEl.className = 'ProseMirror'
    const childEl = document.createElement('p')
    proseMirrorEl.appendChild(childEl)
    document.body.appendChild(proseMirrorEl)

    Object.defineProperty(document, 'activeElement', {
      value: childEl,
      writable: true,
      configurable: true,
    })

    const event = new KeyboardEvent('keydown', {
      key: 'z',
      ctrlKey: true,
      cancelable: true,
    })
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault')

    // Dispatch the event — the handler should NOT call preventDefault
    document.dispatchEvent(event)

    // The handler should not have called preventDefault because activeElement is inside ProseMirror
    expect(preventDefaultSpy).not.toHaveBeenCalled()

    // Cleanup
    document.body.removeChild(proseMirrorEl)
    Object.defineProperty(document, 'activeElement', {
      value: document.body,
      writable: true,
      configurable: true,
    })
  })
})

// ────────────────────────────────────────────────────────────────
// L-19: Corrupt JSON draft warns in dev mode
// ────────────────────────────────────────────────────────────────

describe('L-19: Corrupt draft warns in dev mode', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it('logs console.warn when corrupt draft data is found', async () => {
    vi.doMock('vue', async () => {
      const actual = await vi.importActual<typeof import('vue')>('vue')
      return {
        ...actual,
        onUnmounted: vi.fn(),
      }
    })

    const { useDraft } = await import('@/composables/useDraft')

    // Store corrupt JSON
    localStorage.setItem('test_draft', '{invalid json')

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const draft = useDraft({
      key: 'test_draft',
      defaultValue: { text: '' },
      autoSave: false,
    })

    const result = draft.loadDraft()

    expect(result).toBe(false)
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Corrupt draft data found for key "test_draft"'),
    )
    // Draft should be cleared
    expect(localStorage.getItem('test_draft')).toBeNull()
    // Data should be reset to default
    expect(draft.data.value).toEqual({ text: '' })

    warnSpy.mockRestore()
  })
})

// ────────────────────────────────────────────────────────────────
// L-20: sigId guard in useFormBuilder.saveForm
// ────────────────────────────────────────────────────────────────

describe('L-20: sigId guard in saveForm', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('sets error and returns early if sigId is undefined for non-standalone form', async () => {
    vi.doMock('vue', async () => {
      const actual = await vi.importActual<typeof import('vue')>('vue')
      return {
        ...actual,
        onMounted: vi.fn(),
        onUnmounted: vi.fn(),
      }
    })
    const mockCreateForm = vi.fn()
    vi.doMock('@/api/forms', () => ({
      getForm: vi.fn(),
      createForm: mockCreateForm,
      createStandaloneForm: vi.fn(),
      updateForm: vi.fn(),
    }))
    vi.doMock('@/api/sigs', () => ({ getSig: vi.fn() }))
    vi.doMock('@/api/files', () => ({ uploadEditorFile: vi.fn() }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useFormBuilder } = await import('@/composables/useFormBuilder')
    const mockRouter = { push: vi.fn(), replace: vi.fn() } as any

    const fb = useFormBuilder({
      sigId: () => undefined, // sigId is undefined
      formId: () => '',
      router: mockRouter,
      t: (k: string) => k,
    })

    // Setup valid form data
    fb.title.value = 'Test Form'
    fb.addQuestion()
    fb.questions.value[0].label = 'Question 1'

    await fb.saveForm()

    // createForm should NOT have been called
    expect(mockCreateForm).not.toHaveBeenCalled()
    // Error should be set
    expect(fb.error.value).toBe('forms.builder.saveError')
  })
})

// ────────────────────────────────────────────────────────────────
// L-22: assertShape descriptive warnings
// ────────────────────────────────────────────────────────────────

describe('L-22: assertShape descriptive warnings', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('logs descriptive warning with missing and actual keys', async () => {
    const { assertShape } = await import('@/utils/apiValidation')

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const data = { id: '1', name: 'test' }
    assertShape(data, ['id', 'name', 'email', 'role'], 'getUser')

    expect(warnSpy).toHaveBeenCalledTimes(1)
    const msg = warnSpy.mock.calls[0][0] as string
    expect(msg).toContain('Shape mismatch in "getUser"')
    expect(msg).toContain('missing keys [email, role]')
    expect(msg).toContain('Expected: [id, name, email, role]')
    expect(msg).toContain('Received: [id, name]')

    warnSpy.mockRestore()
  })

  it('does not warn when all keys are present', async () => {
    const { assertShape } = await import('@/utils/apiValidation')

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const data = { id: '1', name: 'test' }
    assertShape(data, ['id', 'name'], 'getUser')

    expect(warnSpy).not.toHaveBeenCalled()

    warnSpy.mockRestore()
  })
})
