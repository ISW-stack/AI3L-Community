/**
 * Format a date string or Date object using the current app locale.
 * Falls back to 'en' if locale is unavailable.
 */
export function formatDate(
  date: string | Date | null | undefined,
  locale: string = 'en',
): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(
  date: string | Date | null | undefined,
  locale: string = 'en',
): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
