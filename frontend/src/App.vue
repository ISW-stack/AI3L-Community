<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import PrivacyConsentModal from '@/components/PrivacyConsentModal.vue'
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

function onConsentAccepted() {
  auth.requiresConsent = false
}
</script>

<template>
  <div class="min-h-screen bg-surface-alt">
    <AppNavbar />
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
    <ToastNotification />
    <PrivacyConsentModal
      v-if="auth.isAuthenticated && auth.requiresConsent"
      @accepted="onConsentAccepted"
    />
  </div>
</template>
