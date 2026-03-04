<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Settings, Trash2 } from 'lucide-vue-next'
import type { Notification } from '@/types'
import {
  listNotifications,
  markRead as apiMarkRead,
  markAllRead as apiMarkAllRead,
  deleteNotification,
  bulkDeleteNotifications,
} from '@/api/notifications'
import { relativeTime } from '@/utils/datetime'
import { useToastStore } from '@/stores/toast'
import { useNotificationStore } from '@/stores/notifications'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const router = useRouter()
const toast = useToastStore()
const notificationStore = useNotificationStore()
const notifications = ref<Notification[]>([])
const total = ref(0)
const unreadCount = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const totalPages = ref(1)
const filter = ref<'all' | 'unread'>('all')

const filteredNotifications = computed(() => {
  if (filter.value === 'unread') return notifications.value.filter((n) => !n.is_read)
  return notifications.value
})

function changeFilter(f: 'all' | 'unread') {
  filter.value = f
}

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
    } catch {
      /* silent */
    }
  }
  navigateToEntity(notif)
}

async function markAllRead() {
  try {
    await apiMarkAllRead()
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
  } catch {
    /* silent */
  }
}

function navigateToEntity(notif: Notification) {
  if (!notif.entity_id) return
  if (notif.entity_type === 'post') {
    router.push(`/forum/${notif.entity_id}`)
  } else if (notif.entity_type === 'comment') {
    // For comment notifications, entity_id is typically the post_id
    // Navigate to the post so the user can see the comment in context
    router.push(`/forum/${notif.entity_id}`)
  }
}

async function handleDeleteNotification(id: string) {
  try {
    await deleteNotification(id)
    notifications.value = notifications.value.filter((n) => n.id !== id)
    notificationStore.fetchUnreadCount()
  } catch {
    toast.show('Failed to delete notification.', 'error')
  }
}

async function handleClearAll() {
  try {
    await bulkDeleteNotifications()
    notifications.value = []
    notificationStore.fetchUnreadCount()
    toast.show('All notifications cleared.', 'success')
  } catch {
    toast.show('Failed to clear notifications.', 'error')
  }
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
      <div class="flex items-center gap-3">
        <button
          v-if="unreadCount > 0"
          @click="markAllRead"
          class="text-sm text-brand-600 hover:text-brand-800 hover:underline"
        >
          Mark all as read ({{ unreadCount }})
        </button>
        <BaseButton
          v-if="notifications.length > 0"
          variant="soft-danger"
          size="sm"
          @click="handleClearAll"
        >
          Clear All
        </BaseButton>
      </div>
    </div>

    <!-- Filter Tabs -->
    <div class="flex gap-1 mb-4 border-b border-border">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          filter === 'all'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="changeFilter('all')"
      >
        All
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          filter === 'unread'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="changeFilter('unread')"
      >
        Unread
        <span
          v-if="unreadCount > 0"
          class="ml-1 text-xs bg-brand-100 text-brand-700 rounded-full px-1.5"
          >{{ unreadCount }}</span
        >
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="filteredNotifications.length === 0"
      message="No notifications yet."
      title="All Caught Up"
    />

    <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
      <button
        v-for="notif in filteredNotifications"
        :key="notif.id"
        @click="markRead(notif)"
        class="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-surface-alt transition"
        :class="{ 'bg-brand-50/40': !notif.is_read }"
      >
        <!-- Avatar -->
        <div
          class="flex-shrink-0 w-10 h-10 rounded-full bg-surface-alt flex items-center justify-center overflow-hidden border border-border"
        >
          <img
            v-if="notif.trigger_user?.avatar_url"
            :src="notif.trigger_user.avatar_url"
            class="w-10 h-10 rounded-full object-cover"
            alt=""
          />
          <component
            :is="notif.action_type === 'SYSTEM' ? Settings : User"
            v-else
            class="w-5 h-5 text-muted"
          />
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

        <!-- Delete button -->
        <button
          @click.stop="handleDeleteNotification(notif.id)"
          class="flex-shrink-0 p-1 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
          title="Delete notification"
        >
          <Trash2 :size="16" />
        </button>
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
