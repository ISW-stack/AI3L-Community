import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/components/base/BaseCard.vue', () => ({
  default: {
    template: '<div class="base-card"><slot /></div>',
    props: ['hoverable'],
  },
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    template: '<button @click="$emit(\'click\')"><slot /></button>',
    emits: ['click'],
  },
}))

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import SearchPanel from '@/components/shared/SearchPanel.vue'
import CategoryFilter from '@/components/shared/CategoryFilter.vue'
import SortControls from '@/components/shared/SortControls.vue'
import TrendingSidebar from '@/components/shared/TrendingSidebar.vue'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const sampleCategories = [
  { id: 'cat-1', name: 'General', description: null, post_count: 5 },
  { id: 'cat-2', name: 'Tech', description: null, post_count: 3 },
]

const samplePosts = [
  {
    id: 'p1',
    title: 'Trending Post 1',
    content: '',
    author: { id: 'u1', username: 'user1', display_name: 'User 1', avatar_url: null },
    category_id: null,
    category_name: null,
    sig_id: null,
    sig_name: null,
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 10,
    is_pinned: false,
    view_count: 100,
    reactions: null,
    last_comment_at: null,
    type: 'post' as const,
    citation_count: 0,
    answer_count: 0,
    best_answer_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p2',
    title: 'Trending Post 2',
    content: '',
    author: { id: 'u2', username: 'user2', display_name: 'User 2', avatar_url: null },
    category_id: null,
    category_name: null,
    sig_id: null,
    sig_name: null,
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 5,
    is_pinned: false,
    view_count: 50,
    reactions: null,
    last_comment_at: null,
    type: 'post' as const,
    citation_count: 0,
    answer_count: 0,
    best_answer_id: null,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

const sortOptions = [
  { value: 'newest', label: 'Newest' },
  { value: 'popular', label: 'Popular' },
  { value: 'active', label: 'Active' },
]

// Stub for router-link
const routerLinkStub = {
  template: '<a :href="to"><slot /></a>',
  props: ['to'],
}

// ---------------------------------------------------------------------------
// SearchPanel
// ---------------------------------------------------------------------------

describe('SearchPanel', () => {
  function mountSearchPanel(propsOverrides = {}) {
    return mount(SearchPanel, {
      props: {
        keyword: '',
        dateFrom: '',
        dateTo: '',
        logic: 'AND',
        showAdvanced: false,
        isSearchLoading: false,
        isSearching: false,
        dateRangeInvalid: false,
        ...propsOverrides,
      },
    })
  }

  it('renders search input with placeholder', () => {
    const wrapper = mountSearchPanel({ placeholder: 'Search questions...' })
    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toBe('Search questions...')
  })

  it('emits update:keyword and search-input on input', async () => {
    const wrapper = mountSearchPanel()
    const input = wrapper.find('input[type="text"]')
    await input.setValue('test query')

    expect(wrapper.emitted('update:keyword')).toBeTruthy()
    expect(wrapper.emitted('update:keyword')![0]).toEqual(['test query'])
    expect(wrapper.emitted('search-input')).toBeTruthy()
  })

  it('emits immediate-search on enter', async () => {
    const wrapper = mountSearchPanel()
    const input = wrapper.find('input[type="text"]')
    await input.trigger('keyup.enter')

    expect(wrapper.emitted('immediate-search')).toBeTruthy()
  })

  it('emits toggle-advanced on toggle click', async () => {
    const wrapper = mountSearchPanel()
    // The toggle button is the last button-like element with the advanced text
    const toggleBtn = wrapper.findAll('button').find((b) => b.text().includes('common.advanced'))
    expect(toggleBtn).toBeTruthy()
    await toggleBtn!.trigger('click')

    expect(wrapper.emitted('toggle-advanced')).toBeTruthy()
  })

  it('shows date inputs when showAdvanced is true', () => {
    const wrapper = mountSearchPanel({ showAdvanced: true })
    const dateInputs = wrapper.findAll('input[type="date"]')
    expect(dateInputs.length).toBe(2)
  })
})

// ---------------------------------------------------------------------------
// CategoryFilter
// ---------------------------------------------------------------------------

describe('CategoryFilter', () => {
  describe('pills mode', () => {
    function mountPills(propsOverrides = {}) {
      return mount(CategoryFilter, {
        props: {
          categories: sampleCategories,
          activeCategory: null,
          mode: 'pills' as const,
          ...propsOverrides,
        },
      })
    }

    it('renders category buttons', () => {
      const wrapper = mountPills()
      const buttons = wrapper.findAll('button')
      // "All" button + one per category
      expect(buttons.length).toBe(1 + sampleCategories.length)
      expect(wrapper.text()).toContain('General')
      expect(wrapper.text()).toContain('Tech')
    })

    it('highlights active category', () => {
      const wrapper = mountPills({ activeCategory: 'cat-1' })
      const buttons = wrapper.findAll('button')
      // The "All" button should NOT have the active class
      expect(buttons[0].classes()).toContain('bg-surface-alt')
      // The first category button should have the active class
      expect(buttons[1].classes()).toContain('bg-brand-600')
    })

    it('emits select with category id on click', async () => {
      const wrapper = mountPills()
      const buttons = wrapper.findAll('button')
      // Click the first category button (index 1, after "All")
      await buttons[1].trigger('click')
      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')![0]).toEqual(['cat-1'])
    })

    it('emits select with null when "All" clicked', async () => {
      const wrapper = mountPills({ activeCategory: 'cat-1' })
      const allButton = wrapper.findAll('button')[0]
      await allButton.trigger('click')
      expect(wrapper.emitted('select')![0]).toEqual([null])
    })
  })

  describe('list mode', () => {
    function mountList(propsOverrides = {}) {
      return mount(CategoryFilter, {
        props: {
          categories: sampleCategories,
          activeCategory: null,
          mode: 'list' as const,
          ...propsOverrides,
        },
      })
    }

    it('renders category list items', () => {
      const wrapper = mountList()
      const listItems = wrapper.findAll('li')
      // "All" item + one per category
      expect(listItems.length).toBe(1 + sampleCategories.length)
      expect(wrapper.text()).toContain('General')
      expect(wrapper.text()).toContain('Tech')
    })

    it('highlights active category in list mode', () => {
      const wrapper = mountList({ activeCategory: 'cat-2' })
      const buttons = wrapper.findAll('button')
      // "All" button (index 0) — not active
      expect(buttons[0].classes()).toContain('text-foreground')
      // cat-1 (index 1) — not active
      expect(buttons[1].classes()).toContain('text-foreground')
      // cat-2 (index 2) — active
      expect(buttons[2].classes()).toContain('bg-brand-50')
    })
  })
})

// ---------------------------------------------------------------------------
// SortControls
// ---------------------------------------------------------------------------

describe('SortControls', () => {
  function mountSort(propsOverrides = {}) {
    return mount(SortControls, {
      props: {
        currentSort: 'newest',
        options: sortOptions,
        ...propsOverrides,
      },
    })
  }

  it('renders all options', () => {
    const wrapper = mountSort()
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(sortOptions.length)
    expect(wrapper.text()).toContain('Newest')
    expect(wrapper.text()).toContain('Popular')
    expect(wrapper.text()).toContain('Active')
  })

  it('highlights current sort', () => {
    const wrapper = mountSort({ currentSort: 'popular' })
    const buttons = wrapper.findAll('button')
    // "newest" is index 0 — should NOT be active
    expect(buttons[0].classes()).toContain('bg-surface')
    // "popular" is index 1 — should be active
    expect(buttons[1].classes()).toContain('bg-brand-600')
  })

  it('emits select on click', async () => {
    const wrapper = mountSort()
    const buttons = wrapper.findAll('button')
    // Click "popular" (index 1)
    await buttons[1].trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual(['popular'])
  })
})

// ---------------------------------------------------------------------------
// TrendingSidebar
// ---------------------------------------------------------------------------

describe('TrendingSidebar', () => {
  function mountTrending(propsOverrides = {}) {
    return mount(TrendingSidebar, {
      props: {
        posts: samplePosts,
        ...propsOverrides,
      },
      global: {
        stubs: {
          'router-link': routerLinkStub,
        },
      },
    })
  }

  it('renders posts when posts array is not empty', () => {
    const wrapper = mountTrending()
    expect(wrapper.find('.base-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('Trending Post 1')
    expect(wrapper.text()).toContain('Trending Post 2')
    const listItems = wrapper.findAll('li')
    expect(listItems.length).toBe(2)
  })

  it('hides when posts array is empty', () => {
    const wrapper = mountTrending({ posts: [] })
    // BaseCard has v-if="posts.length > 0" — should not render
    expect(wrapper.find('.base-card').exists()).toBe(false)
  })

  it('uses scoped slot for custom rendering', () => {
    const wrapper = mount(TrendingSidebar, {
      props: { posts: samplePosts },
      global: {
        stubs: {
          'router-link': routerLinkStub,
        },
      },
      slots: {
        item: `<template #item="{ post }">
          <div class="custom-item">{{ post.title }}</div>
        </template>`,
      },
    })
    const customItems = wrapper.findAll('.custom-item')
    expect(customItems.length).toBe(2)
    expect(customItems[0].text()).toBe('Trending Post 1')
    expect(customItems[1].text()).toBe('Trending Post 2')
  })
})
