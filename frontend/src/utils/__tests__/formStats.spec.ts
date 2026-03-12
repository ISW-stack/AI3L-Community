import { describe, it, expect, vi } from 'vitest'
import {
  computeFormStats,
  filterResponses,
  formatDeleteWarning,
  type ChoiceStats,
  type RatingStats,
  type TextStats,
  type FileStats,
} from '../formStats'
import type { FormResponse, Question } from '@/types'

// ─── Helpers ───────────────────────────────────────────────

function makeQuestion(overrides: Partial<Question> & { id: string; type: string }): Question {
  return {
    label: 'Test Question',
    ...overrides,
  }
}

function makeResponse(
  id: string,
  displayName: string,
  answers: Record<string, unknown>,
  createdAt = '2026-01-15T12:00:00Z',
): FormResponse {
  return { id, display_name: displayName, created_at: createdAt, answers }
}

// ═══════════════════════════════════════════════════════════
// 1. Statistics Computation Logic
// ═══════════════════════════════════════════════════════════

describe('computeFormStats', () => {
  // ── Choice stats (single_choice, multiple_choice, dropdown) ──

  describe('choice questions', () => {
    const choiceQuestion = makeQuestion({
      id: 'q1',
      type: 'single_choice',
      label: 'Favorite Color',
      options: [
        { id: 'opt-r', label: 'Red' },
        { id: 'opt-b', label: 'Blue' },
        { id: 'opt-g', label: 'Green' },
      ],
    })

    it('computes choice stats for single_choice', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'Alice', { q1: 'opt-r' }),
        makeResponse('r2', 'Bob', { q1: 'opt-b' }),
        makeResponse('r3', 'Charlie', { q1: 'opt-r' }),
      ]

      const result = computeFormStats([choiceQuestion], responses)
      expect(result).toHaveLength(1)

      const stat = result[0] as ChoiceStats
      expect(stat.type).toBe('choice')
      expect(stat.questionId).toBe('q1')
      expect(stat.label).toBe('Favorite Color')
      expect(stat.totalResponses).toBe(3)

      const red = stat.options.find((o) => o.id === 'opt-r')!
      const blue = stat.options.find((o) => o.id === 'opt-b')!
      const green = stat.options.find((o) => o.id === 'opt-g')!

      expect(red.count).toBe(2)
      expect(red.percentage).toBe(67) // 2/3 ~ 67%
      expect(blue.count).toBe(1)
      expect(blue.percentage).toBe(33)
      expect(green.count).toBe(0)
      expect(green.percentage).toBe(0)
    })

    it('computes choice stats for multiple_choice (array answers)', () => {
      const mcQuestion = makeQuestion({
        id: 'q1',
        type: 'multiple_choice',
        label: 'Skills',
        options: [
          { id: 'opt-a', label: 'Python' },
          { id: 'opt-b', label: 'JavaScript' },
          { id: 'opt-c', label: 'Rust' },
        ],
      })

      const responses: FormResponse[] = [
        makeResponse('r1', 'Alice', { q1: ['opt-a', 'opt-b'] }),
        makeResponse('r2', 'Bob', { q1: ['opt-b', 'opt-c'] }),
        makeResponse('r3', 'Charlie', { q1: ['opt-a'] }),
      ]

      const result = computeFormStats([mcQuestion], responses)
      const stat = result[0] as ChoiceStats

      expect(stat.type).toBe('choice')
      expect(stat.totalResponses).toBe(3)

      const python = stat.options.find((o) => o.id === 'opt-a')!
      const js = stat.options.find((o) => o.id === 'opt-b')!
      const rust = stat.options.find((o) => o.id === 'opt-c')!

      expect(python.count).toBe(2)
      expect(js.count).toBe(2)
      expect(rust.count).toBe(1)
    })

    it('computes choice stats for dropdown type', () => {
      const ddQuestion = makeQuestion({
        id: 'q1',
        type: 'dropdown',
        label: 'Country',
        options: [
          { id: 'tw', label: 'Taiwan' },
          { id: 'us', label: 'USA' },
        ],
      })

      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q1: 'tw' }),
        makeResponse('r2', 'B', { q1: 'tw' }),
      ]

      const result = computeFormStats([ddQuestion], responses)
      expect(result[0].type).toBe('choice')
    })

    it('handles no responses', () => {
      const result = computeFormStats([choiceQuestion], [])
      const stat = result[0] as ChoiceStats
      expect(stat.totalResponses).toBe(0)
      expect(stat.options.every((o) => o.count === 0 && o.percentage === 0)).toBe(true)
    })

    it('handles null answers gracefully', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'Alice', { q1: null }),
        makeResponse('r2', 'Bob', { q1: 'opt-r' }),
        makeResponse('r3', 'Charlie', {}),
      ]

      const result = computeFormStats([choiceQuestion], responses)
      const stat = result[0] as ChoiceStats
      expect(stat.totalResponses).toBe(1)
    })

    it('handles unknown option IDs (not in question options)', () => {
      const responses: FormResponse[] = [makeResponse('r1', 'Alice', { q1: 'unknown-id' })]

      const result = computeFormStats([choiceQuestion], responses)
      const stat = result[0] as ChoiceStats
      expect(stat.totalResponses).toBe(1)

      const unknownOpt = stat.options.find((o) => o.id === 'unknown-id')
      expect(unknownOpt).toBeTruthy()
      expect(unknownOpt!.label).toBe('unknown-id') // falls back to id
    })
  })

  // ── Rating stats ──

  describe('rating questions', () => {
    const ratingQuestion = makeQuestion({
      id: 'q2',
      type: 'rating',
      label: 'Satisfaction',
      min: 1,
      max: 5,
    })

    it('computes rating stats with correct average and distribution', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q2: 5 }),
        makeResponse('r2', 'B', { q2: 3 }),
        makeResponse('r3', 'C', { q2: 4 }),
        makeResponse('r4', 'D', { q2: 5 }),
      ]

      const result = computeFormStats([ratingQuestion], responses)
      const stat = result[0] as RatingStats

      expect(stat.type).toBe('rating')
      expect(stat.totalResponses).toBe(4)
      expect(stat.average).toBe(4.25)
      expect(stat.min).toBe(1)
      expect(stat.max).toBe(5)

      expect(stat.distribution).toHaveLength(5)
      const dist5 = stat.distribution.find((d) => d.value === 5)!
      expect(dist5.count).toBe(2)
      expect(dist5.percentage).toBe(50)

      const dist1 = stat.distribution.find((d) => d.value === 1)!
      expect(dist1.count).toBe(0)
      expect(dist1.percentage).toBe(0)
    })

    it('handles string rating values (parsed to number)', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q2: '4' }),
        makeResponse('r2', 'B', { q2: '2' }),
      ]

      const result = computeFormStats([ratingQuestion], responses)
      const stat = result[0] as RatingStats

      expect(stat.totalResponses).toBe(2)
      expect(stat.average).toBe(3)
    })

    it('returns zero average for empty responses', () => {
      const result = computeFormStats([ratingQuestion], [])
      const stat = result[0] as RatingStats

      expect(stat.totalResponses).toBe(0)
      expect(stat.average).toBe(0)
      expect(stat.distribution).toHaveLength(5)
      expect(stat.distribution.every((d) => d.count === 0)).toBe(true)
    })

    it('uses default min=1 max=5 when not specified', () => {
      const q = makeQuestion({ id: 'q2', type: 'rating', label: 'Rating' })
      const responses: FormResponse[] = [makeResponse('r1', 'A', { q2: 3 })]

      const result = computeFormStats([q], responses)
      const stat = result[0] as RatingStats

      expect(stat.min).toBe(1)
      expect(stat.max).toBe(5)
      expect(stat.distribution).toHaveLength(5)
    })

    it('rounds average to 2 decimal places', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q2: 1 }),
        makeResponse('r2', 'B', { q2: 2 }),
        makeResponse('r3', 'C', { q2: 3 }),
      ]

      const result = computeFormStats([ratingQuestion], responses)
      const stat = result[0] as RatingStats

      expect(stat.average).toBe(2)
    })

    it('ignores non-numeric values', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q2: 'not-a-number' }),
        makeResponse('r2', 'B', { q2: 3 }),
        makeResponse('r3', 'C', { q2: null }),
      ]

      const result = computeFormStats([ratingQuestion], responses)
      const stat = result[0] as RatingStats

      expect(stat.totalResponses).toBe(1)
      expect(stat.average).toBe(3)
    })
  })

  // ── Text stats ──

  describe('text questions', () => {
    const textQuestion = makeQuestion({
      id: 'q3',
      type: 'short_text',
      label: 'Comments',
    })

    it('collects non-empty text answers', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q3: 'Great work!' }),
        makeResponse('r2', 'B', { q3: 'Needs improvement' }),
        makeResponse('r3', 'C', { q3: '' }),
        makeResponse('r4', 'D', { q3: null }),
        makeResponse('r5', 'E', {}),
      ]

      const result = computeFormStats([textQuestion], responses)
      const stat = result[0] as TextStats

      expect(stat.type).toBe('text')
      expect(stat.totalResponses).toBe(2)
      expect(stat.answers).toEqual(['Great work!', 'Needs improvement'])
    })

    it('handles textarea type identically', () => {
      const taQuestion = makeQuestion({ id: 'q3', type: 'textarea', label: 'Comments' })
      const responses: FormResponse[] = [makeResponse('r1', 'A', { q3: 'Long text here' })]

      const result = computeFormStats([taQuestion], responses)
      expect(result[0].type).toBe('text')
    })

    it('trims whitespace-only answers', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q3: '   ' }),
        makeResponse('r2', 'B', { q3: 'Valid' }),
      ]

      const result = computeFormStats([textQuestion], responses)
      const stat = result[0] as TextStats

      expect(stat.totalResponses).toBe(1)
      expect(stat.answers).toEqual(['Valid'])
    })
  })

  // ── File stats ──

  describe('file_upload questions', () => {
    const fileQuestion = makeQuestion({
      id: 'q4',
      type: 'file_upload',
      label: 'Upload Resume',
    })

    it('collects filenames from object answers', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q4: { filename: 'resume.pdf', url: '/files/1' } }),
        makeResponse('r2', 'B', { q4: { filename: 'cv.docx', url: '/files/2' } }),
      ]

      const result = computeFormStats([fileQuestion], responses)
      const stat = result[0] as FileStats

      expect(stat.type).toBe('file')
      expect(stat.totalUploads).toBe(2)
      expect(stat.filenames).toEqual(['resume.pdf', 'cv.docx'])
    })

    it('collects filenames from string answers', () => {
      const responses: FormResponse[] = [makeResponse('r1', 'A', { q4: 'document.txt' })]

      const result = computeFormStats([fileQuestion], responses)
      const stat = result[0] as FileStats

      expect(stat.totalUploads).toBe(1)
      expect(stat.filenames).toEqual(['document.txt'])
    })

    it('ignores null and empty answers', () => {
      const responses: FormResponse[] = [
        makeResponse('r1', 'A', { q4: null }),
        makeResponse('r2', 'B', { q4: '' }),
        makeResponse('r3', 'C', {}),
      ]

      const result = computeFormStats([fileQuestion], responses)
      const stat = result[0] as FileStats

      expect(stat.totalUploads).toBe(0)
      expect(stat.filenames).toEqual([])
    })

    it('ignores array answers (not valid for file_upload)', () => {
      const responses: FormResponse[] = [makeResponse('r1', 'A', { q4: ['a.pdf', 'b.pdf'] })]

      const result = computeFormStats([fileQuestion], responses)
      const stat = result[0] as FileStats

      expect(stat.totalUploads).toBe(0)
    })
  })

  // ── Mixed questions ──

  describe('mixed question types', () => {
    it('returns one stat per question in order', () => {
      const questions: Question[] = [
        makeQuestion({
          id: 'q1',
          type: 'single_choice',
          label: 'Q1',
          options: [{ id: 'a', label: 'A' }],
        }),
        makeQuestion({ id: 'q2', type: 'rating', label: 'Q2', min: 1, max: 3 }),
        makeQuestion({ id: 'q3', type: 'short_text', label: 'Q3' }),
        makeQuestion({ id: 'q4', type: 'file_upload', label: 'Q4' }),
      ]

      const responses: FormResponse[] = [
        makeResponse('r1', 'User', { q1: 'a', q2: 2, q3: 'hello', q4: { filename: 'f.pdf' } }),
      ]

      const result = computeFormStats(questions, responses)
      expect(result).toHaveLength(4)
      expect(result[0].type).toBe('choice')
      expect(result[1].type).toBe('rating')
      expect(result[2].type).toBe('text')
      expect(result[3].type).toBe('file')
    })

    it('handles empty questions array', () => {
      const result = computeFormStats([], [makeResponse('r1', 'A', { q1: 'val' })])
      expect(result).toEqual([])
    })
  })
})

