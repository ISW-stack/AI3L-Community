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
