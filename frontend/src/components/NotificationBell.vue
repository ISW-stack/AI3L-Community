<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { Notification } from '@/types'
import { useNotificationStore } from '@/stores/notifications'
import { relativeTime } from '@/utils/datetime'
import { Bell, Settings, User } from 'lucide-vue-next'

const router = useRouter()
const notifStore = useNotificationStore()
const dropdownOpen = ref(false)

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
  if (dropdownOpen.value) {
    notifStore.fetchRecent()
  }
}

function closeDropdown() {
  dropdownOpen.value = false
}

async function markRead(notif: Notification) {
  if (!notif.is_read) {
    await notifStore.markRead(notif.id)
  }
  navigateToEntity(notif)
  closeDropdown()
}

function navigateToEntity(notif: Notification) {
  if (notif.entity_type === 'comment' && notif.entity_id) {
    router.push('/notifications')
  } else if (notif.entity_type === 'post' && notif.entity_id) {
    router.push(`/forum/${notif.entity_id}`)
  } else {
    router.push('/notifications')
  }
}

function handleClickOutside(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest('.notification-bell-wrapper')
  if (!el) {
    closeDropdown()
  }
}

onMounted(() => {
  notifStore.fetchUnreadCount()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="relative notification-bell-wrapper">
    <button
      @click="toggleDropdown"
      class="relative p-1 text-muted hover:text-foreground focus:outline-none transition"
      aria-label="Notifications"
      :aria-expanded="dropdownOpen"
    >
      <Bell class="w-5 h-5" aria-hidden="true" />
      <span
        v-if="notifStore.unreadCount > 0"
        class="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-danger-500 rounded-full"
      >
        {{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}
      </span>
    </button>

    <!-- Dropdown -->
    <div
      v-if="dropdownOpen"
      class="absolute right-0 mt-2 w-80 bg-surface border border-border rounded-lg shadow-lg z-50"
    >
      <div class="flex items-center justify-between px-4 py-2 border-b border-border">
        <span class="text-sm font-semibold text-foreground">Notifications</span>
        <button
          v-if="notifStore.unreadCount > 0"
          @click="notifStore.markAllRead"
          class="text-xs text-brand-600 hover:text-brand-700 transition"
        >
          Mark all as read
        </button>
      </div>

      <div v-if="notifStore.loading" class="px-4 py-6 text-center text-sm text-muted">
        Loading...
      </div>

      <div
        v-else-if="notifStore.items.length === 0"
        class="px-4 py-6 text-center text-sm text-muted"
      >
        No notifications yet.
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <button
          v-for="notif in notifStore.items"
          :key="notif.id"
          @click="markRead(notif)"
          class="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-alt border-b border-surface-alt last:border-0 transition"
          :class="{ 'bg-brand-50/50': !notif.is_read }"
        >
          <div
            class="shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden"
          >
            <img
              v-if="notif.trigger_user?.avatar_url"
              :src="notif.trigger_user.avatar_url"
              class="w-8 h-8 rounded-full object-cover"
              alt=""
            />
            <Settings
              v-else-if="notif.action_type === 'SYSTEM'"
              class="w-4 h-4 text-muted"
              aria-hidden="true"
            />
            <User v-else class="w-4 h-4 text-muted" aria-hidden="true" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-foreground leading-snug">{{ notif.message }}</p>
            <p class="text-xs text-muted mt-0.5">{{ relativeTime(notif.created_at) }}</p>
          </div>
          <div v-if="!notif.is_read" class="shrink-0 w-2 h-2 rounded-full bg-brand-500 mt-2"></div>
        </button>
      </div>

      <div class="border-t border-border">
        <router-link
          to="/notifications"
          @click="closeDropdown"
          class="block text-center text-sm text-brand-600 hover:text-brand-700 py-2 transition"
        >
          View All
        </router-link>
      </div>
    </div>
  </div>
</template>
