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

export const deleteNotification = (notificationId: string) =>
  api.delete(`/notifications/${notificationId}`)

export const bulkDeleteNotifications = (notificationIds?: string[]) =>
  api.delete('/notifications', {
    data: notificationIds ? { notification_ids: notificationIds } : undefined,
  })
