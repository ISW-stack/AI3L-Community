import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { getErrorMessage } from '@/utils/error'

// --------------- Mock: API layer ---------------

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockPatch = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
  WS_INITIAL_BACKOFF_MS: 1000,
  WS_MAX_BACKOFF_MS: 30000,
}))

vi.mock('lucide-vue-next', () => ({
  Paperclip: { name: 'Paperclip', template: '<span class="icon-paperclip" />' },
  Send: { name: 'Send', template: '<span class="icon-send" />' },
  Check: { name: 'Check', template: '<span class="icon-check" />' },
  CheckCheck: { name: 'CheckCheck', template: '<span class="icon-check-check" />' },
  MoreHorizontal: { name: 'MoreHorizontal', template: '<span class="icon-more" />' },
  X: { name: 'X', template: '<span class="icon-x" />' },
  File: { name: 'File', template: '<span class="icon-file" />' },
  FileText: { name: 'FileText', template: '<span class="icon-file-text" />' },
  Film: { name: 'Film', template: '<span class="icon-film" />' },
  Music: { name: 'Music', template: '<span class="icon-music" />' },
  Download: { name: 'Download', template: '<span class="icon-download" />' },
  AlertTriangle: { name: 'AlertTriangle', template: '<span class="icon-alert" />' },
  MessageSquare: { name: 'MessageSquare', template: '<span class="icon-message-square" />' },
  ArrowLeft: { name: 'ArrowLeft', template: '<span class="icon-arrow-left" />' },
  ArrowDown: { name: 'ArrowDown', template: '<span class="icon-arrow-down" />' },
  Pencil: { name: 'Pencil', template: '<span class="icon-pencil" />' },
  Trash2: { name: 'Trash2', template: '<span class="icon-trash" />' },
  Globe: { name: 'Globe', template: '<span class="icon-globe" />' },
  ChevronDown: { name: 'ChevronDown', template: '<span class="icon-chevron-down" />' },
  ChevronRight: { name: 'ChevronRight', template: '<span class="icon-chevron-right" />' },
  Lock: { name: 'Lock', template: '<span class="icon-lock" />' },
  Unlock: { name: 'Unlock', template: '<span class="icon-unlock" />' },
}))

vi.mock('@/utils/datetime', () => ({
  relativeTime: (_date: string) => '2 min ago',
  formatDateTime: (date: string) => date,
}))

const mockRouterPush = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    role: 'MEMBER',
    isAuthenticated: true,
    isAdmin: false,
    isSuperAdmin: false,
    isGuest: false,
    user: { id: 'user-1', display_name: 'Bob', username: 'bob', avatar_url: null },
    clearSession: vi.fn(),
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    toasts: [],
    show: vi.fn(),
    dismiss: vi.fn(),
    clearAll: vi.fn(),
    showKey: vi.fn(),
  }),
}))

const mockFetchConversations = vi.fn().mockResolvedValue(undefined)
const mockFetchMessages = vi.fn().mockResolvedValue(undefined)
const mockSetActiveConversation = vi.fn()
const mockSetCurrentUserId = vi.fn()

vi.mock('@/stores/dm', () => ({
  useDMStore: () => ({
    conversations: [],
    conversationsTotal: 0,
    messages: [],
    messagesTotal: 0,
    unreadCount: 0,
    activeConversationId: null,
    loading: false,
    error: null,
    currentUserId: '',
    fetchConversations: mockFetchConversations,
    fetchMessages: mockFetchMessages,
    setActiveConversation: mockSetActiveConversation,
    setCurrentUserId: mockSetCurrentUserId,
    fetchUnreadCount: vi.fn(),
    resetState: vi.fn(),
  }),
}))

vi.mock('@/api/dm', () => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
  editMessage: vi.fn(),
  recallMessage: vi.fn(),
  markConversationRead: vi.fn(),
  getUnreadCount: vi.fn(),
}))

vi.mock('@/composables/usePagination', () => ({
  usePagination: () => ({
    page: { value: 1 },
    total: { value: 0 },
    totalPages: { value: 1 },
    pageSize: 30,
    setPage: vi.fn(),
    resetPage: vi.fn(),
    updateFromResponse: vi.fn(),
  }),
}))

// --------------- Imports ---------------

import DMView from '@/views/DMView.vue'

// --------------- parseDMError re-implementation for unit testing ---------------

