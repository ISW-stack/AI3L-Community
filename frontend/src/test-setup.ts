// Polyfill ResizeObserver for JSDOM (used by MessageThread and other components)
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    constructor(_callback: ResizeObserverCallback) {}
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import en from './locales/en'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en },
  missing: () => {
    /* suppress warnings in tests */
  },
})

config.global.plugins.push(i18n)
