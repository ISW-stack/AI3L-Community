/**
 * Check whether a locale is supported by Intl.DateTimeFormat.
 * If not, warn in development mode and return 'en' as fallback.
 */
function resolveLocale(locale: string): string {
  try {
    const supported = Intl.DateTimeFormat.supportedLocalesOf([locale])
    if (supported.length === 0) {
      if (import.meta.env.DEV) {
        console.warn(
          `[date] Locale "${locale}" is not supported by Intl.DateTimeFormat. Falling back to "en".`,
        )
      }
      return 'en'
    }
  } catch {
    if (import.meta.env.DEV) {
      console.warn(
        `[date] Locale "${locale}" is not supported by Intl.DateTimeFormat. Falling back to "en".`,
      )
    }
    return 'en'
  }
  return locale
}

/**
 * Format a date string or Date object using the current app locale.
 * Falls back to 'en' if locale is unavailable.
 */
export function formatDate(date: string | Date | null | undefined, locale: string = 'en'): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  const resolved = resolveLocale(locale)
  return d.toLocaleDateString(resolved, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(
  date: string | Date | null | undefined,
  locale: string = 'en',
): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  const resolved = resolveLocale(locale)
  return d.toLocaleString(resolved, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
