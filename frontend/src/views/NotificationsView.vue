<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Settings } from 'lucide-vue-next'
import type { Notification } from '@/types'
import { listNotifications, markRead as apiMarkRead, markAllRead as apiMarkAllRead } from '@/api/notifications'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const router = useRouter()
const notifications = ref<Notification[]>([])
const total = ref(0)
const unreadCount = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const totalPages = ref(1)

async function fetchNotifications() {
  loading.value = true
  try {
    const data = await listNotifications({ page: page.value, page_size: pageSize })
    notifications.value = data.notifications
    total.value = data.total
    unreadCount.value = data.unread_count
    totalPages.value = Math.max(1, Math.ceil(data.total / pageSize))
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

async function markRead(notif: Notification) {
  if (!notif.is_read) {
    try {
      await apiMarkRead(notif.id)
      notif.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch { /* silent */ }
  }
  navigateToEntity(notif)
}

async function markAllRead() {
  try {
    await apiMarkAllRead()
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
  } catch { /* silent */ }
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

function goToPage(p: number) {
  page.value = p
  fetchNotifications()
}

onMounted(fetchNotifications)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Notifications</h1>
      <button
        v-if="unreadCount > 0"
        @click="markAllRead"
        class="text-sm text-brand-600 hover:text-brand-800 hover:underline"
      >
        Mark all as read ({{ unreadCount }})
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState v-else-if="notifications.length === 0" message="No notifications yet." title="All Caught Up" />

    <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
      <button
        v-for="notif in notifications"
        :key="notif.id"
        @click="markRead(notif)"
        class="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-surface-alt transition"
        :class="{ 'bg-brand-50/40': !notif.is_read }"
      >
        <!-- Avatar -->
        <div class="flex-shrink-0 w-10 h-10 rounded-full bg-surface-alt flex items-center justify-center overflow-hidden border border-border">
          <img
            v-if="notif.trigger_user?.avatar_url"
            :src="notif.trigger_user.avatar_url"
            class="w-10 h-10 rounded-full object-cover"
            alt=""
          />
          <component :is="notif.action_type === 'SYSTEM' ? Settings : User" v-else class="w-5 h-5 text-muted" />
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <p class="text-sm text-foreground">{{ notif.message }}</p>
          <p class="text-xs text-muted mt-1">{{ relativeTime(notif.created_at) }}</p>
        </div>

        <!-- Unread dot -->
        <div
          v-if="!notif.is_read"
          class="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-brand-600 mt-2"
        ></div>
      </button>
    </div>

    <BasePagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      @update:current-page="goToPage"
      class="mt-6"
    />
  </div>
</template>
