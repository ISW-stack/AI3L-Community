import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VoteButtons from '../VoteButtons.vue'

vi.mock('lucide-vue-next', () => ({
  ChevronUp: { name: 'ChevronUp', template: '<svg data-testid="chevron-up" />' },
  ChevronDown: { name: 'ChevronDown', template: '<svg data-testid="chevron-down" />' },
}))

function mountVoteButtons(props: {
  commentId: string
  score: number
  userVote: -1 | 0 | 1
  disabled: boolean
}) {
  return mount(VoteButtons, { props })
}

describe('VoteButtons', () => {
  describe('rendering', () => {
    it('displays the score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 5,
        userVote: 0,
        disabled: false,
      })
      expect(wrapper.text()).toContain('5')
    })

    it('displays negative score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: -3,
        userVote: 0,
        disabled: false,
      })
      expect(wrapper.text()).toContain('-3')
    })

    it('displays zero score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: false,
      })
      expect(wrapper.text()).toContain('0')
    })

    it('renders up and down arrows', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: false,
      })
      expect(wrapper.find('[data-testid="chevron-up"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="chevron-down"]').exists()).toBe(true)
    })
  })

  describe('up vote', () => {
    it('emits vote(1) when up arrow clicked and userVote is 0', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: false,
      })
      const upBtn = wrapper.findAll('button')[0]
      await upBtn.trigger('click')
      expect(wrapper.emitted('vote')).toBeTruthy()
      expect(wrapper.emitted('vote')![0]).toEqual([1])
    })

    it('emits vote(0) when up arrow clicked and userVote is already 1 (toggle off)', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 1,
        userVote: 1,
        disabled: false,
      })
      const upBtn = wrapper.findAll('button')[0]
      await upBtn.trigger('click')
      expect(wrapper.emitted('vote')![0]).toEqual([0])
    })

    it('emits vote(1) when up arrow clicked and userVote is -1', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: -1,
        userVote: -1,
        disabled: false,
      })
      const upBtn = wrapper.findAll('button')[0]
      await upBtn.trigger('click')
      expect(wrapper.emitted('vote')![0]).toEqual([1])
    })
  })

  describe('down vote', () => {
    it('emits vote(-1) when down arrow clicked and userVote is 0', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: false,
      })
      const downBtn = wrapper.findAll('button')[1]
      await downBtn.trigger('click')
      expect(wrapper.emitted('vote')![0]).toEqual([-1])
    })

    it('emits vote(0) when down arrow clicked and userVote is already -1 (toggle off)', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: -1,
        userVote: -1,
        disabled: false,
      })
      const downBtn = wrapper.findAll('button')[1]
      await downBtn.trigger('click')
      expect(wrapper.emitted('vote')![0]).toEqual([0])
    })

    it('emits vote(-1) when down arrow clicked and userVote is 1', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 1,
        userVote: 1,
        disabled: false,
      })
      const downBtn = wrapper.findAll('button')[1]
      await downBtn.trigger('click')
      expect(wrapper.emitted('vote')![0]).toEqual([-1])
    })
  })

  describe('disabled state', () => {
    it('does not emit when disabled and up arrow clicked', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: true,
      })
      const upBtn = wrapper.findAll('button')[0]
      await upBtn.trigger('click')
      expect(wrapper.emitted('vote')).toBeUndefined()
    })

    it('does not emit when disabled and down arrow clicked', async () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: true,
      })
      const downBtn = wrapper.findAll('button')[1]
      await downBtn.trigger('click')
      expect(wrapper.emitted('vote')).toBeUndefined()
    })

    it('buttons have disabled attribute when disabled', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: true,
      })
      const buttons = wrapper.findAll('button')
      expect(buttons[0].attributes('disabled')).toBeDefined()
      expect(buttons[1].attributes('disabled')).toBeDefined()
    })
  })

  describe('visual highlights', () => {
    it('highlights up button when userVote is 1', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 1,
        userVote: 1,
        disabled: false,
      })
      const upBtn = wrapper.findAll('button')[0]
      expect(upBtn.classes()).toContain('text-brand-600')
    })

    it('highlights down button when userVote is -1', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: -1,
        userVote: -1,
        disabled: false,
      })
      const downBtn = wrapper.findAll('button')[1]
      expect(downBtn.classes()).toContain('text-danger-600')
    })

    it('score text is styled for positive score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 3,
        userVote: 0,
        disabled: false,
      })
      const scoreEl = wrapper.find('.font-semibold')
      expect(scoreEl.classes()).toContain('text-brand-600')
    })

    it('score text is styled for negative score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: -2,
        userVote: 0,
        disabled: false,
      })
      const scoreEl = wrapper.find('.font-semibold')
      expect(scoreEl.classes()).toContain('text-danger-600')
    })

    it('score text is muted for zero score', () => {
      const wrapper = mountVoteButtons({
        commentId: 'c1',
        score: 0,
        userVote: 0,
        disabled: false,
      })
      const scoreEl = wrapper.find('.font-semibold')
      expect(scoreEl.classes()).toContain('text-muted')
    })
  })
})
