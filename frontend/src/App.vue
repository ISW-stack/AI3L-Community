<script setup lang="ts">
import { watch, computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'
import AppFooter from '@/components/AppFooter.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import PrivacyConsentModal from '@/components/PrivacyConsentModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useWebSocket } from '@/composables/useWebSocket'

const auth = useAuthStore()
const { connect, cleanup } = useWebSocket()
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

function onConsentAccepted() {
  auth.requiresConsent = false
}
</script>

<template>
  <div class="min-h-screen bg-surface-alt flex flex-col overflow-x-hidden">
    <AppNavbar />

    <main
      :class="[
        'flex-1 flex flex-col w-full',
        isFullWidth ? '' : 'max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8',
      ]"
      style="min-width: 0"
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

<style>
html {
  margin-left: calc(100vw - 100%);
  overflow-y: scroll;
  scrollbar-gutter: stable;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
}

@media (min-width: 1024px) {
  ::-webkit-scrollbar {
    width: 8px;
  }
  ::-webkit-scrollbar-track {
    background: #f1f1f1;
  }
  ::-webkit-scrollbar-thumb {
    background: #ccc;
    border-radius: 4px;
  }
}
</style>
