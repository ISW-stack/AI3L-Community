<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/composables/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

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
const notifications = ref<Notification[]>([])
const total = ref(0)
const unreadCount = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

async function fetchNotifications() {
  loading.value = true
  try {
    const { data } = await api.get('/notifications', {
      params: { page: page.value, page_size: pageSize },
    })
    notifications.value = data.notifications
    total.value = data.total
    unreadCount.value = data.unread_count
  } catch {
    // silent
  } finally {
    loading.value = false
  }
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
  if (notif.entity_type === 'post' && notif.entity_id) {
    router.push(`/forum/${notif.entity_id}`)
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

const totalPages = ref(1)

function updateTotalPages() {
  totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
}

async function goToPage(p: number) {
  page.value = p
  await fetchNotifications()
  updateTotalPages()
}

onMounted(async () => {
  await fetchNotifications()
  updateTotalPages()
})
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Notifications</h1>
      <button
        v-if="unreadCount > 0"
        @click="markAllRead"
        class="text-sm text-blue-600 hover:text-blue-800"
      >
        Mark all as read ({{ unreadCount }})
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState v-else-if="notifications.length === 0" message="No notifications yet." title="All Caught Up" />

    <div v-else class="bg-white rounded-xl shadow border border-gray-200 divide-y divide-gray-100">
      <button
        v-for="notif in notifications"
        :key="notif.id"
        @click="markRead(notif)"
        class="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-gray-50 transition"
        :class="{ 'bg-blue-50/40': !notif.is_read }"
      >
        <!-- Avatar -->
        <div class="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden">
          <img
            v-if="notif.trigger_user?.avatar_url"
            :src="notif.trigger_user.avatar_url"
            class="w-10 h-10 rounded-full object-cover"
            alt=""
          />
          <svg
            v-else
            class="w-5 h-5 text-gray-500"
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

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <p class="text-sm text-gray-800">{{ notif.message }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ relativeTime(notif.created_at) }}</p>
        </div>

        <!-- Unread dot -->
        <div
          v-if="!notif.is_read"
          class="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-blue-500 mt-2"
        ></div>
      </button>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex justify-center gap-2 mt-6">
      <button
        v-for="p in totalPages"
        :key="p"
        @click="goToPage(p)"
        class="px-3 py-1 text-sm rounded-lg border"
        :class="p === page
          ? 'bg-blue-600 text-white border-blue-600'
          : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'"
      >
        {{ p }}
      </button>
    </div>
  </div>
</template>
