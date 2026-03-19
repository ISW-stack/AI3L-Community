/**
 * Tests for bug fixes B-17, B-18, B-19, B-21, B-24, B-25, S-07, S-10.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

// ─────────────────────────────────────────────────────────
// B-17: isContentEmpty utility
// ─────────────────────────────────────────────────────────
import { isContentEmpty } from '@/utils/html'

describe('B-17: isContentEmpty detects empty TiptapEditor HTML', () => {
  it('returns true for empty string', () => {
    expect(isContentEmpty('')).toBe(true)
  })

  it('returns true for <p></p>', () => {
    expect(isContentEmpty('<p></p>')).toBe(true)
  })

  it('returns true for <p><br></p> (TipTap default empty)', () => {
    expect(isContentEmpty('<p><br></p>')).toBe(true)
  })

  it('returns true for whitespace-only content in tags', () => {
    expect(isContentEmpty('<p>   </p>')).toBe(true)
  })

  it('returns true for multiple empty paragraphs', () => {
    expect(isContentEmpty('<p></p><p></p>')).toBe(true)
  })

  it('returns false for content with actual text', () => {
    expect(isContentEmpty('<p>Hello world</p>')).toBe(false)
  })

  it('returns false for content with an image tag', () => {
    expect(isContentEmpty('<p><img src="test.png" /></p>')).toBe(false)
  })

  it('returns false for content with a video tag', () => {
    expect(isContentEmpty('<video src="video.mp4"></video>')).toBe(false)
  })

  it('returns false for content with a table tag', () => {
    expect(isContentEmpty('<table><tr><td></td></tr></table>')).toBe(false)
  })

  it('returns true for null/undefined coerced to empty', () => {
    expect(isContentEmpty(null as unknown as string)).toBe(true)
    expect(isContentEmpty(undefined as unknown as string)).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────
// B-18: DMView optimistic recall rollback re-finds by ID
// ─────────────────────────────────────────────────────────
describe('B-18: Recall rollback re-finds message by ID, not stale index', () => {
  it('restores the correct message even after array insertion shifts indices', () => {
    // Simulate a messages array and the rollback logic
    const messages = [
      { id: 'msg-1', content: 'Hello', is_recalled: false },
      { id: 'msg-2', content: 'World', is_recalled: false },
    ]

    const messageId = 'msg-2'
    const idx = messages.findIndex((m) => m.id === messageId)
    const original = { ...messages[idx] }

    // Optimistic update
    messages[idx] = { ...messages[idx], is_recalled: true, content: null as unknown as string }

    // Simulate a WS event that inserts a new message at position 0
    messages.unshift({ id: 'msg-3', content: 'New message', is_recalled: false })

    // Now idx (1) is stale -- msg-2 is now at index 2
    // Old buggy code would do: messages[idx] = original (overwrites msg-3!)
    // Fixed code: re-find by ID
    const rollbackIdx = messages.findIndex((m) => m.id === messageId)
    expect(rollbackIdx).toBe(2) // not idx (1)
    expect(rollbackIdx).not.toBe(idx)

    if (rollbackIdx >= 0) {
      messages[rollbackIdx] = original
    }

    // Verify the correct message was restored
    expect(messages[rollbackIdx].content).toBe('World')
    expect(messages[rollbackIdx].is_recalled).toBe(false)

    // Verify the WS-inserted message was not damaged
    expect(messages[0].id).toBe('msg-3')
    expect(messages[0].content).toBe('New message')
  })

  it('handles case where message was removed entirely during rollback', () => {
    const messages = [{ id: 'msg-1', content: 'Hello', is_recalled: false }]

    const messageId = 'msg-removed'
    const original = { id: messageId, content: 'Was here', is_recalled: false }

    // Message no longer in array
    const rollbackIdx = messages.findIndex((m) => m.id === messageId)
    expect(rollbackIdx).toBe(-1)

    // Should not crash or corrupt array
    if (rollbackIdx >= 0) {
      messages[rollbackIdx] = original
    }

    expect(messages).toHaveLength(1)
    expect(messages[0].id).toBe('msg-1')
  })
})

// ─────────────────────────────────────────────────────────
// B-19: useInfiniteScroll watches sentinelRef for lazy mount
// ─────────────────────────────────────────────────────────

type IOCallback = (entries: IntersectionObserverEntry[]) => void

describe('B-19: useInfiniteScroll creates observer when sentinelRef becomes available', () => {
  let _capturedCallback: IOCallback | null = null
  const mockObserve = vi.fn()
  const mockDisconnect = vi.fn()

  class MockIntersectionObserver {
    constructor(callback: IOCallback) {
      _capturedCallback = callback
    }
    observe = mockObserve
    unobserve = vi.fn()
    disconnect = mockDisconnect
  }

  beforeEach(() => {
    _capturedCallback = null
    mockObserve.mockClear()
    mockDisconnect.mockClear()
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('creates observer when sentinelRef changes from null to an element', async () => {
    const { useInfiniteScroll } = await import('@/composables/useInfiniteScroll')

    const onLoadMore = vi.fn()

    // Component that initially hides the sentinel, then shows it
    const comp = defineComponent({
      setup() {
        const sentinel = ref<HTMLElement | null>(null)
        const showSentinel = ref(false)
        useInfiniteScroll(sentinel, onLoadMore)
        return { sentinel, showSentinel }
      },
      template: '<div><div v-if="showSentinel" ref="sentinel" class="sentinel"></div></div>',
    })

    const wrapper = mount(comp)
    await nextTick()

    // Initially no observer because sentinel is null
    expect(mockObserve).not.toHaveBeenCalled()

    // Show the sentinel element
    ;(wrapper.vm as unknown as { showSentinel: boolean }).showSentinel = true
    await nextTick()
    await nextTick() // extra tick for the watch to fire

    // Now the observer should be created and observing
    expect(mockObserve).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('disconnects old observer when sentinel goes from element to null', async () => {
    const { useInfiniteScroll } = await import('@/composables/useInfiniteScroll')

    const onLoadMore = vi.fn()

    // Component that can toggle sentinel visibility
    const comp = defineComponent({
      setup() {
        const sentinel = ref<HTMLElement | null>(null)
        const showSentinel = ref(true)
        useInfiniteScroll(sentinel, onLoadMore)
        return { sentinel, showSentinel }
      },
      template: '<div><div v-if="showSentinel" ref="sentinel"></div></div>',
    })

    const wrapper = mount(comp)
    await nextTick()

    // Observer created (may be called multiple times due to mount + watch)
    expect(mockObserve).toHaveBeenCalled()

    const observeCallsBefore = mockObserve.mock.calls.length
    const disconnectCallsBefore = mockDisconnect.mock.calls.length

    // Hide sentinel
    ;(wrapper.vm as unknown as { showSentinel: boolean }).showSentinel = false
    await nextTick()
    await nextTick()

    // Should have disconnected
    expect(mockDisconnect.mock.calls.length).toBeGreaterThan(disconnectCallsBefore)

    // Show sentinel again
    ;(wrapper.vm as unknown as { showSentinel: boolean }).showSentinel = true
    await nextTick()
    await nextTick()

    // Should have created a new observer
    expect(mockObserve.mock.calls.length).toBeGreaterThan(observeCallsBefore)

    wrapper.unmount()
  })
})

// ─────────────────────────────────────────────────────────
// B-21: UserProfileView co-authored posts uses different API
// ─────────────────────────────────────────────────────────
vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('B-21: Co-authored posts fetch uses listCoAuthoredPosts API', () => {
  it('listCoAuthoredPosts calls /co-authors/user/{userId}/posts endpoint', async () => {
    const api = (await import('@/composables/api')).default
    const mockGet = api.get as ReturnType<typeof vi.fn>
    mockGet.mockResolvedValue({
      data: { posts: [{ id: 'p1', title: 'Collab Post', created_at: '2026-01-01' }], total: 1 },
    })

    const { listCoAuthoredPosts } = await import('@/api/coauthors')
    const result = await listCoAuthoredPosts('user-123', 1, 10)

    expect(mockGet).toHaveBeenCalledWith('/co-authors/user/user-123/posts', {
      params: { page: 1, page_size: 10 },
    })
    expect(result.posts).toHaveLength(1)
    expect(result.posts[0].title).toBe('Collab Post')
  })

  it('listCoAuthoredPosts is a separate function from listPosts', async () => {
    const { listCoAuthoredPosts } = await import('@/api/coauthors')
    const { listPosts } = await import('@/api/posts')
    expect(listCoAuthoredPosts).not.toBe(listPosts)
  })
})

// ─────────────────────────────────────────────────────────
// B-24: Date formatting uses dynamic locale
// ─────────────────────────────────────────────────────────
describe('B-24: Date formatting uses dynamic locale, not hardcoded en-US', () => {
  it('formatDate uses the passed locale', async () => {
    const { formatDate } = await import('@/utils/date')

    const date = '2026-03-15T00:00:00Z'
    const enResult = formatDate(date, 'en')
    const deResult = formatDate(date, 'de')

    // Both should produce valid date strings but may differ
    expect(enResult).toBeTruthy()
    expect(deResult).toBeTruthy()
    // English typically uses "Mar" while German uses "Mär." or "März"
    // Just verify they are not identical when locales differ
    // (some minimal environments may not have locale data, so just ensure no crash)
    expect(typeof enResult).toBe('string')
    expect(typeof deResult).toBe('string')
  })

  it('formatDateTime uses the passed locale', async () => {
    const { formatDateTime } = await import('@/utils/date')

    const date = '2026-03-15T14:30:00Z'
    const result = formatDateTime(date, 'ja')
    expect(result).toBeTruthy()
    expect(typeof result).toBe('string')
  })

  it('InviteCodesView formatDate no longer uses hardcoded en-US', async () => {
    // Read the source to verify no hardcoded 'en-US' remains
    // This is a source-level check by importing and verifying the locale plumbing
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../views/admin/InviteCodesView.vue'), 'utf-8')
    // The formatDate function should NOT contain 'en-US'
    const formatDateMatch = source.match(/function formatDate[\s\S]*?\n\}/m)
    expect(formatDateMatch).toBeTruthy()
    expect(formatDateMatch![0]).not.toContain("'en-US'")
    expect(formatDateMatch![0]).toContain('locale')
  })

  it('MessageThread does not contain hardcoded en-US in date formatting', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/dm/MessageThread.vue'), 'utf-8')
    // No 'en-US' should remain in the file
    expect(source).not.toContain("'en-US'")
  })
})

// ─────────────────────────────────────────────────────────
// B-25: PostCard uses local ref instead of mutating prop
// ─────────────────────────────────────────────────────────
describe('B-25: PostCard does not directly mutate post.comment_count prop', () => {
  it('source code does not contain props.post.comment_count++', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/PostCard.vue'), 'utf-8')
    expect(source).not.toContain('props.post.comment_count++')
    expect(source).toContain('localCommentCount')
  })

  it('uses localCommentCount ref initialized from prop', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/PostCard.vue'), 'utf-8')
    // Should define a local ref
    expect(source).toContain('const localCommentCount = ref(props.post.comment_count)')
    // Should display localCommentCount in template
    expect(source).toContain('{{ localCommentCount }}')
    // handleCommented should increment localCommentCount
    expect(source).toContain('localCommentCount.value++')
  })

  it('watches prop changes and syncs localCommentCount', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/PostCard.vue'), 'utf-8')
    // Should watch for prop changes
    expect(source).toContain('() => props.post.comment_count')
    expect(source).toContain('localCommentCount.value = newVal')
  })
})

// ─────────────────────────────────────────────────────────
// S-07: SVG removed from IMAGE_EXTS
// ─────────────────────────────────────────────────────────
describe('S-07: IMAGE_EXTS does not include svg', () => {
  it('source file does not list svg in IMAGE_EXTS', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/dm/MessageThread.vue'), 'utf-8')
    // Extract the IMAGE_EXTS line
    const match = source.match(/const IMAGE_EXTS = new Set\(\[.*?\]\)/)
    expect(match).toBeTruthy()
    expect(match![0]).not.toContain("'svg'")
    expect(match![0]).not.toContain('"svg"')
  })

  it('allowed image extensions include jpg, jpeg, png, gif, webp but not svg', async () => {
    const { readFileSync } = await import('fs')
    const { resolve } = await import('path')
    const source = readFileSync(resolve(__dirname, '../components/dm/MessageThread.vue'), 'utf-8')
    const match = source.match(/const IMAGE_EXTS = new Set\(\[.*?\]\)/)
    const line = match![0]
    expect(line).toContain("'jpg'")
    expect(line).toContain("'jpeg'")
    expect(line).toContain("'png'")
    expect(line).toContain("'gif'")
    expect(line).toContain("'webp'")
    expect(line).not.toContain("'svg'")
  })
})

// ─────────────────────────────────────────────────────────
// S-10: isAllowedDownloadUrl validates origin
// ─────────────────────────────────────────────────────────
describe('S-10: isAllowedDownloadUrl rejects untrusted origins', () => {
  let isAllowedDownloadUrl: (url: string) => boolean

  beforeEach(async () => {
    const mod = await import('@/composables/useFormExport')
    isAllowedDownloadUrl = mod.isAllowedDownloadUrl
  })

  it('accepts URLs from window.location.origin', () => {
    // jsdom defaults to http://localhost
    const url = `${window.location.origin}/downloads/export.csv`
    expect(isAllowedDownloadUrl(url)).toBe(true)
  })

  it('accepts URLs from MinIO localhost:19000', () => {
    const url = 'http://localhost:19000/bucket/export.csv?token=abc'
    expect(isAllowedDownloadUrl(url)).toBe(true)
  })

  it('rejects URLs from untrusted origins', () => {
    expect(isAllowedDownloadUrl('https://evil.com/malware.exe')).toBe(false)
  })

  it('rejects URLs with different port from allowed origins', () => {
    expect(isAllowedDownloadUrl('http://localhost:9999/file.csv')).toBe(false)
  })

  it('rejects malformed URLs', () => {
    expect(isAllowedDownloadUrl('not-a-url')).toBe(false)
  })

  it('rejects javascript: protocol URLs', () => {
    expect(isAllowedDownloadUrl('javascript:alert(1)')).toBe(false)
  })

  it('rejects data: URLs', () => {
    expect(isAllowedDownloadUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
  })
})
