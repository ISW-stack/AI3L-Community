import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

vi.mock('@/utils/apiValidation', () => ({
  assertShape: <T>(data: T) => data,
}))

import {
  listEvents,
  getEvent,
  createEvent,
  updateEvent,
  deleteEvent,
  toggleEventReaction,
  listEventComments,
  createEventComment,
  deleteEventComment,
} from '../events'

describe('events API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listEvents calls GET /events with params', async () => {
    const mockData = { events: [], total: 0, page: 1, total_pages: 1 }
    mockGet.mockResolvedValue({ data: mockData })

    const result = await listEvents({ page: 1, page_size: 20 })

    expect(mockGet).toHaveBeenCalledWith('/events', { params: { page: 1, page_size: 20 } })
    expect(result).toEqual(mockData)
  })

  it('listEvents passes sig_id param', async () => {
    const mockData = { events: [], total: 0, page: 1, total_pages: 1 }
    mockGet.mockResolvedValue({ data: mockData })

    await listEvents({ page: 1, sig_id: 'sig-123' })

    expect(mockGet).toHaveBeenCalledWith('/events', {
      params: { page: 1, sig_id: 'sig-123' },
    })
  })

  it('getEvent calls GET /events/:id', async () => {
    const mockData = { id: 'ev-1', title: 'Test' }
    mockGet.mockResolvedValue({ data: mockData })

    const result = await getEvent('ev-1')

    expect(mockGet).toHaveBeenCalledWith('/events/ev-1')
    expect(result).toEqual(mockData)
  })

  it('createEvent calls POST /events', async () => {
    const payload = {
      title: 'New Event',
      content: '<p>Hi</p>',
      visibility: ['MEMBER'],
    }
    const mockData = { id: 'ev-1', ...payload }
    mockPost.mockResolvedValue({ data: mockData })

    const result = await createEvent(payload)

    expect(mockPost).toHaveBeenCalledWith('/events', payload)
    expect(result).toEqual(mockData)
  })

  it('updateEvent calls PUT /events/:id', async () => {
    const payload = { title: 'Updated', version: 1 }
    const mockData = { id: 'ev-1', title: 'Updated' }
    mockPut.mockResolvedValue({ data: mockData })

    const result = await updateEvent('ev-1', payload)

    expect(mockPut).toHaveBeenCalledWith('/events/ev-1', payload)
    expect(result).toEqual(mockData)
  })

  it('deleteEvent calls DELETE /events/:id', async () => {
    mockDelete.mockResolvedValue({})

    await deleteEvent('ev-1')

    expect(mockDelete).toHaveBeenCalledWith('/events/ev-1')
  })

  it('toggleEventReaction calls POST /events/:id/reactions', async () => {
    const mockData = { id: 'ev-1', reaction_counts: { LIKE: 1 } }
    mockPost.mockResolvedValue({ data: mockData })

    const result = await toggleEventReaction('ev-1', 'LIKE')

    expect(mockPost).toHaveBeenCalledWith('/events/ev-1/reactions', { reaction: 'LIKE' })
    expect(result).toEqual(mockData)
  })

  it('listEventComments calls GET /events/:id/comments', async () => {
    const mockData = { comments: [], total: 0 }
    mockGet.mockResolvedValue({ data: mockData })

    const result = await listEventComments('ev-1', { page: 1 })

    expect(mockGet).toHaveBeenCalledWith('/events/ev-1/comments', { params: { page: 1 } })
    expect(result).toEqual(mockData)
  })

  it('createEventComment calls POST /events/:id/comments', async () => {
    const payload = { content: 'Nice!' }
    const mockData = { id: 'c-1', content: 'Nice!' }
    mockPost.mockResolvedValue({ data: mockData })

    const result = await createEventComment('ev-1', payload)

    expect(mockPost).toHaveBeenCalledWith('/events/ev-1/comments', payload)
    expect(result).toEqual(mockData)
  })

  it('deleteEventComment calls DELETE /events/:id/comments/:commentId', async () => {
    mockDelete.mockResolvedValue({})

    await deleteEventComment('ev-1', 'c-1')

    expect(mockDelete).toHaveBeenCalledWith('/events/ev-1/comments/c-1')
  })
})
