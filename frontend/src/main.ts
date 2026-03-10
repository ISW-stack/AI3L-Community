import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { i18n } from '@/locales'
import { useToastStore } from '@/stores/toast'
import '@fontsource-variable/inter'
import './style.css'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(i18n)
app.use(router)

app.config.errorHandler = (err) => {
  const message = err instanceof Error ? err.message : i18n.global.t('common.unknownError')
  useToastStore().show(message, 'error')
  console.error('[Vue Error]', err)
}

app.mount('#app')
