import { describe, it, expect, vi } from 'vitest'
import { useFetchPaginated } from '../useFetchPaginated'

describe('useFetchPaginated', () => {
  it('has correct initial state', () => {
    const fetchFn = vi.fn()
    const { items, loading, error, page, total, totalPages, pageSize } = useFetchPaginated(fetchFn)

    expect(items.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBe('')
    expect(page.value).toBe(1)
    expect(total.value).toBe(0)
    expect(totalPages.value).toBe(1)
    expect(pageSize).toBe(20)
  })

  it('accepts custom pageSize', () => {
    const fetchFn = vi.fn()
    const { pageSize } = useFetchPaginated(fetchFn, 50)
    expect(pageSize).toBe(50)
  })

  it('successful fetch populates items and total', async () => {
    const mockData = [
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
    ]
    const fetchFn = vi.fn().mockResolvedValue({ items: mockData, total: 42 })

    const { items, total, totalPages, fetchPage } = useFetchPaginated(fetchFn, 20)

    await fetchPage()

    expect(items.value).toEqual(mockData)
    expect(total.value).toBe(42)
    expect(totalPages.value).toBe(3) // ceil(42/20) = 3
    expect(fetchFn).toHaveBeenCalledWith(1, 20)
  })

  it('error handling sets error message', async () => {
    const fetchFn = vi.fn().mockRejectedValue({
      response: { data: { detail: 'Server error occurred' } },
    })

    const { items, error, fetchPage } = useFetchPaginated(fetchFn)

    await fetchPage()

    expect(error.value).toBe('Server error occurred')
    expect(items.value).toEqual([])
  })

  it('uses fallback message when error has no detail', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('network'))

    const { error, fetchPage } = useFetchPaginated(fetchFn)

    await fetchPage()

    expect(error.value).toBe('Failed to fetch data')
  })

  it('loading state transitions correctly during fetch', async () => {
    const loadingStates: boolean[] = []
    let resolveFn: (value: { items: unknown[]; total: number }) => void
    const fetchFn = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve
        }),
    )

    const { loading, fetchPage } = useFetchPaginated(fetchFn)

    loadingStates.push(loading.value) // before fetch: false

    const fetchPromise = fetchPage()
    loadingStates.push(loading.value) // during fetch: true

    resolveFn!({ items: [], total: 0 })
    await fetchPromise

    loadingStates.push(loading.value) // after fetch: false

    expect(loadingStates).toEqual([false, true, false])
  })

  it('loading is false after error', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('fail'))

    const { loading, fetchPage } = useFetchPaginated(fetchFn)

    await fetchPage()

    expect(loading.value).toBe(false)
  })

  it('error is cleared on new fetch', async () => {
    const fetchFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ items: [{ id: '1' }], total: 1 })

    const { error, items, fetchPage } = useFetchPaginated(fetchFn)

    await fetchPage()
    expect(error.value).toBe('Failed to fetch data')

    await fetchPage()
    expect(error.value).toBe('')
    expect(items.value).toEqual([{ id: '1' }])
  })

  it('setPage changes page value', () => {
    const fetchFn = vi.fn()
    const { page, setPage } = useFetchPaginated(fetchFn)

    setPage(3)
    expect(page.value).toBe(3)
  })

  it('resetPage resets to page 1', () => {
    const fetchFn = vi.fn()
    const { page, setPage, resetPage } = useFetchPaginated(fetchFn)

    setPage(5)
    expect(page.value).toBe(5)

    resetPage()
    expect(page.value).toBe(1)
  })

  it('fetchPage passes current page to fetchFn', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ items: [], total: 100 })
    const { setPage, fetchPage } = useFetchPaginated(fetchFn, 10)

    setPage(3)
    await fetchPage()

    expect(fetchFn).toHaveBeenCalledWith(3, 10)
  })

  it('refresh calls fetchPage', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ items: [{ id: '1' }], total: 1 })
    const { refresh, items } = useFetchPaginated(fetchFn)

    await refresh()

    expect(items.value).toEqual([{ id: '1' }])
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('totalPages is calculated correctly', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ items: [], total: 55 })
    const { totalPages, fetchPage } = useFetchPaginated(fetchFn, 10)

    await fetchPage()

    expect(totalPages.value).toBe(6) // ceil(55/10) = 6
  })

  it('totalPages is at least 1 when total is 0', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ items: [], total: 0 })
    const { totalPages, fetchPage } = useFetchPaginated(fetchFn)

    await fetchPage()

    expect(totalPages.value).toBe(1)
  })

  it('page change followed by fetchPage uses updated page', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ items: [], total: 100 })
    const { setPage, fetchPage } = useFetchPaginated(fetchFn, 20)

    await fetchPage()
    expect(fetchFn).toHaveBeenCalledWith(1, 20)

    setPage(2)
    await fetchPage()
    expect(fetchFn).toHaveBeenCalledWith(2, 20)

    setPage(5)
    await fetchPage()
    expect(fetchFn).toHaveBeenCalledWith(5, 20)
  })

  // ---------- B17: page restoration on fetch failure ----------

  describe('page restoration on failure', () => {
    it('reverts page to previous value on fetch failure', async () => {
      const fetchFn = vi
        .fn()
        .mockResolvedValueOnce({ items: [{ id: '1' }], total: 100 })
        .mockRejectedValueOnce(new Error('Server error'))

      const { page, setPage, fetchPage } = useFetchPaginated(fetchFn, 20)

      // Successfully fetch page 1
      await fetchPage()
      expect(page.value).toBe(1)

      // Navigate to page 3, then fetch fails
      setPage(3)
      await fetchPage()

      // Page should revert to 3 (the value at the time fetchPage was called)
      // since setPage(3) happened before fetchPage()
      expect(page.value).toBe(3)
    })

    it('reverts page when fetch fails after setPage during fetchPage', async () => {
      // First fetch succeeds at page 1
      const fetchFn = vi
        .fn()
        .mockResolvedValueOnce({ items: [{ id: '1' }], total: 100 })
        .mockRejectedValueOnce(new Error('Network error'))

      const { page, setPage, fetchPage } = useFetchPaginated(fetchFn, 20)

      // Successfully load page 1
      await fetchPage()
      expect(page.value).toBe(1)

      // User clicks page 5 — setPage then fetchPage
      setPage(5)
      await fetchPage()

      // On failure, page should stay at 5 (previousPage captured at start of fetchPage)
      expect(page.value).toBe(5)
    })

    it('keeps items from previous successful fetch on failure', async () => {
      const oldItems = [{ id: 'old1' }, { id: 'old2' }]
      const fetchFn = vi
        .fn()
        .mockResolvedValueOnce({ items: oldItems, total: 50 })
        .mockRejectedValueOnce(new Error('fail'))

      const { items, setPage, fetchPage } = useFetchPaginated(fetchFn, 10)

      await fetchPage()
      expect(items.value).toEqual(oldItems)

      setPage(2)
      await fetchPage()

      // Old items should still be visible (not cleared on failure)
      expect(items.value).toEqual(oldItems)
    })

    it('error message is set on failure even with page restoration', async () => {
      const fetchFn = vi
        .fn()
        .mockResolvedValueOnce({ items: [], total: 0 })
        .mockRejectedValueOnce({
          response: { data: { detail: 'Page not found' } },
        })

      const { error, setPage, fetchPage } = useFetchPaginated(fetchFn, 20)

      await fetchPage()
      setPage(999)
      await fetchPage()

      expect(error.value).toBe('Page not found')
    })
  })

  // ---------- fetchId race condition guard ----------

  describe('fetchId race condition guard', () => {
    it('stale response from slower first request is discarded', async () => {
      let resolveFirst: (value: { items: unknown[]; total: number }) => void
      let resolveSecond: (value: { items: unknown[]; total: number }) => void

      const fetchFn = vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveFirst = resolve
            }),
        )
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveSecond = resolve
            }),
        )

      const { items, fetchPage } = useFetchPaginated(fetchFn, 10)

      // Start first request
      const first = fetchPage()
      // Start second request (supersedes first)
      const second = fetchPage()

      // Resolve second first (latest)
      resolveSecond!({ items: [{ id: 'latest' }], total: 1 })
      await second

      // Resolve first (stale) — should be discarded
      resolveFirst!({ items: [{ id: 'stale' }], total: 1 })
      await first

      expect(items.value).toEqual([{ id: 'latest' }])
    })

    it('loading stays true while latest request is pending', async () => {
      let resolveFirst: (value: { items: unknown[]; total: number }) => void
      let resolveSecond: (value: { items: unknown[]; total: number }) => void

      const fetchFn = vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveFirst = resolve
            }),
        )
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveSecond = resolve
            }),
        )

      const { loading, fetchPage } = useFetchPaginated(fetchFn, 10)

      // Start first request
      const first = fetchPage()
      // Start second request (supersedes first)
      const second = fetchPage()

      // Resolve first (stale) — loading should stay true because second is still pending
      resolveFirst!({ items: [], total: 0 })
      await first

      expect(loading.value).toBe(true)

      // Resolve second (latest) — now loading should become false
      resolveSecond!({ items: [], total: 0 })
      await second

      expect(loading.value).toBe(false)
    })

    it('stale error is discarded', async () => {
      let rejectFirst: (reason: unknown) => void
      let resolveSecond: (value: { items: unknown[]; total: number }) => void

      const fetchFn = vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise((_resolve, reject) => {
              rejectFirst = reject
            }),
        )
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              resolveSecond = resolve
            }),
        )

      const { error, fetchPage } = useFetchPaginated(fetchFn, 10)

      // Start first request
      const first = fetchPage()
      // Start second request (supersedes first)
      const second = fetchPage()

      // Reject first (stale) — error should NOT be set
      rejectFirst!(new Error('stale error'))
      await first

      expect(error.value).toBe('')

      // Resolve second (latest)
      resolveSecond!({ items: [], total: 0 })
      await second

      expect(error.value).toBe('')
    })
  })
})
