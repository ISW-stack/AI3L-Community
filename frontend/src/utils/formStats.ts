import type { FormResponse, Question } from '@/types'

export interface ChoiceStats {
  type: 'choice'
  questionId: string
  label: string
  totalResponses: number
  options: { id: string; label: string; count: number; percentage: number }[]
}

export interface RatingStats {
  type: 'rating'
  questionId: string
  label: string
  totalResponses: number
  average: number
  min: number
  max: number
  distribution: { value: number; count: number; percentage: number }[]
}

export interface TextStats {
  type: 'text'
  questionId: string
  label: string
  totalResponses: number
  answers: string[]
}

export interface FileStats {
  type: 'file'
  questionId: string
  label: string
  totalUploads: number
  filenames: string[]
}

export type QuestionStats = ChoiceStats | RatingStats | TextStats | FileStats

const CHOICE_TYPES = new Set(['single_choice', 'multiple_choice', 'dropdown'])

export function computeFormStats(
  questions: Question[],
  responses: FormResponse[],
): QuestionStats[] {
  return questions.map((q) => {
    if (CHOICE_TYPES.has(q.type)) {
      return computeChoiceStats(q, responses)
    }
    if (q.type === 'rating') {
      return computeRatingStats(q, responses)
    }
    if (q.type === 'file_upload') {
      return computeFileStats(q, responses)
    }
    return computeTextStats(q, responses)
  })
}

function computeChoiceStats(q: Question, responses: FormResponse[]): ChoiceStats {
  const optionCounts = new Map<string, number>()
  for (const opt of q.options || []) {
    optionCounts.set(opt.id, 0)
  }

  let totalResponses = 0
  for (const resp of responses) {
    const val = resp.answers[q.id]
    if (val == null) continue
    totalResponses++
    if (Array.isArray(val)) {
      for (const v of val) {
        const key = String(v)
        optionCounts.set(key, (optionCounts.get(key) || 0) + 1)
      }
    } else {
      const key = String(val)
      optionCounts.set(key, (optionCounts.get(key) || 0) + 1)
    }
  }

  const optionMap = new Map((q.options || []).map((o) => [o.id, o.label]))
  const totalVotes = Array.from(optionCounts.values()).reduce((a, b) => a + b, 0)

  return {
    type: 'choice',
    questionId: q.id,
    label: q.label,
    totalResponses,
    options: Array.from(optionCounts.entries()).map(([id, count]) => ({
      id,
      label: optionMap.get(id) || id,
      count,
      percentage: totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0,
    })),
  }
}

function computeRatingStats(q: Question, responses: FormResponse[]): RatingStats {
  const values: number[] = []
  for (const resp of responses) {
    const val = resp.answers[q.id]
    if (val != null && typeof val === 'number') {
      values.push(val)
    } else if (val != null && typeof val === 'string') {
      const parsed = Number(val)
      if (!isNaN(parsed)) values.push(parsed)
    }
  }

  const minRange = q.min ?? 1
  const maxRange = q.max ?? 5

  if (values.length === 0) {
    const distribution: { value: number; count: number; percentage: number }[] = []
    for (let i = minRange; i <= maxRange; i++) {
      distribution.push({ value: i, count: 0, percentage: 0 })
    }
    return {
      type: 'rating',
      questionId: q.id,
      label: q.label,
      totalResponses: 0,
      average: 0,
      min: minRange,
      max: maxRange,
      distribution,
    }
  }

  const sum = values.reduce((a, b) => a + b, 0)
  const average = Math.round((sum / values.length) * 100) / 100

  const distMap = new Map<number, number>()
  for (let i = minRange; i <= maxRange; i++) {
    distMap.set(i, 0)
  }
  for (const v of values) {
    distMap.set(v, (distMap.get(v) || 0) + 1)
  }

  const distribution = Array.from(distMap.entries()).map(([value, count]) => ({
    value,
    count,
    percentage: values.length > 0 ? Math.round((count / values.length) * 100) : 0,
  }))

  return {
    type: 'rating',
    questionId: q.id,
    label: q.label,
    totalResponses: values.length,
    average,
    min: minRange,
    max: maxRange,
    distribution,
  }
}

function computeTextStats(q: Question, responses: FormResponse[]): TextStats {
  const answers: string[] = []
  for (const resp of responses) {
    const val = resp.answers[q.id]
    if (val != null && String(val).trim() !== '') {
      answers.push(String(val))
    }
  }

  return {
    type: 'text',
    questionId: q.id,
    label: q.label,
    totalResponses: answers.length,
    answers,
  }
}

function computeFileStats(q: Question, responses: FormResponse[]): FileStats {
  const filenames: string[] = []
  for (const resp of responses) {
    const val = resp.answers[q.id]
    if (val != null && typeof val === 'object' && !Array.isArray(val)) {
      const obj = val as Record<string, unknown>
      if (obj.filename) filenames.push(String(obj.filename))
    } else if (val != null && typeof val === 'string' && val.trim() !== '') {
      filenames.push(val)
    }
  }

  return {
    type: 'file',
    questionId: q.id,
    label: q.label,
    totalUploads: filenames.length,
    filenames,
  }
}

export function filterResponses(
  responses: FormResponse[],
  searchQuery: string,
  dateFrom: string,
  dateTo: string,
): FormResponse[] {
  let filtered = responses

  if (searchQuery.trim()) {
    const query = searchQuery.trim().toLowerCase()
    filtered = filtered.filter((r) => r.display_name.toLowerCase().includes(query))
  }

  if (dateFrom) {
    const fromDate = new Date(dateFrom)
    fromDate.setHours(0, 0, 0, 0)
    filtered = filtered.filter((r) => new Date(r.created_at) >= fromDate)
  }

  if (dateTo) {
    const toDate = new Date(dateTo)
    toDate.setHours(23, 59, 59, 999)
    filtered = filtered.filter((r) => new Date(r.created_at) <= toDate)
  }

  return filtered
}

export function formatDeleteWarning(
  responseCount: number,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  if (responseCount === 0) {
    return t('sigs.forms.deleteConfirm.messageNoResponses')
  }
  return t('sigs.forms.deleteConfirm.messageWithCount', { count: responseCount })
}
