import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ReactionPicker from '../ReactionPicker.vue'

vi.mock('@/constants', () => ({
  REACTIONS: ['LIKE', 'SMILE', 'CRY'] as const,
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('lucide-vue-next', () => ({
  Smile: { name: 'Smile', template: '<svg data-testid="smile-icon" />' },
}))

function mountPicker(
  props: {
    reactionCounts?: Record<string, number> | null
    userReactions?: string[] | null
    readonly?: boolean
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(ReactionPicker, {
    props: {
      reactionCounts: props.reactionCounts ?? null,
      userReactions: props.userReactions ?? null,
      readonly: props.readonly ?? false,
    },
    attachTo: document.body,
  })
}

describe('ReactionPicker', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  describe('interactive mode (readonly=false)', () => {
    it('shows "Add reaction" button', () => {
      const wrapper = mountPicker({ userReactions: [] })
      expect(wrapper.find('button[aria-label="Add reaction"]').exists()).toBe(true)
    })

    it('shows no reaction chips when reactionCounts is null', () => {
      const wrapper = mountPicker({ userReactions: [] })
      const chips = wrapper.findAll('button[aria-label^="React with"]')
      expect(chips.length).toBe(0)
    })

    it('shows chips only for reactions with count > 0', () => {
      const wrapper = mountPicker({
        userReactions: [],
        reactionCounts: { LIKE: 1, SMILE: 0 },
      })
      expect(wrapper.find('button[aria-label="React with LIKE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with SMILE"]').exists()).toBe(false)
    })

    it('shows reaction count in chip', () => {
      const wrapper = mountPicker({
        userReactions: [],
        reactionCounts: { LIKE: 2 },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.text()).toContain('2')
    })

    it('highlights chip when user has reacted', () => {
      const wrapper = mountPicker({
        userReactions: ['LIKE'],
        reactionCounts: { LIKE: 2 },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.classes()).toContain('bg-brand-100')
      expect(likeChip.attributes('aria-pressed')).toBe('true')
    })

    it('does not highlight chip when user has not reacted', () => {
      const wrapper = mountPicker({
        userReactions: [],
        reactionCounts: { LIKE: 1 },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.classes()).not.toContain('bg-brand-100')
      expect(likeChip.attributes('aria-pressed')).toBe('false')
    })

    it('emits toggle with reaction type when chip is clicked', async () => {
      const wrapper = mountPicker({
        userReactions: [],
        reactionCounts: { LIKE: 1 },
      })
      await wrapper.find('button[aria-label="React with LIKE"]').trigger('click')
      expect(wrapper.emitted('toggle')).toBeTruthy()
      expect(wrapper.emitted('toggle')![0]).toEqual(['LIKE'])
    })

    it('picker popup is hidden by default', () => {
      const wrapper = mountPicker({ userReactions: [] })
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })

    it('opens picker popup when "Add reaction" button is clicked', async () => {
      const wrapper = mountPicker({ userReactions: [] })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      const popupBtns = wrapper.findAll('button[aria-label^="React with"]')
      expect(popupBtns.length).toBe(3)
    })

    it('shows all 3 reactions in the picker popup', async () => {
      const wrapper = mountPicker({ userReactions: [] })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      expect(wrapper.find('button[aria-label="React with LIKE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with SMILE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with CRY"]').exists()).toBe(true)
    })

    it('highlights already-reacted reaction in picker popup', async () => {
      const wrapper = mountPicker({
        userReactions: ['LIKE'],
        reactionCounts: { LIKE: 1 },
      })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      const likeInPopup = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeInPopup.classes()).toContain('bg-brand-100')
    })

    it('emits toggle and closes picker when popup reaction is clicked', async () => {
      const wrapper = mountPicker({ userReactions: [] })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      await wrapper.find('button[aria-label="React with SMILE"]').trigger('click')
      await nextTick()

      expect(wrapper.emitted('toggle')![0]).toEqual(['SMILE'])
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })

    it('closes picker when clicking outside the component', async () => {
      const wrapper = mountPicker({ userReactions: [] })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(3)

      document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await nextTick()

      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })
  })

  describe('readonly mode', () => {
    it('shows no "Add reaction" button in readonly mode', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactionCounts: { LIKE: 1 },
        userReactions: ['LIKE'],
      })
      expect(wrapper.find('button[aria-label="Add reaction"]').exists()).toBe(false)
    })

    it('shows visible reactions as spans (not buttons) in readonly mode', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactionCounts: { LIKE: 1, SMILE: 1 },
        userReactions: null,
      })
      expect(wrapper.findAll('button').length).toBe(0)
      const spans = wrapper.findAll('span.rounded-full')
      expect(spans.length).toBe(2)
    })

    it('shows no reactions UI in readonly mode when reactionCounts is null', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactionCounts: null,
        userReactions: null,
      })
      expect(wrapper.findAll('button').length).toBe(0)
      expect(wrapper.findAll('span.rounded-full').length).toBe(0)
    })

    it('shows reaction count in readonly span', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactionCounts: { CRY: 3 },
        userReactions: null,
      })
      const spans = wrapper.findAll('span.rounded-full')
      expect(spans[0].text()).toContain('3')
    })
  })
})