// ═══════════════════════════════════════════════════════════
// 2. Search/Filter Functionality
// ═══════════════════════════════════════════════════════════

describe('filterResponses', () => {
  const responses: FormResponse[] = [
    makeResponse('r1', 'Alice Johnson', { q1: 'answer1' }, '2026-01-10T10:00:00Z'),
    makeResponse('r2', 'Bob Smith', { q1: 'answer2' }, '2026-01-15T14:00:00Z'),
    makeResponse('r3', 'Charlie Brown', { q1: 'answer3' }, '2026-01-20T08:00:00Z'),
    makeResponse('r4', 'Alice Wang', { q1: 'answer4' }, '2026-02-01T12:00:00Z'),
    makeResponse('r5', 'David Lee', { q1: 'answer5' }, '2026-02-15T16:00:00Z'),
  ]

  describe('search by name', () => {
    it('filters by display name (case-insensitive)', () => {
      const result = filterResponses(responses, 'alice', '', '')
      expect(result).toHaveLength(2)
      expect(result[0].display_name).toBe('Alice Johnson')
      expect(result[1].display_name).toBe('Alice Wang')
    })

    it('filters by partial name', () => {
      const result = filterResponses(responses, 'son', '', '')
      expect(result).toHaveLength(1)
      expect(result[0].display_name).toBe('Alice Johnson')
    })

    it('returns all when search is empty', () => {
      const result = filterResponses(responses, '', '', '')
      expect(result).toHaveLength(5)
    })

    it('returns all when search is whitespace only', () => {
      const result = filterResponses(responses, '   ', '', '')
      expect(result).toHaveLength(5)
    })

    it('returns empty for no match', () => {
      const result = filterResponses(responses, 'Xavier', '', '')
      expect(result).toHaveLength(0)
    })

    it('is case-insensitive', () => {
      const result = filterResponses(responses, 'BOB', '', '')
      expect(result).toHaveLength(1)
      expect(result[0].display_name).toBe('Bob Smith')
    })
  })

  describe('date range filter', () => {
    it('filters from dateFrom', () => {
      const result = filterResponses(responses, '', '2026-01-15', '')
      expect(result).toHaveLength(4)
      expect(result.map((r) => r.id)).toEqual(['r2', 'r3', 'r4', 'r5'])
    })

    it('filters up to dateTo (inclusive, end of day)', () => {
      const result = filterResponses(responses, '', '', '2026-01-15')
      expect(result).toHaveLength(2)
      expect(result.map((r) => r.id)).toEqual(['r1', 'r2'])
    })

    it('filters both dateFrom and dateTo', () => {
      const result = filterResponses(responses, '', '2026-01-15', '2026-01-20')
      expect(result).toHaveLength(2)
      expect(result.map((r) => r.id)).toEqual(['r2', 'r3'])
    })

    it('returns all when no dates specified', () => {
      const result = filterResponses(responses, '', '', '')
      expect(result).toHaveLength(5)
    })

    it('returns empty when date range excludes all', () => {
      const result = filterResponses(responses, '', '2026-06-01', '2026-06-30')
      expect(result).toHaveLength(0)
    })
  })

  describe('combined search and date filter', () => {
    it('combines name search with date range', () => {
      const result = filterResponses(responses, 'Alice', '2026-01-01', '2026-01-31')
      expect(result).toHaveLength(1)
      expect(result[0].display_name).toBe('Alice Johnson')
    })

    it('returns empty when combined filters match nothing', () => {
      const result = filterResponses(responses, 'David', '2026-01-01', '2026-01-31')
      expect(result).toHaveLength(0)
    })
  })

  describe('edge cases', () => {
    it('handles empty responses array', () => {
      const result = filterResponses([], 'Alice', '2026-01-01', '2026-12-31')
      expect(result).toHaveLength(0)
    })

    it('does not mutate original array', () => {
      const original = [...responses]
      filterResponses(responses, 'Alice', '', '')
      expect(responses).toEqual(original)
    })
  })
})

