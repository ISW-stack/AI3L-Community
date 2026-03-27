<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Notification } from '@/types'
import { useNotificationStore } from '@/stores/notifications'
import { useDropdownKeyNav } from '@/composables/useDropdownKeyNav'
import { relativeTime } from '@/utils/datetime'
import { Bell, Settings, User } from 'lucide-vue-next'

const { t } = useI18n()
const router = useRouter()
const notifStore = useNotificationStore()
const dropdownOpen = ref(false)
const avatarFailed = reactive<Record<string, boolean>>({})

function openDropdown() {
  if (!dropdownOpen.value) {
    dropdownOpen.value = true
    notifStore.fetchRecent()
  }
}

const { handleDropdownKeydown } = useDropdownKeyNav({
  isOpen: dropdownOpen,
  onOpen: openDropdown,
  onClose: () => (dropdownOpen.value = false),
  wrapperClass: 'notification-bell-wrapper',
  triggerSelector: 'button[data-notification-trigger]',
})

function toggleDropdown() {
  if (dropdownOpen.value) {
    dropdownOpen.value = false
  } else {
    openDropdown()
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
  if (notif.entity_type === 'friendship') {
    router.push('/friends')
  } else if (notif.action_type === 'CO_AUTHOR_INVITE') {
    router.push('/profile?tab=social')
  } else if ((notif.entity_type === 'comment' || notif.entity_type === 'post') && notif.entity_id) {
    router.push(`/forum/${notif.entity_id}`)
  } else {
    router.push('/notifications')
  }
}

// Store the registered handler reference so addEventListener and
// removeEventListener receive the exact same function object.
let _clickHandler: ((e: MouseEvent) => void) | null = null

onMounted(() => {
  notifStore.fetchUnreadCount()
  _clickHandler = (e: MouseEvent) => {
    const el = (e.target as HTMLElement).closest('.notification-bell-wrapper')
    if (!el) {
      closeDropdown()
    }
  }
  document.addEventListener('click', _clickHandler)
})

onUnmounted(() => {
  if (_clickHandler) {
    document.removeEventListener('click', _clickHandler)
    _clickHandler = null
  }
})
</script>

<template>
  <div class="relative notification-bell-wrapper" @keydown="handleDropdownKeydown">
    <button
      data-notification-trigger
      @click="toggleDropdown"
      class="relative p-2 text-muted hover:text-foreground focus:outline-none transition"
      :aria-label="t('aria.notifications')"
      :aria-expanded="dropdownOpen"
    >
      <Bell class="w-5 h-5" aria-hidden="true" />
      <span
        v-if="notifStore.unreadCount > 0"
        class="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[11px] font-bold text-white bg-danger-500 rounded-full"
      >
        {{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}
      </span>
    </button>

    <!-- Dropdown -->
    <div
      v-if="dropdownOpen"
      class="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-surface border border-border rounded-lg shadow-lg z-50"
    >
      <div class="flex items-center justify-between px-4 py-2 border-b border-border">
        <span class="text-sm font-semibold text-foreground">{{ t('notifications.title') }}</span>
        <button
          v-if="notifStore.unreadCount > 0"
          @click="notifStore.markAllRead()"
          class="text-xs text-brand-600 hover:text-brand-700 transition"
          tabindex="-1"
        >
          {{ t('notifications.markAllRead') }}
        </button>
      </div>

      <div v-if="notifStore.loading" class="px-4 py-6 text-center text-sm text-muted">
        {{ t('common.loading') }}
      </div>

      <div
        v-else-if="notifStore.items.length === 0"
        class="px-4 py-6 text-center text-sm text-muted"
      >
        {{ t('notifications.emptyMessage') }}
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <button
          v-for="notif in notifStore.items"
          :key="notif.id"
          @click="markRead(notif)"
          class="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-alt border-b border-surface-alt last:border-0 transition"
          :class="{ 'bg-brand-50/50': !notif.is_read }"
          tabindex="-1"
        >
          <div
            class="shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden"
          >
            <img
              v-if="notif.trigger_user?.avatar_url && !avatarFailed[notif.id]"
              :src="notif.trigger_user.avatar_url"
              class="w-8 h-8 rounded-full object-cover"
              :alt="`${notif.trigger_user.display_name}'s avatar`"
              @error="avatarFailed[notif.id] = true"
            />
            <span
              v-else-if="
                notif.trigger_user?.display_name &&
                (!notif.trigger_user.avatar_url || avatarFailed[notif.id])
              "
              class="text-xs font-semibold text-muted"
              >{{ notif.trigger_user.display_name.charAt(0).toUpperCase() }}</span
            >
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
          tabindex="-1"
        >
          {{ t('notifications.viewAll') }}
        </router-link>
      </div>
    </div>
  </div>
</template>
