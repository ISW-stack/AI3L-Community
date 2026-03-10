import { ref, type Ref } from 'vue'

export interface PaginationState {
  page: Ref<number>
  total: Ref<number>
  totalPages: Ref<number>
  pageSize: number
  setPage: (p: number) => void
  resetPage: () => void
  updateFromResponse: (responseTotal: number, responseTotalPages?: number) => void
}

export function usePagination(defaultPageSize = 20): PaginationState {
  const page = ref(1)
  const total = ref(0)
  const totalPages = ref(1)

  function setPage(p: number) {
    page.value = p
  }

  function resetPage() {
    page.value = 1
  }

  function updateFromResponse(responseTotal: number, responseTotalPages?: number) {
    total.value = responseTotal
    totalPages.value = responseTotalPages ?? Math.max(1, Math.ceil(responseTotal / defaultPageSize))
  }

  return {
    page,
    total,
    totalPages,
    pageSize: defaultPageSize,
    setPage,
    resetPage,
    updateFromResponse,
  }
}