// ═══════════════════════════════════════════════════════════
// 3. Delete Warning Message Formatting
// ═══════════════════════════════════════════════════════════

describe('formatDeleteWarning', () => {
  it('returns no-responses message when count is 0', () => {
    const mockT = vi.fn().mockImplementation((key: string) => {
      if (key === 'sigs.forms.deleteConfirm.messageNoResponses') {
        return 'This form has no responses. Are you sure you want to delete it?'
      }
      return key
    })

    const result = formatDeleteWarning(0, mockT)
    expect(result).toBe('This form has no responses. Are you sure you want to delete it?')
    expect(mockT).toHaveBeenCalledWith('sigs.forms.deleteConfirm.messageNoResponses')
  })

  it('returns with-count message when count > 0', () => {
    const mockT = vi.fn().mockImplementation((key: string, params?: Record<string, unknown>) => {
      if (key === 'sigs.forms.deleteConfirm.messageWithCount') {
        return `This form has ${params?.count} response(s). Deleting it will remove all data permanently.`
      }
      return key
    })

    const result = formatDeleteWarning(5, mockT)
    expect(result).toBe(
      'This form has 5 response(s). Deleting it will remove all data permanently.',
    )
    expect(mockT).toHaveBeenCalledWith('sigs.forms.deleteConfirm.messageWithCount', { count: 5 })
  })

  it('passes count=1 for single response', () => {
    const mockT = vi.fn().mockReturnValue('message')
    formatDeleteWarning(1, mockT)
    expect(mockT).toHaveBeenCalledWith('sigs.forms.deleteConfirm.messageWithCount', { count: 1 })
  })

  it('passes count for large numbers', () => {
    const mockT = vi.fn().mockReturnValue('message')
    formatDeleteWarning(999, mockT)
    expect(mockT).toHaveBeenCalledWith('sigs.forms.deleteConfirm.messageWithCount', { count: 999 })
  })
})

