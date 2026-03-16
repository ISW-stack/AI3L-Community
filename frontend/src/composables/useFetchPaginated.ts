import { ref, type Ref } from 'vue'
import { usePagination } from './usePagination'
import { getErrorMessage } from '@/utils/error'

interface FetchResult<T> {
  items: T[]
  total: number
}

interface UseFetchPaginatedReturn<T> {
  items: Ref<T[]>
  loading: Ref<boolean>
  error: Ref<string>
  page: Ref<number>
  total: Ref<number>
  totalPages: Ref<number>
  pageSize: number
  fetchPage: () => Promise<void>
  setPage: (p: number) => void
  resetPage: () => void
  refresh: () => Promise<void>
}

export function useFetchPaginated<T>(
  fetchFn: (page: number, pageSize: number) => Promise<FetchResult<T>>,
  pageSize = 20,
): UseFetchPaginatedReturn<T> {
  const items = ref<T[]>([]) as Ref<T[]>
  const loading = ref(false)
  const error = ref('')
  const { page, total, totalPages, setPage, resetPage, updateFromResponse } =
    usePagination(pageSize)

  let fetchId = 0

  async function fetchPage() {
    const localFetchId = ++fetchId
    const previousPage = page.value
    loading.value = true
    error.value = ''
    try {
      const result = await fetchFn(page.value, pageSize)
      if (localFetchId !== fetchId) return
      items.value = result.items
      updateFromResponse(result.total)
    } catch (e: unknown) {
      if (localFetchId !== fetchId) return
      setPage(previousPage) // Restore page on failure
      error.value = getErrorMessage(e, 'Failed to fetch data')
    } finally {
      if (localFetchId === fetchId) {
        loading.value = false
      }
    }
  }

  async function refresh() {
    await fetchPage()
  }

  return {
    items,
    loading,
    error,
    page,
    total,
    totalPages,
    pageSize,
    fetchPage,
    setPage,
    resetPage,
    refresh,
  }
}
