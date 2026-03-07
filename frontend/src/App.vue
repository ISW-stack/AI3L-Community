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

const isAdminPage = computed(() => route.path.startsWith('/admin'))
const isSigPage = computed(() => route.path.startsWith('/sigs/') && route.params.id)
const isProfilePage = computed(() => route.path === '/profile')
const isPublicProfilePage = computed(() => route.path.startsWith('/users/') && route.params.id)

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
  <div class="min-h-screen bg-surface-alt flex flex-col">
    <AppNavbar />
    <!-- 
      For Admin/SIG/Profile: w-full 
      For Others: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8
    -->
    <main
      :class="[
        'flex-1',
        isAdminPage || isSigPage || isProfilePage || isPublicProfilePage
          ? 'w-full'
          : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8',
        isSigPage ? 'flex flex-col h-[calc(100vh-64px)] overflow-hidden' : '',
      ]"
    >
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
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
