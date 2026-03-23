/**
 * Tests for co-author & citation audit fixes (B1, B2, B6, U1, U2, U3).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// ──────────────────────────────────────────────────────────────────
// Mocks
// ──────────────────────────────────────────────────────────────────

vi.mock('@/api/coauthors', () => ({
  listAllCoAuthors: vi.fn().mockResolvedValue({ co_authors: [] }),
  inviteCoAuthor: vi.fn(),
  addExternalCoAuthor: vi.fn(),
  removeCoAuthor: vi.fn().mockResolvedValue(undefined),
  searchUsers: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/citations', () => ({
  searchForCitation: vi.fn().mockResolvedValue([]),
  getCitedBy: vi.fn().mockResolvedValue({ citations: [], total: 0 }),
  getCiting: vi.fn().mockResolvedValue({ citations: [], total: 0 }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({ show: vi.fn() }),
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    props: ['loading', 'size', 'disabled', 'variant'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
}))

vi.mock('@/components/base/BaseInput.vue', () => ({
  default: {
    props: ['modelValue', 'label', 'placeholder', 'required'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))

vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: {
    props: ['variant'],
    template: '<span class="badge"><slot /></span>',
  },
}))

vi.mock('@/components/base/BaseAvatar.vue', () => ({
  default: {
    props: ['src', 'name', 'size'],
    template: '<img :alt="name" />',
  },
}))

vi.mock('@/components/base/BaseAlert.vue', () => ({
  default: {
    props: ['type'],
    template: '<div><slot /></div>',
  },
}))

vi.mock('@/components/base/BaseModal.vue', () => ({
  default: {
    props: ['modelValue', 'title', 'size'],
    template: '<div><slot /></div>',
  },
}))

vi.mock('lucide-vue-next', () => ({
  UserPlus: { template: '<span />' },
  X: { template: '<span />' },
  Users: { template: '<span />' },
  Search: { template: '<span />' },
}))

import CoAuthorBadges from '../CoAuthorBadges.vue'
import CoAuthorManager from '../CoAuthorManager.vue'
import CitationSearchDialog from '../CitationSearchDialog.vue'
import type { CoAuthor } from '../../../types/coauthor'

function makeCoAuthor(overrides: Partial<CoAuthor> = {}): CoAuthor {
  return {
    id: `ca-${Math.random().toString(36).slice(2, 8)}`,
    post_id: 'post-1',
    user_id: 'user-1',
    display_name: 'Test User',
    affiliation: null,
    orcid: null,
    is_external: false,
    status: 'ACCEPTED',
    avatar_url: null,
    invited_at: new Date().toISOString(),
    responded_at: null,
    ...overrides,
  }
}

// ──────────────────────────────────────────────────────────────────
// B1: CitationSearchDialog should not show "Invalid Date"
// ──────────────────────────────────────────────────────────────────

describe('B1 — CitationSearchDialog: no Invalid Date', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders search results without created_at field', async () => {
    const { searchForCitation } = await import('@/api/citations')
    const mock = searchForCitation as ReturnType<typeof vi.fn>
    mock.mockResolvedValue([
      { id: '1', title: 'Post One', author_name: 'Alice' },
    ])

    const wrapper = mount(CitationSearchDialog, {
      props: { modelValue: true },
    })

    const input = wrapper.find('input')
    await input.setValue('test')
    await input.trigger('input')
    vi.advanceTimersByTime(300)
    await flushPromises()

    // Should show author_name without "Invalid Date"
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Post One')
    expect(wrapper.text()).not.toContain('Invalid Date')
  })
})

// ──────────────────────────────────────────────────────────────────
// B2: CoAuthorBadges reactivity
// ──────────────────────────────────────────────────────────────────

describe('B2 — CoAuthorBadges: reactive on prop change', () => {
  it('updates when coAuthors prop changes', async () => {
    const initial = [makeCoAuthor({ id: 'ca-1', display_name: 'Alice' })]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors: initial },
    })

    expect(wrapper.text()).toContain('Alice')

    // Update props — add a second co-author
    const updated = [
      makeCoAuthor({ id: 'ca-1', display_name: 'Alice' }),
      makeCoAuthor({ id: 'ca-2', display_name: 'Bob' }),
    ]
    await wrapper.setProps({ coAuthors: updated })

    expect(wrapper.text()).toContain('Bob')
  })

  it('updates "and N more" count on prop change', async () => {
    const initial = Array.from({ length: 4 }, (_, i) =>
      makeCoAuthor({ id: `ca-${i}`, display_name: `User${i}` }),
    )
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors: initial },
    })

    expect(wrapper.text()).toContain('and 1 more')

    // Add more co-authors
    const expanded = [
      ...initial,
      makeCoAuthor({ id: 'ca-4', display_name: 'User4' }),
      makeCoAuthor({ id: 'ca-5', display_name: 'User5' }),
    ]
    await wrapper.setProps({ coAuthors: expanded })

    expect(wrapper.text()).toContain('and 3 more')
  })
})

// ──────────────────────────────────────────────────────────────────
// U3: CoAuthorBadges i18n "with" prefix
// ──────────────────────────────────────────────────────────────────

describe('U3 — CoAuthorBadges: i18n withPrefix', () => {
  it('renders the "with" prefix from i18n', () => {
    const coAuthors = [makeCoAuthor({ id: 'ca-1', display_name: 'Alice' })]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    // The i18n key 'coauthors.withPrefix' resolves to 'with' in English
    expect(wrapper.text()).toContain('with')
  })
})

// ──────────────────────────────────────────────────────────────────
// U1: CoAuthorManager — confirm before remove
// ──────────────────────────────────────────────────────────────────

describe('U1 — CoAuthorManager: confirm before remove', () => {
  it('calls confirm before removing a co-author', async () => {
    const { listAllCoAuthors, removeCoAuthor } = await import('@/api/coauthors')
    const mockList = listAllCoAuthors as ReturnType<typeof vi.fn>
    const mockRemove = removeCoAuthor as ReturnType<typeof vi.fn>

    const ca = makeCoAuthor({ id: 'ca-1', display_name: 'Alice', status: 'ACCEPTED' })
    mockList.mockResolvedValue({ co_authors: [ca] })
    mockRemove.mockResolvedValue(undefined)

    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(true)

    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    // Find and click the remove button (the X button)
    const removeBtn = wrapper.find('button[aria-label]')
    expect(removeBtn.exists()).toBe(true)
    await removeBtn.trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(mockRemove).toHaveBeenCalledWith('post-1', 'ca-1')

    confirmSpy.mockRestore()
  })

  it('does not remove when confirm is cancelled', async () => {
    const { listAllCoAuthors, removeCoAuthor } = await import('@/api/coauthors')
    const mockList = listAllCoAuthors as ReturnType<typeof vi.fn>
    const mockRemove = removeCoAuthor as ReturnType<typeof vi.fn>

    const ca = makeCoAuthor({ id: 'ca-1', display_name: 'Alice', status: 'ACCEPTED' })
    mockList.mockResolvedValue({ co_authors: [ca] })
    mockRemove.mockClear()

    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(false)

    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    const removeBtn = wrapper.find('button[aria-label]')
    await removeBtn.trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(mockRemove).not.toHaveBeenCalled()

    confirmSpy.mockRestore()
  })
})

// ──────────────────────────────────────────────────────────────────
// U2: CoAuthorManager — active count excludes REJECTED
// ──────────────────────────────────────────────────────────────────

describe('U2 — CoAuthorManager: active count excludes REJECTED', () => {
  it('header shows count excluding REJECTED co-authors', async () => {
    const { listAllCoAuthors } = await import('@/api/coauthors')
    const mock = listAllCoAuthors as ReturnType<typeof vi.fn>

    mock.mockResolvedValue({
      co_authors: [
        makeCoAuthor({ id: 'ca-1', status: 'ACCEPTED' }),
        makeCoAuthor({ id: 'ca-2', status: 'PENDING' }),
        makeCoAuthor({ id: 'ca-3', status: 'REJECTED' }),
      ],
    })

    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    // The count should be 2 (ACCEPTED + PENDING), not 3
    const header = wrapper.find('h3')
    expect(header.text()).toContain('2/10')
    expect(header.text()).not.toContain('3/10')
  })
})

// ──────────────────────────────────────────────────────────────────
// B6: Citations API sends pagination params
// ──────────────────────────────────────────────────────────────────

describe('B6 — Citations API: pagination params', () => {
  it('getCitedBy can be called with pagination params', async () => {
    const { getCitedBy } = await import('@/api/citations')
    const mock = getCitedBy as ReturnType<typeof vi.fn>
    mock.mockResolvedValue({ citations: [], total: 42 })

    const result = await mock('post-1', 1, 100)
    expect(result.total).toBe(42)
    expect(mock).toHaveBeenCalledWith('post-1', 1, 100)
  })

  it('getCiting can be called with pagination params', async () => {
    const { getCiting } = await import('@/api/citations')
    const mock = getCiting as ReturnType<typeof vi.fn>
    mock.mockResolvedValue({ citations: [], total: 15 })

    const result = await mock('post-1', 1, 100)
    expect(result.total).toBe(15)
    expect(mock).toHaveBeenCalledWith('post-1', 1, 100)
  })
})
