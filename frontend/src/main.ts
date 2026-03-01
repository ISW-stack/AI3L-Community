import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useToastStore } from '@/stores/toast'
import '@fontsource-variable/inter'
import './style.css'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)

app.config.errorHandler = (err) => {
  const message = err instanceof Error ? err.message : 'An unexpected error occurred.'
  useToastStore().show(message, 'error')
  console.error('[Vue Error]', err)
}

app.mount('#app')
