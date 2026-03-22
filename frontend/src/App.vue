<script setup lang="ts">
import { watch, computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'
import AppFooter from '@/components/AppFooter.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import PrivacyConsentModal from '@/components/PrivacyConsentModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useDMStore } from '@/stores/dm'
import { useWebSocket } from '@/composables/useWebSocket'

const auth = useAuthStore()
const dmStore = useDMStore()
const { connect, cleanup, onReconnect } = useWebSocket()
const route = useRoute()

const isFullWidth = computed(() => route.meta.fullWidth === true)

watch(
  () => auth.isAuthenticated,
  (authenticated) => {
    if (authenticated) connect()
    else cleanup()
  },
  { immediate: true },
)

// DM-02: After WebSocket reconnection, re-sync DM state to recover any
// messages that arrived while the connection was dropped.
onReconnect(() => {
  dmStore.fetchUnreadCount()
  const convId = dmStore.activeConversationId
  if (convId) {
    dmStore.fetchMessages(convId, 1, 30)
  }
})

function onConsentAccepted() {
  auth.requiresConsent = false
}
</script>

<template>
  <div class="min-h-screen bg-surface-alt flex flex-col">
    <AppNavbar />

    <main
      :class="[
        'flex-1 flex flex-col w-full min-w-0',
        isFullWidth ? '' : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8',
      ]"
    >
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <div :key="route.path" class="w-full flex-1 flex flex-col">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>

    <AppFooter />
    <ToastNotification />
    <PrivacyConsentModal
      v-if="auth.isAuthenticated && auth.requiresConsent"
      @accepted="onConsentAccepted"
    />
  </div>
</template>
