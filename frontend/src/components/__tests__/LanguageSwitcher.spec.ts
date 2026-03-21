import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import LanguageSwitcher from '../LanguageSwitcher.vue'

const mockSetLocale = vi.fn().mockResolvedValue(undefined)
const mockT = vi.fn((key: string) => key)
const mockCurrentLocale = ref('en')

vi.mock('@/composables/useLocale', () => ({
  useLocale: () => ({
    t: mockT,
    currentLocale: mockCurrentLocale,
    setLocale: mockSetLocale,
  }),
}))

vi.mock('@/locales', () => ({
  LOCALE_GROUPS: [
    {
      id: 'europe',
      labelKey: 'language.region.europe',
      locales: ['fr', 'es'],
    },
    {
      id: 'eastAsia',
      labelKey: 'language.region.eastAsia',
      locales: ['zh-TW', 'ja'],
    },
  ],
  LOCALE_OPTIONS: [
    { value: 'en', label: 'English' },
    { value: 'fr', label: 'Français' },
    { value: 'es', label: 'Español' },
    { value: 'zh-TW', label: '繁體中文' },
    { value: 'ja', label: '日本語' },
  ],
}))

function mountSwitcher(props: Record<string, unknown> = {}) {
  return mount(LanguageSwitcher, {
    props,
    global: {
      stubs: {
        Globe: { template: '<span class="icon-globe" />' },
        ChevronDown: { template: '<span class="icon-chevron-down" />' },
        ChevronRight: { template: '<span class="icon-chevron-right" />' },
        Check: { template: '<span class="icon-check" />' },
      },
    },
  })
}

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    mockSetLocale.mockReset()
    mockSetLocale.mockResolvedValue(undefined)
    mockT.mockReset()
    mockT.mockImplementation((key: string) => key)
    mockCurrentLocale.value = 'en'
  })

  describe('rendering', () => {
    it('should render the trigger button', () => {
      const wrapper = mountSwitcher()
      const button = wrapper.find('button')
      expect(button.exists()).toBe(true)
    })

    it('should show the current locale label', () => {
      const wrapper = mountSwitcher()
      expect(wrapper.find('button span.truncate').text()).toBe('English')
    })

    it('should show correct label when locale changes', () => {
      mockCurrentLocale.value = 'fr'
      const wrapper = mountSwitcher()
      expect(wrapper.find('button span.truncate').text()).toBe('Français')
    })
  })

  describe('toggle', () => {
    it('should open dropdown panel on click', async () => {
      const wrapper = mountSwitcher()
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)

      await wrapper.find('button').trigger('click')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(true)
    })

    it('should close dropdown panel on second click', async () => {
      const wrapper = mountSwitcher()

      await wrapper.find('button').trigger('click')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(true)

      await wrapper.find('button').trigger('click')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    })
  })

  describe('locale selection', () => {
    it('should call setLocale and close panel when selecting a locale', async () => {
      const wrapper = mountSwitcher()

      // Open the dropdown
      await wrapper.find('button').trigger('click')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(true)

      // Click the English option (ungrouped, always visible)
      const options = wrapper.findAll('[role="option"]')
      expect(options.length).toBeGreaterThanOrEqual(1)
      await options[0].trigger('click')

      expect(mockSetLocale).toHaveBeenCalledWith('en')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    })
  })

  describe('escape key', () => {
    it('should close panel on Escape key', async () => {
      const wrapper = mountSwitcher()

      // Open the dropdown
      await wrapper.find('button').trigger('click')
      expect(wrapper.find('[role="listbox"]').exists()).toBe(true)

      // Press Escape on the trigger button
      await wrapper.find('button').trigger('keydown', { key: 'Escape' })
      expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    })
  })

  describe('compact variant', () => {
    it('should apply compact styling by default', () => {
      const wrapper = mountSwitcher()
      const button = wrapper.find('button')
      expect(button.classes()).toContain('bg-transparent')
    })

    it('should not apply w-full to wrapper by default', () => {
      const wrapper = mountSwitcher()
      const root = wrapper.find('.relative')
      expect(root.classes()).not.toContain('w-full')
    })
  })

  describe('form variant', () => {
    it('should apply form styling classes', () => {
      const wrapper = mountSwitcher({ variant: 'form' })
      const button = wrapper.find('button')
      expect(button.classes()).toContain('w-full')
      expect(button.classes()).toContain('border')
      expect(button.classes()).toContain('border-border')
    })

    it('should apply w-full to wrapper', () => {
      const wrapper = mountSwitcher({ variant: 'form' })
      const root = wrapper.find('.relative')
      expect(root.classes()).toContain('w-full')
    })
  })

  describe('group expand/collapse', () => {
    it('should expand a group when its header is clicked', async () => {
      const wrapper = mountSwitcher()

      // Open the dropdown
      await wrapper.find('button').trigger('click')

      // Find group header buttons (they have uppercase tracking-wider classes)
      const groupHeaders = wrapper.findAll('button.uppercase')
      expect(groupHeaders.length).toBe(2)

      // Initially the first group should NOT be expanded
      expect(groupHeaders[0].attributes('aria-expanded')).toBe('false')

      // Click the first group header (Europe)
      await groupHeaders[0].trigger('click')

      // The group should now be expanded
      expect(groupHeaders[0].attributes('aria-expanded')).toBe('true')
    })

    it('should collapse a group when its header is clicked again', async () => {
      const wrapper = mountSwitcher()

      // Open the dropdown
      await wrapper.find('button').trigger('click')

      const groupHeaders = wrapper.findAll('button.uppercase')

      // Expand
      await groupHeaders[0].trigger('click')
      expect(groupHeaders[0].attributes('aria-expanded')).toBe('true')

      // Collapse
      await groupHeaders[0].trigger('click')
      expect(groupHeaders[0].attributes('aria-expanded')).toBe('false')
    })
  })

  describe('scrollbar-gutter', () => {
    it('should have scrollbar-gutter: stable on the dropdown scroll container', async () => {
      const wrapper = mountSwitcher()

      // Open the dropdown
      await wrapper.find('button').trigger('click')

      // Find the scrollable container
      const scrollContainer = wrapper.find('.max-h-80.overflow-y-auto')
      expect(scrollContainer.exists()).toBe(true)
      expect(scrollContainer.attributes('style')).toContain('scrollbar-gutter: stable')
    })
  })

  describe('check icon for current locale', () => {
    it('should show check icon for English when current locale is en', async () => {
      mockCurrentLocale.value = 'en'
      const wrapper = mountSwitcher()

      // Open dropdown
      await wrapper.find('button').trigger('click')

      // The English option should have aria-selected="true"
      const englishOption = wrapper.findAll('[role="option"]')[0]
      expect(englishOption.attributes('aria-selected')).toBe('true')
      // Check icon is rendered with font-medium styling for active locale
      expect(englishOption.classes()).toContain('font-medium')
      expect(englishOption.classes()).toContain('text-brand-600')
    })

    it('should not show check icon for English when current locale is not en', async () => {
      mockCurrentLocale.value = 'fr'
      const wrapper = mountSwitcher()

      // Open dropdown
      await wrapper.find('button').trigger('click')

      // The English option should NOT have the check icon
      const englishOption = wrapper.findAll('[role="option"]')[0]
      expect(englishOption.find('.icon-check').exists()).toBe(false)
    })
  })
})
