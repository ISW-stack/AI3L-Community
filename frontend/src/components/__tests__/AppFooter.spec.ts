import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppFooter from '../AppFooter.vue'

describe('AppFooter', () => {
  it('should render copyright text', () => {
    const wrapper = mount(AppFooter)
    expect(wrapper.text()).toContain('© 2025 AI3L Community. All rights reserved.')
  })

  it('should render tagline text', () => {
    const wrapper = mount(AppFooter)
    expect(wrapper.text()).toContain('AI in Language Learning and Literacy')
  })
})
