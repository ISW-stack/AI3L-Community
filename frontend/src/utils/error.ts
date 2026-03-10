export function getErrorMessage(e: unknown, fallback = 'An error occurred.'): string {
  if (e == null || typeof e !== 'object') return fallback
  const err = e as { response?: { data?: { detail?: string | { message?: string } } } }
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object' && detail !== null && 'message' in detail && detail.message) {
    return detail.message
  }
  return fallback
}
