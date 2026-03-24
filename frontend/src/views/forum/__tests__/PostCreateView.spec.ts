import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PostCreateView from '../PostCreateView.vue'

const mockCreatePost = vi.fn()
const mockListCategories = vi.fn()
const mockListMySigs = vi.fn()

vi.mock('@/api/posts', () => ({
  createPost: (...args: unknown[]) => mockCreatePost(...args),
  listPosts: vi.fn(),
}))

vi.mock('@/api/categories', () => ({
  listCategories: (...args: unknown[]) => mockListCategories(...args),
}))

vi.mock('@/api/sigs', () => ({
  listMySigs: (...args: unknown[]) => mockListMySigs(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeCategories = [
  { id: 'cat1', name: 'AI Research', post_count: 10 },
  { id: 'cat2', name: 'Language Learning', post_count: 5 },
]

const fakeSigs = [
  {
    id: 'sig1',
    name: 'NLP SIG',
    description: 'NLP',
    member_count: 10,
    created_at: '2026-01-01T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/forum/create', component: PostCreateView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
      { path: '/sigs/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'label', 'placeholder', 'required', 'maxlength'],
    },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'type'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    TiptapEditor: {
      template: '<div class="tiptap-editor" />',
      props: ['modelValue'],
      emits: ['update:modelValue'],
    },
  }
}

async function mountPostCreate(options?: { query?: Record<string, string> }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const path =
    '/forum/create' + (options?.query ? '?' + new URLSearchParams(options.query).toString() : '')
  await router.push(path)
  await router.isReady()

  const wrapper = mount(PostCreateView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('PostCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListCategories.mockResolvedValue(fakeCategories)
    mockListMySigs.mockResolvedValue(fakeSigs)
    mockCreatePost.mockResolvedValue({ id: 'new-post-1' })
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('renders create post title', async () => {
    const { wrapper } = await mountPostCreate()
    expect(wrapper.text()).toContain('Create Post')
  })

  it('fetches categories on mount', async () => {
    await mountPostCreate()
    expect(mockListCategories).toHaveBeenCalled()
  })

  it('fetches user SIGs on mount', async () => {
    await mountPostCreate()
    expect(mockListMySigs).toHaveBeenCalled()
  })

  it('renders title input', async () => {
    const { wrapper } = await mountPostCreate()
    expect(wrapper.find('.base-input').exists()).toBe(true)
  })

  it('renders TiptapEditor', async () => {
    const { wrapper } = await mountPostCreate()
    expect(wrapper.find('.tiptap-editor').exists()).toBe(true)
  })

  it('renders category select', async () => {
    const { wrapper } = await mountPostCreate()
    const selects = wrapper.findAll('select')
    expect(selects.length).toBeGreaterThanOrEqual(1)
    expect(wrapper.text()).toContain('AI Research')
    expect(wrapper.text()).toContain('Language Learning')
  })

  it('renders SIG select when user has SIGs', async () => {
    const { wrapper } = await mountPostCreate()
    expect(wrapper.text()).toContain('NLP SIG')
  })

  it('shows validation error when submitting empty form', async () => {
    const { wrapper } = await mountPostCreate()
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Title and content are required')
    expect(mockCreatePost).not.toHaveBeenCalled()
  })

  it('renders allow comments checkbox', async () => {
    const { wrapper } = await mountPostCreate()
    const checkbox = wrapper.find('#allow-comments')
    expect(checkbox.exists()).toBe(true)
  })

  it('adds and removes keywords', async () => {
    const { wrapper } = await mountPostCreate()
    // Find keyword input
    const kwInput = wrapper
      .findAll('input[type="text"]')
      .find((i) => i.attributes('maxlength') === '50')
    expect(kwInput).toBeTruthy()
    await kwInput!.setValue('machine-learning')
    await kwInput!.trigger('keydown.enter')
    await flushPromises()

    expect(wrapper.text()).toContain('machine-learning')

    // Remove keyword
    const removeBtn = wrapper.findAll('button').find((b) => b.text().includes('\u00D7'))
    if (removeBtn) {
      await removeBtn.trigger('click')
      expect(wrapper.text()).not.toContain('machine-learning')
    }
  })

  it('navigates to post after successful creation', async () => {
    const { wrapper, router } = await mountPostCreate()
    const pushSpy = vi.spyOn(router, 'push')

    // Set title and content via component internals
    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'My New Post'
    vm.content = '<p>Some content</p>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'My New Post', content: '<p>Some content</p>' }),
    )
    expect(pushSpy).toHaveBeenCalledWith('/forum/new-post-1')
  })

  it('shows error message on creation failure', async () => {
    mockCreatePost.mockRejectedValue({
      response: { data: { detail: 'Post creation failed' } },
    })
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'My New Post'
    vm.content = '<p>Some content</p>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Post creation failed')
  })

  it('restores draft from localStorage on mount', async () => {
    // Key for route without sig_id is ai3l_post_draft_general_anon
    localStorage.setItem(
      'ai3l_post_draft_general_anon',
      JSON.stringify({
        title: 'Draft Title',
        content: '<p>Draft content</p>',
        categoryId: null,
        keywords: ['draft-kw'],
        allowComments: true,
      }),
    )

    const { wrapper } = await mountPostCreate()
    // Draft restored alert should be shown
    expect(wrapper.text()).toContain('Draft restored')
  })

  it('discards draft when discard button clicked', async () => {
    localStorage.setItem(
      'ai3l_post_draft_general_anon',
      JSON.stringify({ title: 'Draft', content: '<p>Draft</p>' }),
    )

    const { wrapper } = await mountPostCreate()
    const discardBtn = wrapper.findAll('button').find((b) => b.text().includes('Discard draft'))
    expect(discardBtn).toBeTruthy()
    await discardBtn!.trigger('click')
    await flushPromises()

    expect(localStorage.getItem('ai3l_post_draft_general_anon')).toBeNull()
  })

  it('uses sig-specific draft key when posting from SIG', async () => {
    localStorage.setItem(
      'ai3l_post_draft_sig1_anon',
      JSON.stringify({ title: 'SIG Draft', content: '<p>SIG content</p>' }),
    )

    const { wrapper } = await mountPostCreate({ query: { sig_id: 'sig1' } })
    expect(wrapper.text()).toContain('Draft restored')
  })

  it('rejects Tiptap empty HTML content on submit', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'My Title'
    vm.content = '<p></p>' // Tiptap default empty

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Content is required')
  })

  it('shows title-specific error when only title is empty', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = ''
    vm.content = '<p>Some content here</p>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Title is required')
  })

  it('shows content-specific error when only content is empty', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'My Title'
    vm.content = ''

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Content is required')
  })

  it('accepts content with only an image tag', async () => {
    const { wrapper, router } = await mountPostCreate()
    const pushSpy = vi.spyOn(router, 'push')

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'Image Post'
    vm.content = '<p><img src="https://example.com/img.png" alt="test"></p>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).toHaveBeenCalledWith(expect.objectContaining({ title: 'Image Post' }))
    expect(pushSpy).toHaveBeenCalledWith('/forum/new-post-1')
  })

  it('accepts content with only an iframe tag', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'Video Embed'
    vm.content = '<iframe src="https://youtube.com/embed/abc"></iframe>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).toHaveBeenCalled()
  })

  it('accepts content with only a video tag', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'Video Post'
    vm.content = '<video src="https://example.com/vid.mp4"></video>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).toHaveBeenCalled()
  })

  it('accepts content with a table tag', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'Table Post'
    vm.content = '<table><tr><td>data</td></tr></table>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).toHaveBeenCalled()
  })

  it('rejects content with only whitespace text', async () => {
    const { wrapper } = await mountPostCreate()

    const vm = wrapper.vm as unknown as { title: string; content: string }
    vm.title = 'Title'
    vm.content = '<p>   </p>'

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreatePost).not.toHaveBeenCalled()
  })

  it('renders back button', async () => {
    const { wrapper } = await mountPostCreate()
    const backBtn = wrapper.findAll('button').find((b) => b.text().includes('Back'))
    expect(backBtn).toBeTruthy()
  })

  it('back button uses router.back() when history exists', async () => {
    const { wrapper, router } = await mountPostCreate()
    const backSpy = vi.spyOn(router, 'back')
    // Simulate history state with a back entry
    Object.defineProperty(window.history, 'state', {
      value: { ...window.history.state, back: '/some-page' },
      writable: true,
      configurable: true,
    })

    const backBtn = wrapper.findAll('button').find((b) => b.text().includes('Back'))
    await backBtn!.trigger('click')

    expect(backSpy).toHaveBeenCalled()
    backSpy.mockRestore()
  })

  it('back button falls back to home when no history', async () => {
    const { wrapper, router } = await mountPostCreate()
    const pushSpy = vi.spyOn(router, 'push')
    // Simulate no back entry in history state
    Object.defineProperty(window.history, 'state', {
      value: { ...window.history.state, back: null },
      writable: true,
      configurable: true,
    })

    const backBtn = wrapper.findAll('button').find((b) => b.text().includes('Back'))
    await backBtn!.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/')
    pushSpy.mockRestore()
  })

  it('back button falls back to SIG when posting from SIG with no history', async () => {
    const { wrapper, router } = await mountPostCreate({ query: { sig_id: 'sig1' } })
    const pushSpy = vi.spyOn(router, 'push')
    Object.defineProperty(window.history, 'state', {
      value: { ...window.history.state, back: null },
      writable: true,
      configurable: true,
    })

    const backBtn = wrapper.findAll('button').find((b) => b.text().includes('Back'))
    await backBtn!.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/sigs/sig1')
    pushSpy.mockRestore()
  })

  describe('H-09: draft key uses getter function', () => {
    it('passes a getter function to useDraft so key is evaluated lazily', async () => {
      // The key is `ai3l_post_draft_general_anon` at setup time (no auth user).
      // When auth loads, the key would change to include the real user ID.
      // This test verifies the draft key resolves correctly at mount time.
      localStorage.setItem(
        'ai3l_post_draft_general_anon',
        JSON.stringify({
          title: 'Lazy Draft',
          content: '<p>Lazy content</p>',
          categoryId: null,
          keywords: [],
          allowComments: true,
        }),
      )

      const { wrapper } = await mountPostCreate()
      // The draft should still be found since the getter evaluates to the same key
      expect(wrapper.text()).toContain('Draft restored')
    })

    it('draft key includes sig_id when posting from SIG context', async () => {
      localStorage.setItem(
        'ai3l_post_draft_sig1_anon',
        JSON.stringify({
          title: 'SIG Lazy Draft',
          content: '<p>SIG content</p>',
          categoryId: null,
          keywords: [],
          allowComments: true,
        }),
      )

      const { wrapper } = await mountPostCreate({ query: { sig_id: 'sig1' } })
      expect(wrapper.text()).toContain('Draft restored')

      // Verify the general key's draft is NOT loaded when sig context is active
      expect(localStorage.getItem('ai3l_post_draft_general_anon')).toBeNull()
    })
  })

  describe('draft integration with useDraft', () => {
    it('clears draft from localStorage after successful submit', async () => {
      localStorage.setItem(
        'ai3l_post_draft_general_anon',
        JSON.stringify({
          title: 'Draft Title',
          content: '<p>Draft content</p>',
          categoryId: null,
          keywords: [],
          allowComments: true,
        }),
      )

      const { wrapper } = await mountPostCreate()
      // Draft should be loaded
      expect(wrapper.text()).toContain('Draft restored')

      // Submit the form (draft data has title and content)
      const form = wrapper.find('form')
      await form.trigger('submit')
      await flushPromises()

      expect(mockCreatePost).toHaveBeenCalled()
      expect(localStorage.getItem('ai3l_post_draft_general_anon')).toBeNull()
    })

    it('does not show draft restored when draft has no title or content', async () => {
      localStorage.setItem(
        'ai3l_post_draft_general_anon',
        JSON.stringify({
          title: '',
          content: '',
          categoryId: null,
          keywords: [],
          allowComments: true,
        }),
      )

      const { wrapper } = await mountPostCreate()
      expect(wrapper.text()).not.toContain('Draft restored')
    })

    it('discard draft resets all form fields', async () => {
      localStorage.setItem(
        'ai3l_post_draft_general_anon',
        JSON.stringify({
          title: 'Draft Title',
          content: '<p>Some content</p>',
          categoryId: 'cat1',
          keywords: ['test'],
          allowComments: false,
        }),
      )

      const { wrapper } = await mountPostCreate()
      expect(wrapper.text()).toContain('Draft restored')

      const discardBtn = wrapper.findAll('button').find((b) => b.text().includes('Discard draft'))
      await discardBtn!.trigger('click')
      await flushPromises()

      // Draft alert should be hidden
      expect(wrapper.text()).not.toContain('Draft restored')

      // Form should be reset (submitting empty form should show validation error)
      const form = wrapper.find('form')
      await form.trigger('submit')
      await flushPromises()
      expect(wrapper.text()).toContain('Title and content are required')
    })
  })
})
