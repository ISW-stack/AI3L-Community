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

import {
  getForm,
  createForm,
  updateForm,
  deleteForm,
  submitForm,
  exportForm,
  listFormResponses,
} from '../forms'

describe('forms API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getForm', () => {
    it('calls GET /forms/{formId} and returns data', async () => {
      const formId = 'form-1'
      const mockData = { id: formId, title: 'Test Form' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getForm(formId)

      expect(mockGet).toHaveBeenCalledWith(`/forms/${formId}`)
      expect(result).toEqual(mockData)
    })
  })

  describe('createForm', () => {
    it('calls POST /sigs/{sigId}/forms with payload and returns data', async () => {
      const sigId = 'sig-1'
      const payload = {
        title: 'New Form',
        description: 'A form',
        banner_url: null,
        deadline: null,
        max_respondents: null,
        questions: [],
        allow_non_members: false,
      }
      const mockData = { id: 'new-form', ...payload }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createForm(sigId, payload)

      expect(mockPost).toHaveBeenCalledWith(`/sigs/${sigId}/forms`, payload)
      expect(result).toEqual(mockData)
    })
  })

  describe('updateForm', () => {
    it('calls PUT /forms/{formId} with payload and returns data', async () => {
      const formId = 'form-upd'
      const payload = { title: 'Updated Title', questions: [] }
      const mockData = { id: formId, title: 'Updated Title' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updateForm(formId, payload)

      expect(mockPut).toHaveBeenCalledWith(`/forms/${formId}`, payload)
      expect(result).toEqual(mockData)
    })

    it('supports partial payload update', async () => {
      const formId = 'form-partial'
      const payload = { deadline: '2026-12-31' }
      mockPut.mockResolvedValue({ data: { id: formId } })

      await updateForm(formId, payload)

      expect(mockPut).toHaveBeenCalledWith(`/forms/${formId}`, payload)
    })
  })

  describe('deleteForm', () => {
    it('calls DELETE /forms/{formId} and returns undefined', async () => {
      mockDelete.mockResolvedValue({})
      const formId = 'form-del'

      const result = await deleteForm(formId)

      expect(mockDelete).toHaveBeenCalledWith(`/forms/${formId}`)
      expect(result).toBeUndefined()
    })
  })

  describe('submitForm', () => {
    it('calls POST /forms/{formId}/submit with answers wrapped in object', async () => {
      const formId = 'form-sub'
      const answers = { q1: 'Answer 1', q2: 42 }
      mockPost.mockResolvedValue({})

      const result = await submitForm(formId, answers)

      expect(mockPost).toHaveBeenCalledWith(`/forms/${formId}/submit`, { answers })
      expect(result).toBeUndefined()
    })
  })

  describe('exportForm', () => {
    it('calls POST /forms/{formId}/export and returns task_id', async () => {
      const formId = 'form-exp'
      const mockData = { task_id: 'task-abc' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await exportForm(formId)

      expect(mockPost).toHaveBeenCalledWith(`/forms/${formId}/export`)
      expect(result).toEqual(mockData)
    })
  })

  describe('listFormResponses', () => {
    it('calls GET /forms/{formId}/responses with default page/pageSize', async () => {
      const formId = 'form-resp'
      const mockData = { responses: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listFormResponses(formId)

      expect(mockGet).toHaveBeenCalledWith(`/forms/${formId}/responses`, {
        params: { page: 1, page_size: 20 },
      })
      expect(result).toEqual(mockData)
    })

    it('calls GET /forms/{formId}/responses with custom page and pageSize', async () => {
      const formId = 'form-resp-custom'
      mockGet.mockResolvedValue({ data: { responses: [], total: 0 } })

      await listFormResponses(formId, 2, 50)

      expect(mockGet).toHaveBeenCalledWith(`/forms/${formId}/responses`, {
        params: { page: 2, page_size: 50 },
      })
    })
  })
})
