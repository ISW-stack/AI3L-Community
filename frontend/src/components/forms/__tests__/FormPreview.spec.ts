import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import FormPreview from '../FormPreview.vue'
import type { Question } from '@/types'

vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}))

function createStubs() {
  return {
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    EmptyState: { template: '<div class="empty-state" />', props: ['message'] },
  }
}

function mountPreview(props: Partial<Record<string, unknown>> = {}) {
  return mount(FormPreview, {
    props: {
      title: 'Test Form',
      description: '',
      bannerUrl: '',
      questions: [],
      previewMode: 'desktop' as const,
      ...props,
    },
    global: { stubs: createStubs() },
  })
}

describe('FormPreview', () => {
  describe('rendering', () => {
    it('renders desktop/mobile toggle buttons', () => {
      const wrapper = mountPreview()
      expect(wrapper.text()).toContain('Desktop')
      expect(wrapper.text()).toContain('Mobile')
    })

    it('renders preview mode info alert', () => {
      const wrapper = mountPreview()
      expect(wrapper.find('.base-alert').exists()).toBe(true)
    })

    it('renders banner image when bannerUrl provided', () => {
      const wrapper = mountPreview({ bannerUrl: 'https://example.com/img.jpg' })
      const img = wrapper.find('img[alt="Banner"]')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('https://example.com/img.jpg')
    })

    it('hides banner when bannerUrl is empty', () => {
      const wrapper = mountPreview({ bannerUrl: '' })
      const img = wrapper.find('img[alt="Banner"]')
      expect(img.exists()).toBe(false)
    })

    it('renders description HTML when provided', () => {
      const wrapper = mountPreview({ description: '<p>Hello World</p>' })
      const desc = wrapper.find('.prose')
      expect(desc.exists()).toBe(true)
      expect(desc.html()).toContain('Hello World')
    })

    it('hides description when empty', () => {
      const wrapper = mountPreview({ description: '' })
      expect(wrapper.find('.prose').exists()).toBe(false)
    })
  })

  describe('questions rendering', () => {
    it('renders empty state when no questions', () => {
      const wrapper = mountPreview({ questions: [] })
      expect(wrapper.find('.empty-state').exists()).toBe(true)
    })

    it('renders text question', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'text', label: 'Name', required: true, options: [] },
      ]
      const wrapper = mountPreview({ questions })
      expect(wrapper.text()).toContain('1. Name')
      const textInput = wrapper.find('input[type="text"]')
      expect(textInput.exists()).toBe(true)
      expect(textInput.attributes('disabled')).toBeDefined()
    })

    it('renders textarea question', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'textarea', label: 'Description', options: [] },
      ]
      const wrapper = mountPreview({ questions })
      expect(wrapper.text()).toContain('1. Description')
      expect(wrapper.find('textarea').exists()).toBe(true)
    })

    it('renders single_choice question with options', () => {
      const questions: Question[] = [
        {
          id: 'q1',
          type: 'single_choice',
          label: 'Pick one',
          options: [
            { id: 'o1', label: 'Alpha' },
            { id: 'o2', label: 'Beta' },
          ],
        },
      ]
      const wrapper = mountPreview({ questions })
      expect(wrapper.text()).toContain('Alpha')
      expect(wrapper.text()).toContain('Beta')
      const radios = wrapper.findAll('input[type="radio"]')
      expect(radios.length).toBe(2)
    })

    it('renders multiple_choice question with options', () => {
      const questions: Question[] = [
        {
          id: 'q1',
          type: 'multiple_choice',
          label: 'Select multiple',
          options: [
            { id: 'o1', label: 'X' },
            { id: 'o2', label: 'Y' },
          ],
        },
      ]
      const wrapper = mountPreview({ questions })
      const checkboxes = wrapper.findAll('input[type="checkbox"]')
      expect(checkboxes.length).toBe(2)
    })

    it('renders dropdown question', () => {
      const questions: Question[] = [
        {
          id: 'q1',
          type: 'dropdown',
          label: 'Choose',
          options: [{ id: 'o1', label: 'Opt1' }],
        },
      ]
      const wrapper = mountPreview({ questions })
      const select = wrapper.find('select')
      expect(select.exists()).toBe(true)
    })

    it('renders rating question with buttons', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'rating', label: 'Rate', min: 1, max: 5, options: [] },
      ]
      const wrapper = mountPreview({ questions })
      const ratingBtns = wrapper.findAll('button[disabled]')
      expect(ratingBtns.length).toBe(5)
    })

    it('renders file_upload question', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'file_upload', label: 'Upload', options: [] },
      ]
      const wrapper = mountPreview({ questions })
      const fileInput = wrapper.find('input[type="file"]')
      expect(fileInput.exists()).toBe(true)
    })

    it('shows required asterisk for required questions', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'text', label: 'Required Q', required: true, options: [] },
      ]
      const wrapper = mountPreview({ questions })
      expect(wrapper.find('.text-danger-500').exists()).toBe(true)
    })

    it('renders multiple questions with correct numbering', () => {
      const questions: Question[] = [
        { id: 'q1', type: 'text', label: 'First', options: [] },
        { id: 'q2', type: 'text', label: 'Second', options: [] },
        { id: 'q3', type: 'text', label: 'Third', options: [] },
      ]
      const wrapper = mountPreview({ questions })
      expect(wrapper.text()).toContain('1. First')
      expect(wrapper.text()).toContain('2. Second')
      expect(wrapper.text()).toContain('3. Third')
    })
  })

  describe('mobile preview mode', () => {
    it('applies mobile frame class when previewMode is mobile', () => {
      const wrapper = mountPreview({ previewMode: 'mobile' })
      expect(wrapper.find('.rounded-4xl').exists()).toBe(true)
    })

    it('does not apply mobile frame class when previewMode is desktop', () => {
      const wrapper = mountPreview({ previewMode: 'desktop' })
      expect(wrapper.find('.rounded-4xl').exists()).toBe(false)
    })
  })

  describe('emits', () => {
    it('emits set-desktop when desktop button clicked', async () => {
      const wrapper = mountPreview({ previewMode: 'mobile' })
      const desktopBtn = wrapper.findAll('button').find((b) => b.text() === 'Desktop')
      await desktopBtn!.trigger('click')
      expect(wrapper.emitted('set-desktop')).toBeTruthy()
    })

    it('emits set-mobile when mobile button clicked', async () => {
      const wrapper = mountPreview({ previewMode: 'desktop' })
      const mobileBtn = wrapper.findAll('button').find((b) => b.text() === 'Mobile')
      await mobileBtn!.trigger('click')
      expect(wrapper.emitted('set-mobile')).toBeTruthy()
    })
  })
})
