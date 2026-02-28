<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import { useAuthStore } from '@/stores/auth'
import { useWebSocket } from '@/composables/useWebSocket'

const auth = useAuthStore()
const { connect, cleanup } = useWebSocket()

watch(
  () => auth.isAuthenticated,
  (authenticated) => {
    if (authenticated) connect()
    else cleanup()
  },
  { immediate: true },
)
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    <main>
      <RouterView />
    </main>
    <ToastNotification />
  </div>
</template>