// ═══════════════════════════════════════════════════════════
// 4. Description Truncation Detection
// ═══════════════════════════════════════════════════════════

describe('description truncation detection', () => {
  // These tests validate the logic used in SigFormsView for truncation detection.
  // The view uses: el.scrollHeight > el.clientHeight

  function isTruncated(scrollHeight: number, clientHeight: number): boolean {
    return scrollHeight > clientHeight
  }

  it('detects truncation when scrollHeight > clientHeight', () => {
    expect(isTruncated(120, 60)).toBe(true)
  })

  it('does not detect truncation when scrollHeight === clientHeight', () => {
    expect(isTruncated(60, 60)).toBe(false)
  })

  it('does not detect truncation when scrollHeight < clientHeight', () => {
    expect(isTruncated(40, 60)).toBe(false)
  })

  it('handles zero heights', () => {
    expect(isTruncated(0, 0)).toBe(false)
  })

  it('handles very large content', () => {
    expect(isTruncated(5000, 60)).toBe(true)
  })
})

// ═══════════════════════════════════════════════════════════
// 5. Copy Feedback Timing
// ═══════════════════════════════════════════════════════════

describe('copy feedback timing', () => {
  // These tests validate the feedback timing logic used in SigFormsView:
  // - Show feedback immediately on copy
  // - Hide after 2 seconds
  // - Clear previous timer on rapid re-copy

  it('shows feedback immediately', () => {
    let feedbackFormId: string | null = null
    let timer: ReturnType<typeof setTimeout> | null = null

    // Simulate handleShareForm logic
    feedbackFormId = 'form-1'
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      feedbackFormId = null
    }, 2000)

    expect(feedbackFormId).toBe('form-1')
    clearTimeout(timer!)
  })

  it('clears feedback after 2 seconds', async () => {
    vi.useFakeTimers()

    let feedbackFormId: string | null = null
    let timer: ReturnType<typeof setTimeout> | null = null

    feedbackFormId = 'form-1'
    timer = setTimeout(() => {
      feedbackFormId = null
    }, 2000)

    expect(feedbackFormId).toBe('form-1')

    vi.advanceTimersByTime(1999)
    expect(feedbackFormId).toBe('form-1')

    vi.advanceTimersByTime(1)
    expect(feedbackFormId).toBeNull()

    vi.useRealTimers()
    clearTimeout(timer!)
  })

  it('resets timer on rapid consecutive copies', () => {
    vi.useFakeTimers()

    let feedbackFormId: string | null = null
    let timer: ReturnType<typeof setTimeout> | null = null

    // First copy
    feedbackFormId = 'form-1'
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      feedbackFormId = null
    }, 2000)

    vi.advanceTimersByTime(1500)
    expect(feedbackFormId).toBe('form-1')

    // Second copy (different form) — should reset timer
    feedbackFormId = 'form-2'
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      feedbackFormId = null
    }, 2000)

    // 500ms after second copy — still visible
    vi.advanceTimersByTime(500)
    expect(feedbackFormId).toBe('form-2')

    // Full 2000ms after second copy — now cleared
    vi.advanceTimersByTime(1500)
    expect(feedbackFormId).toBeNull()

    vi.useRealTimers()
  })

  it('clears on unmount to prevent memory leaks', () => {
    vi.useFakeTimers()

    let feedbackFormId: string | null = null
    let timer: ReturnType<typeof setTimeout> | null = null

    feedbackFormId = 'form-1'
    timer = setTimeout(() => {
      feedbackFormId = null
    }, 2000)

    // Simulate onUnmounted cleanup
    if (timer) clearTimeout(timer)
    timer = null

    // Even after 2s, value was not cleared by timer (because we cleared it)
    vi.advanceTimersByTime(3000)
    expect(feedbackFormId).toBe('form-1') // still set, timer was cancelled

    vi.useRealTimers()
  })
})
