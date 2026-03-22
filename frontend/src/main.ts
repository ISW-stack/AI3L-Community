import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { i18n, loadLocaleMessages } from '@/locales'
import { useToastStore } from '@/stores/toast'
import '@fontsource-variable/inter'
import './style.css'

async function bootstrap() {
  // Load the detected locale messages before mounting (en is already bundled)
  const initialLocale = i18n.global.locale.value
  if (initialLocale !== 'en') {
    await loadLocaleMessages(initialLocale)
  }

  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)
  app.use(i18n)
  app.use(router)

  app.config.errorHandler = (_err, _instance, info) => {
    if (import.meta.env.DEV) console.error('[Vue Error]', _err, info)
    try {
      const toastStore = useToastStore()
      toastStore.show('An unexpected error occurred.', 'error')
    } catch {
      // Toast store not yet available
    }
  }

  app.mount('#app')
}

bootstrap()
