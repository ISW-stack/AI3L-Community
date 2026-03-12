import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Notification } from '@/types/notification'
import {
  listNotifications,
  markRead as apiMarkRead,
  markAllRead as apiMarkAllRead,
} from '@/api/notifications'

export const useNotificationStore = defineStore('notifications', () => {
  const unreadCount = ref(0)
  const items = ref<Notification[]>([])
  const loading = ref(false)

  async function fetchUnreadCount() {
    try {
      const data = await listNotifications({ unread: true, page_size: 1 })
      unreadCount.value = data.unread_count
    } catch {
      // silent
    }
  }

  async function fetchRecent(page = 1, pageSize = 10) {
    if (loading.value) return
    loading.value = true
    try {
      const data = await listNotifications({ page, page_size: pageSize })
      items.value = data.notifications
      unreadCount.value = data.unread_count
    } catch {
      // silent
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string) {
    try {
      await apiMarkRead(id)
      const notif = items.value.find((n) => n.id === id)
      if (notif && !notif.is_read) {
        notif.is_read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch {
      // silent
    }
  }

  async function markAllRead() {
    try {
      await apiMarkAllRead()
      items.value.forEach((n) => (n.is_read = true))
      unreadCount.value = 0
    } catch {
      // silent
    }
  }

  function addFromWebSocket(notification: Notification) {
    unreadCount.value++
    items.value.unshift(notification)
    if (items.value.length > 10) {
      items.value.pop()
    }
  }

  function resetState() {
    unreadCount.value = 0
    items.value = []
    loading.value = false
  }

  return {
    unreadCount,
    items,
    loading,
    fetchUnreadCount,
    fetchRecent,
    markRead,
    markAllRead,
    addFromWebSocket,
    resetState,
  }
})
