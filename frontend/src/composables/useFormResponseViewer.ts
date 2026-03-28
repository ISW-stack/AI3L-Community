import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { getForm, listFormResponses, getFormStats } from '@/api/forms'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'
import { filterResponses, type QuestionStats } from '@/utils/formStats'
import type { FormResponse, Question } from '@/types'

export type ResponseViewMode = 'individual' | 'statistics'

export interface UseFormResponseViewerOptions {
  pageSize?: number
  onError?: (msg: string) => void
}

export interface UseFormResponseViewerReturn {
  responses: Ref<FormResponse[]>
  filteredResponses: ComputedRef<FormResponse[]>
  filteredCount: ComputedRef<number>
  questions: Ref<Question[]>
  formStats: Ref<QuestionStats[]>
  loading: Ref<boolean>
  viewMode: Ref<ResponseViewMode>
  searchQuery: Ref<string>
  dateFrom: Ref<string>
  dateTo: Ref<string>
  expandedTextQuestions: Ref<Set<string>>
  pagination: ReturnType<typeof usePagination>
  fetchResponses: (formId: string, page?: number) => Promise<void>
  resetFilters: () => void
  toggleTextExpand: (questionId: string) => void
  isTextExpanded: (questionId: string) => boolean
  resolveQuestionLabel: (questionId: string) => string
  resolveAnswerValue: (questionId: string, value: unknown) => string
}

export function useFormResponseViewer(
  options: UseFormResponseViewerOptions = {},
): UseFormResponseViewerReturn {
  const { pageSize = 100, onError } = options

  const responses = ref<FormResponse[]>([])
  const questions = ref<Question[]>([])
  const formStats = ref<QuestionStats[]>([])
  const loading = ref(false)
  const viewMode = ref<ResponseViewMode>('individual')
  const searchQuery = ref('')
  const dateFrom = ref('')
  const dateTo = ref('')
  const expandedTextQuestions = ref<Set<string>>(new Set())

  const pagination = usePagination(pageSize)
  let _fetchId = 0

  const filteredResponses: ComputedRef<FormResponse[]> = computed(() =>
    filterResponses(responses.value, searchQuery.value, dateFrom.value, dateTo.value),
  )

  const filteredCount: ComputedRef<number> = computed(() => filteredResponses.value.length)

  function resetFilters() {
    searchQuery.value = ''
    dateFrom.value = ''
    dateTo.value = ''
    viewMode.value = 'individual'
    expandedTextQuestions.value = new Set()
  }

  function toggleTextExpand(questionId: string) {
    if (expandedTextQuestions.value.has(questionId)) {
      expandedTextQuestions.value.delete(questionId)
    } else {
      expandedTextQuestions.value.add(questionId)
    }
  }

  function isTextExpanded(questionId: string): boolean {
    return expandedTextQuestions.value.has(questionId)
  }

  function resolveQuestionLabel(questionId: string): string {
    const q = questions.value.find((q) => q.id === questionId)
    return q?.label || questionId
  }

  function resolveAnswerValue(questionId: string, value: unknown): string {
    const q = questions.value.find((q) => q.id === questionId)
    if (!q) return String(value ?? '(None)')

    const optionMap = new Map((q.options || []).map((o) => [o.id, o.label]))

    if (Array.isArray(value)) {
      return value.map((v) => optionMap.get(String(v)) ?? String(v)).join(', ') || '(None)'
    }
    if (typeof value === 'string' && optionMap.has(value)) {
      return optionMap.get(value)!
    }
    if (typeof value === 'object' && value !== null) {
      const obj = value as Record<string, unknown>
      if (obj.filename) return String(obj.filename)
      return JSON.stringify(value)
    }
    return String(value ?? '(None)')
  }

  async function fetchResponses(formId: string, page = 1): Promise<void> {
    const localFetchId = ++_fetchId
    loading.value = true
    pagination.setPage(page)

    try {
      const [formData, respData, statsData] = await Promise.all([
        page === 1 ? getForm(formId) : Promise.resolve(null),
        listFormResponses(formId, page, pageSize),
        page === 1 ? getFormStats(formId).catch(() => null) : Promise.resolve(null),
      ])

      if (localFetchId !== _fetchId) return // stale response

      if (formData) {
        questions.value = formData.questions
      }

      responses.value = respData.responses || []
      const total = respData.total || 0
      pagination.updateFromResponse(total, Math.ceil(total / pageSize) || 1)

      if (statsData && statsData.question_stats) {
        // Map server-side stats to the QuestionStats format used by the UI
        if (!Array.isArray(statsData.question_stats)) {
          console.warn(
            '[FormResponseViewer] Expected question_stats to be an array, got:',
            typeof statsData.question_stats,
          )
          formStats.value = []
        } else {
          const mapped = (statsData.question_stats as unknown[])
            .filter((qs: unknown) => {
              if (
                !qs ||
                typeof qs !== 'object' ||
                !(qs as Record<string, unknown>).question_id ||
                !(qs as Record<string, unknown>).stats
              ) {
                console.warn('[FormResponseViewer] Invalid question stat entry:', qs)
                return false
              }
              return true
            })
            .map((qs: unknown) => {
              const entry = qs as Record<string, unknown>
              return {
                ...(entry.stats as Record<string, unknown>),
                questionId: entry.question_id,
                label: entry.question_label,
              }
            })
          formStats.value = mapped as QuestionStats[]
        }
      }
    } catch (e: unknown) {
      if (localFetchId !== _fetchId) return // stale response
      onError?.(getErrorMessage(e, ''))
    } finally {
      if (localFetchId === _fetchId) loading.value = false
    }
  }

  return {
    responses,
    filteredResponses,
    filteredCount,
    questions,
    formStats,
    loading,
    viewMode,
    searchQuery,
    dateFrom,
    dateTo,
    expandedTextQuestions,
    pagination,
    fetchResponses,
    resetFilters,
    toggleTextExpand,
    isTextExpanded,
    resolveQuestionLabel,
    resolveAnswerValue,
  }
}
