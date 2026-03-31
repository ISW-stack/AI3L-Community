import api from '@/composables/api'
import { assertShape } from '@/utils/apiValidation'
import type { Event, EventListResponse } from '@/types'

export async function listEvents(params: {
  page?: number
  page_size?: number
  sig_id?: string
}) {
  const { data } = await api.get('/events', { params })
  return assertShape<EventListResponse>(data, ['events', 'total'], 'listEvents')
}

export async function getEvent(eventId: string) {
  const { data } = await api.get(`/events/${eventId}`)
  return assertShape<Event>(data, ['id', 'title'], 'getEvent')
}

export async function createEvent(payload: {
  title: string
  content: string
  sig_id?: string
  visibility: string[]
  allow_comments?: boolean
}) {
  const { data } = await api.post('/events', payload)
  return data as Event
}

export async function updateEvent(
  eventId: string,
  payload: {
    title?: string
    content?: string
    sig_id?: string | null
    visibility?: string[]
    allow_comments?: boolean
    version: number
  },
) {
  const { data } = await api.put(`/events/${eventId}`, payload)
  return data as Event
}

export async function deleteEvent(eventId: string) {
  await api.delete(`/events/${eventId}`)
}

export async function toggleEventReaction(eventId: string, reaction: string) {
  const { data } = await api.post(`/events/${eventId}/reactions`, { reaction })
  return data as Event
}

export async function listEventComments(
  eventId: string,
  params: { page?: number; page_size?: number; root_only?: boolean; sort?: string },
) {
  const { data } = await api.get(`/events/${eventId}/comments`, { params })
  return data
}

export async function createEventComment(
  eventId: string,
  payload: { content: string; parent_id?: string; mentions?: string[] },
) {
  const { data } = await api.post(`/events/${eventId}/comments`, payload)
  return data
}

export async function deleteEventComment(eventId: string, commentId: string) {
  await api.delete(`/events/${eventId}/comments/${commentId}`)
}
