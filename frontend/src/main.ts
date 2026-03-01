import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.config.errorHandler = (err) => {
  const message = err instanceof Error ? err.message : 'An unexpected error occurred.'
  window.dispatchEvent(
    new CustomEvent('app:toast', {
      detail: { message, type: 'error' },
    }),
  )
  console.error('[Vue Error]', err)
}

app.mount('#app')
