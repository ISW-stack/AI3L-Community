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
    reactions?: Record<string, string[]> | null
    userId?: string | null
    readonly?: boolean
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(ReactionPicker, {
    props: {
      reactions: props.reactions ?? null,
      userId: props.userId ?? null,
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
      const wrapper = mountPicker({ userId: 'u1' })
      expect(wrapper.find('button[aria-label="Add reaction"]').exists()).toBe(true)
    })

    it('shows no reaction chips when reactions is null', () => {
      const wrapper = mountPicker({ userId: 'u1' })
      const chips = wrapper.findAll('button[aria-label^="React with"]')
      expect(chips.length).toBe(0)
    })

    it('shows chips only for reactions with count > 0', () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u2'], SMILE: [] },
      })
      // LIKE has count 1, SMILE has count 0
      expect(wrapper.find('button[aria-label="React with LIKE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with SMILE"]').exists()).toBe(false)
    })

    it('shows reaction count in chip', () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u2', 'u3'] },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.text()).toContain('2')
    })

    it('highlights chip when userId has reacted', () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u1', 'u2'] },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.classes()).toContain('bg-brand-100')
      expect(likeChip.attributes('aria-pressed')).toBe('true')
    })

    it('does not highlight chip when userId has not reacted', () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u2'] },
      })
      const likeChip = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeChip.classes()).not.toContain('bg-brand-100')
      expect(likeChip.attributes('aria-pressed')).toBe('false')
    })

    it('emits toggle with reaction type when chip is clicked', async () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u2'] },
      })
      await wrapper.find('button[aria-label="React with LIKE"]').trigger('click')
      expect(wrapper.emitted('toggle')).toBeTruthy()
      expect(wrapper.emitted('toggle')![0]).toEqual(['LIKE'])
    })

    it('picker popup is hidden by default', () => {
      const wrapper = mountPicker({ userId: 'u1' })
      // All 3 reaction buttons inside the popup should not exist (v-if=false)
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })

    it('opens picker popup when "Add reaction" button is clicked', async () => {
      const wrapper = mountPicker({ userId: 'u1' })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      const popupBtns = wrapper.findAll('button[aria-label^="React with"]')
      expect(popupBtns.length).toBe(3) // LIKE, SMILE, CRY
    })

    it('shows all 3 reactions in the picker popup', async () => {
      const wrapper = mountPicker({ userId: 'u1' })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      expect(wrapper.find('button[aria-label="React with LIKE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with SMILE"]').exists()).toBe(true)
      expect(wrapper.find('button[aria-label="React with CRY"]').exists()).toBe(true)
    })

    it('highlights already-reacted reaction in picker popup', async () => {
      const wrapper = mountPicker({
        userId: 'u1',
        reactions: { LIKE: ['u1'] },
      })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      const likeInPopup = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeInPopup.classes()).toContain('bg-brand-100')
    })

    it('emits toggle and closes picker when popup reaction is clicked', async () => {
      const wrapper = mountPicker({ userId: 'u1' })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()

      await wrapper.find('button[aria-label="React with SMILE"]').trigger('click')
      await nextTick()

      expect(wrapper.emitted('toggle')![0]).toEqual(['SMILE'])
      // Picker should close after selection
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })

    it('closes picker when clicking outside the component', async () => {
      const wrapper = mountPicker({ userId: 'u1' })
      await wrapper.find('button[aria-label="Add reaction"]').trigger('click')
      await nextTick()
      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(3)

      // Click outside
      document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await nextTick()

      expect(wrapper.findAll('button[aria-label^="React with"]').length).toBe(0)
    })
  })

  describe('readonly mode', () => {
    it('shows no "Add reaction" button in readonly mode', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactions: { LIKE: ['u1'] },
        userId: 'u1',
      })
      expect(wrapper.find('button[aria-label="Add reaction"]').exists()).toBe(false)
    })

    it('shows visible reactions as spans (not buttons) in readonly mode', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactions: { LIKE: ['u1'], SMILE: ['u2'] },
        userId: null,
      })
      // No buttons at all
      expect(wrapper.findAll('button').length).toBe(0)
      // Spans for LIKE and SMILE
      const spans = wrapper.findAll('span.rounded-full')
      expect(spans.length).toBe(2)
    })

    it('shows no reactions UI in readonly mode when reactions is null', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactions: null,
        userId: null,
      })
      expect(wrapper.findAll('button').length).toBe(0)
      expect(wrapper.findAll('span.rounded-full').length).toBe(0)
    })

    it('shows reaction count in readonly span', () => {
      const wrapper = mountPicker({
        readonly: true,
        reactions: { CRY: ['u1', 'u2', 'u3'] },
        userId: null,
      })
      const spans = wrapper.findAll('span.rounded-full')
      expect(spans[0].text()).toContain('3')
    })
  })
})