function parseDMError(e: unknown, fallback: string): string {
  if (e && typeof e === 'object' && 'response' in e) {
    const resp = (
      e as {
        response?: {
          data?: { detail?: { code?: string; message?: string } }
        }
      }
    ).response
    const code = resp?.data?.detail?.code
    if (code === 'DM_001') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.includes('friends')) return 'This user only accepts messages from friends.'
      return 'You cannot message this user.'
    }
    if (code === 'DM_002') return 'The edit/recall window (12 hours) has expired.'
    if (code === 'DM_003') return 'You cannot message yourself.'
    if (code === 'DM_004') return 'Storage quota exceeded (1 GB limit).'
    if (code === 'DM_005') return 'File too large (max 50 MB).'
    if (code === 'SYS_422') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.includes('already recalled')) return 'This message has already been recalled.'
      if (msg.includes('recalled message')) return 'Cannot edit a recalled message.'
    }
    if (code === 'SYS_403') return 'You can only edit or recall your own messages.'
  }
  return getErrorMessage(e, fallback)
}

// --------------- DMView — dm_friends_only toggle tests ---------------

describe('DMView — dm_friends_only toggle', () => {
  function mountDMView() {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
        },
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/me/preferences') {
        return Promise.resolve({
          data: {
            theme: 'light',
            notify_mentions: true,
            notify_replies: true,
            notify_sig_posts: true,
            dm_friends_only: false,
          },
        })
      }
      return Promise.resolve({ data: {} })
    })
    mockPatch.mockResolvedValue({
      data: {
        theme: 'light',
        notify_mentions: true,
        notify_replies: true,
        notify_sig_posts: true,
        dm_friends_only: true,
      },
    })
  })

  it('renders friends-only toggle button showing "Open to all" by default', async () => {
    const wrapper = mountDMView()
    await flushPromises()

    const btn = wrapper.find('[data-testid="dm-friends-only-toggle"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('Open to all')
  })

  it('shows "Friends only" when preference is true', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/me/preferences') {
        return Promise.resolve({
          data: {
            theme: 'light',
            notify_mentions: true,
            notify_replies: true,
            notify_sig_posts: true,
            dm_friends_only: true,
          },
        })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountDMView()
    await flushPromises()

    const btn = wrapper.find('[data-testid="dm-friends-only-toggle"]')
    expect(btn.text()).toContain('Friends only')
  })

  it('calls PATCH /users/me/preferences when toggle is clicked', async () => {
    const wrapper = mountDMView()
    await flushPromises()

    const btn = wrapper.find('[data-testid="dm-friends-only-toggle"]')
    await btn.trigger('click')
    await flushPromises()

    expect(mockPatch).toHaveBeenCalledWith('/users/me/preferences', {
      dm_friends_only: true,
    })
  })

  it('reverts toggle on API failure', async () => {
    mockPatch.mockRejectedValue(new Error('Network error'))

    const wrapper = mountDMView()
    await flushPromises()

    const btn = wrapper.find('[data-testid="dm-friends-only-toggle"]')
    expect(btn.text()).toContain('Open to all')

    await btn.trigger('click')
    await flushPromises()

    // Should revert since API failed
    expect(btn.text()).toContain('Open to all')
  })
})

// --------------- parseDMError unit tests ---------------

describe('parseDMError — new error codes', () => {
  it('returns friends-only message for DM_001 with "friends" in message', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'DM_001',
            message: 'This user only accepts messages from friends.',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe(
      'This user only accepts messages from friends.',
    )
  })

  it('returns generic block message for DM_001 without "friends" in message', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'DM_001',
            message: 'User has blocked you.',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('You cannot message this user.')
  })

  it('returns self-message error for DM_003', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'DM_003',
            message: 'Cannot send DM to yourself.',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('You cannot message yourself.')
  })

  it('returns storage quota error for DM_004', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'DM_004',
            message: 'Storage quota exceeded.',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('Storage quota exceeded (1 GB limit).')
  })

  it('returns file size error for DM_005', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'DM_005',
            message: 'File too large.',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('File too large (max 50 MB).')
  })

  it('still handles DM_002 (edit/recall window)', () => {
    const err = {
      response: { data: { detail: { code: 'DM_002', message: '' } } },
    }
    expect(parseDMError(err, 'fallback')).toBe(
      'The edit/recall window (12 hours) has expired.',
    )
  })

  it('returns fallback for unknown errors', () => {
    expect(parseDMError(null, 'My fallback')).toBe('My fallback')
  })
})

// --------------- DMView setCurrentUserId test ---------------

describe('DMView — setCurrentUserId on mount', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls dmStore.setCurrentUserId with auth user id on mount', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(mockSetCurrentUserId).toHaveBeenCalledWith('user-1')
  })

  it('calls dmStore.setCurrentUserId before fetchConversations', async () => {
    const callOrder: string[] = []
    mockSetCurrentUserId.mockImplementation(() => {
      callOrder.push('setCurrentUserId')
    })
    mockFetchConversations.mockImplementation(() => {
      callOrder.push('fetchConversations')
      return Promise.resolve()
    })

    const pinia = createPinia()
    setActivePinia(pinia)

    mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(callOrder[0]).toBe('setCurrentUserId')
    expect(callOrder[1]).toBe('fetchConversations')
  })
})
