import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock API modules
vi.mock('@/api/forms', () => ({
  getForm: vi.fn(),
  listFormResponses: vi.fn(),
  getFormStats: vi.fn(),
}))

import { useFormResponseViewer } from '../useFormResponseViewer'
import { getForm, listFormResponses, getFormStats } from '@/api/forms'

const mockGetForm = getForm as ReturnType<typeof vi.fn>
const mockListFormResponses = listFormResponses as ReturnType<typeof vi.fn>
const mockGetFormStats = getFormStats as ReturnType<typeof vi.fn>

describe('useFormResponseViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---------- F-29: stats validation ----------

  describe('stats runtime validation (F-29)', () => {
    it('handles valid question_stats array correctly', async () => {
      mockGetForm.mockResolvedValue({
        questions: [{ id: 'q1', type: 'text', label: 'Name', required: true, options: [] }],
      })
      mockListFormResponses.mockResolvedValue({ responses: [], total: 0 })
      mockGetFormStats.mockResolvedValue({
        question_stats: [
          {
            question_id: 'q1',
            question_label: 'Name',
            stats: { type: 'text', totalResponses: 5, answers: ['a', 'b'] },
          },
        ],
      })

      const { formStats, fetchResponses } = useFormResponseViewer()
      await fetchResponses('form-1')

      expect(formStats.value).toHaveLength(1)
      expect(formStats.value[0].questionId).toBe('q1')
      expect(formStats.value[0].label).toBe('Name')
    })

    it('sets empty array when question_stats is not an array', async () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      mockGetForm.mockResolvedValue({
        questions: [{ id: 'q1', type: 'text', label: 'Name', required: true, options: [] }],
      })
      mockListFormResponses.mockResolvedValue({ responses: [], total: 0 })
      mockGetFormStats.mockResolvedValue({
        question_stats: 'not-an-array',
      })

      const { formStats, fetchResponses } = useFormResponseViewer()
      await fetchResponses('form-1')

      expect(formStats.value).toEqual([])
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('Expected question_stats to be an array'),
        'string',
      )

      warnSpy.mockRestore()
    })

    it('filters out invalid stat entries and logs warning', async () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      mockGetForm.mockResolvedValue({
        questions: [
          { id: 'q1', type: 'text', label: 'Name', required: true, options: [] },
          { id: 'q2', type: 'text', label: 'Email', required: true, options: [] },
        ],
      })
      mockListFormResponses.mockResolvedValue({ responses: [], total: 0 })
      mockGetFormStats.mockResolvedValue({
        question_stats: [
          {
            question_id: 'q1',
            question_label: 'Name',
            stats: { type: 'text', totalResponses: 5, answers: [] },
          },
          // Invalid entry: missing stats
          { question_id: 'q2', question_label: 'Email' },
          // Invalid entry: null
          null,
        ],
      })

      const { formStats, fetchResponses } = useFormResponseViewer()
      await fetchResponses('form-1')

      // Only the valid entry should remain
      expect(formStats.value).toHaveLength(1)
      expect(formStats.value[0].questionId).toBe('q1')
      expect(warnSpy).toHaveBeenCalled()

      warnSpy.mockRestore()
    })

    it('handles null statsData gracefully', async () => {
      mockGetForm.mockResolvedValue({
        questions: [{ id: 'q1', type: 'text', label: 'Name', required: true, options: [] }],
      })
      mockListFormResponses.mockResolvedValue({ responses: [], total: 0 })
      mockGetFormStats.mockRejectedValue(new Error('stats error'))

      const { formStats, fetchResponses } = useFormResponseViewer()
      await fetchResponses('form-1')

      // formStats should remain at default empty array
      expect(formStats.value).toEqual([])
    })
  })
})
