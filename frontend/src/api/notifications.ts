import api from '@/composables/api'
import type { Notification } from '@/types'

export interface NotificationsListResponse {
  notifications: Notification[]
  total: number
  unread_count: number
}

export async function listNotifications(params: {
  page?: number
  page_size?: number
  unread?: boolean
}) {
  const { data } = await api.get('/notifications', { params })
  return data as NotificationsListResponse
}

export async function markRead(notificationId: string) {
  await api.put(`/notifications/${notificationId}/read`)
}

export async function markAllRead() {
  await api.put('/notifications/read-all')
}

export async function getUnreadCount() {
  const { data } = await api.get('/notifications', {
    params: { unread: true, page_size: 0 },
  })
  return data.unread_count as number
}
