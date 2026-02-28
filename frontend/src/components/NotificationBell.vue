<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/composables/api'

interface TriggerUser {
  id: string
  display_name: string
  avatar_url: string | null
}

interface Notification {
  id: string
  action_type: string
  entity_type: string | null
  entity_id: string | null
  message: string
  is_read: boolean
  created_at: string
  trigger_user: TriggerUser | null
}

const router = useRouter()
const unreadCount = ref(0)
const notifications = ref<Notification[]>([])
const dropdownOpen = ref(false)
const loading = ref(false)

async function fetchUnreadCount() {
  try {
    const { data } = await api.get('/notifications', {
      params: { unread: true, page_size: 0 },
    })
    unreadCount.value = data.unread_count
  } catch {
    // silent
  }
}

async function fetchRecent() {
  if (loading.value) return
  loading.value = true
  try {
    const { data } = await api.get('/notifications', {
      params: { page: 1, page_size: 10 },
    })
    notifications.value = data.notifications
    unreadCount.value = data.unread_count
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
  if (dropdownOpen.value) {
    fetchRecent()
  }
}

function closeDropdown() {
  dropdownOpen.value = false
}

async function markRead(notif: Notification) {
  if (!notif.is_read) {
    try {
      await api.put(`/notifications/${notif.id}/read`)
      notif.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch {
      // silent
    }
  }
  navigateToEntity(notif)
  closeDropdown()
}

async function markAllRead() {
  try {
    await api.put('/notifications/read-all')
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
  } catch {
    // silent
  }
}

function navigateToEntity(notif: Notification) {
  if (notif.entity_type === 'comment' && notif.entity_id) {
    // Navigate to the post containing this comment - entity_id is the comment id
    // For now, navigate to notifications page since we don't have the post_id
    router.push('/notifications')
  } else if (notif.entity_type === 'post' && notif.entity_id) {
    router.push(`/forum/${notif.entity_id}`)
  } else {
    router.push('/notifications')
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

function handleNewNotification(e: Event) {
  const detail = (e as CustomEvent).detail
  if (detail) {
    unreadCount.value++
    // Prepend to list if dropdown is open
    if (dropdownOpen.value) {
      notifications.value.unshift(detail)
      if (notifications.value.length > 10) {
        notifications.value.pop()
      }
    }
  }
}

function handleClickOutside(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest('.notification-bell-wrapper')
  if (!el) {
    closeDropdown()
  }
}

onMounted(() => {
  fetchUnreadCount()
  window.addEventListener('app:notification', handleNewNotification)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('app:notification', handleNewNotification)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="relative notification-bell-wrapper">
    <button
      @click="toggleDropdown"
      class="relative p-1 text-gray-500 hover:text-gray-700 focus:outline-none"
      aria-label="Notifications"
    >
      <!-- Bell icon (SVG) -->
      <svg
        class="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        stroke-width="1.5"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
        />
      </svg>
      <!-- Badge -->
      <span
        v-if="unreadCount > 0"
        class="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- Dropdown -->
    <div
      v-if="dropdownOpen"
      class="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50"
    >
      <div class="flex items-center justify-between px-4 py-2 border-b border-gray-100">
        <span class="text-sm font-semibold text-gray-800">Notifications</span>
        <button
          v-if="unreadCount > 0"
          @click="markAllRead"
          class="text-xs text-blue-600 hover:text-blue-800"
        >
          Mark all as read
        </button>
      </div>

      <div v-if="loading" class="px-4 py-6 text-center text-sm text-gray-400">
        Loading...
      </div>

      <div v-else-if="notifications.length === 0" class="px-4 py-6 text-center text-sm text-gray-400">
        No notifications yet.
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <button
          v-for="notif in notifications"
          :key="notif.id"
          @click="markRead(notif)"
          class="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-50 last:border-0"
          :class="{ 'bg-blue-50/50': !notif.is_read }"
        >
          <!-- Avatar or system icon -->
          <div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden">
            <img
              v-if="notif.trigger_user?.avatar_url"
              :src="notif.trigger_user.avatar_url"
              class="w-8 h-8 rounded-full object-cover"
              alt=""
            />
            <svg
              v-else
              class="w-4 h-4 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              stroke-width="1.5"
            >
              <path
                v-if="notif.action_type === 'SYSTEM'"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"
              />
              <path
                v-if="notif.action_type === 'SYSTEM'"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
              <path
                v-else
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
              />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-800 leading-snug">{{ notif.message }}</p>
            <p class="text-xs text-gray-400 mt-0.5">{{ relativeTime(notif.created_at) }}</p>
          </div>
          <div
            v-if="!notif.is_read"
            class="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-2"
          ></div>
        </button>
      </div>

      <div class="border-t border-gray-100">
        <router-link
          to="/notifications"
          @click="closeDropdown"
          class="block text-center text-sm text-blue-600 hover:text-blue-800 py-2"
        >
          View All
        </router-link>
      </div>
    </div>
  </div>
</template>
