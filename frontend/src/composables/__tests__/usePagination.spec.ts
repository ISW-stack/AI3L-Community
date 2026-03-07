import { describe, it, expect } from 'vitest'
import { usePagination } from '../usePagination'

describe('usePagination', () => {
  it('has correct initial state', () => {
    const { page, total, totalPages, pageSize } = usePagination()
    expect(page.value).toBe(1)
    expect(total.value).toBe(0)
    expect(totalPages.value).toBe(1)
    expect(pageSize).toBe(20)
  })

  it('setPage changes page value', () => {
    const { page, setPage } = usePagination()
    setPage(5)
    expect(page.value).toBe(5)
  })

  it('resetPage resets to 1', () => {
    const { page, setPage, resetPage } = usePagination()
    setPage(10)
    expect(page.value).toBe(10)
    resetPage()
    expect(page.value).toBe(1)
  })

  it('updateFromResponse with explicit totalPages', () => {
    const { total, totalPages, updateFromResponse } = usePagination()
    updateFromResponse(100, 5)
    expect(total.value).toBe(100)
    expect(totalPages.value).toBe(5)
  })

  it('updateFromResponse calculates totalPages from total when not provided', () => {
    const { total, totalPages, updateFromResponse } = usePagination(10)
    updateFromResponse(45)
    expect(total.value).toBe(45)
    expect(totalPages.value).toBe(5)
  })

  it('updateFromResponse never sets totalPages below 1', () => {
    const { totalPages, updateFromResponse } = usePagination()
    updateFromResponse(0)
    expect(totalPages.value).toBe(1)
  })

  it('accepts custom pageSize parameter', () => {
    const { pageSize } = usePagination(50)
    expect(pageSize).toBe(50)
  })

  it('calculates totalPages correctly with custom pageSize', () => {
    const { totalPages, updateFromResponse } = usePagination(15)
    updateFromResponse(31)
    expect(totalPages.value).toBe(3)
  })

  it('multiple updateFromResponse calls override previous values', () => {
    const { total, totalPages, updateFromResponse } = usePagination(10)
    updateFromResponse(50, 5)
    expect(total.value).toBe(50)
    expect(totalPages.value).toBe(5)

    updateFromResponse(30, 3)
    expect(total.value).toBe(30)
    expect(totalPages.value).toBe(3)
  })

  it('integration: setPage + resetPage cycle', () => {
    const { page, setPage, resetPage, updateFromResponse } = usePagination()
    updateFromResponse(100, 5)

    setPage(3)
    expect(page.value).toBe(3)

    setPage(5)
    expect(page.value).toBe(5)

    resetPage()
    expect(page.value).toBe(1)

    setPage(2)
    expect(page.value).toBe(2)
  })
})
