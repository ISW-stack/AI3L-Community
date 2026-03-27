export function getErrorMessage(
  e: unknown,
  tOrFallback?: ((key: string) => string) | string,
  fallbackKey = 'errors.unknown',
): string {
  const isTranslateFn = typeof tOrFallback === 'function'
  const t = isTranslateFn ? tOrFallback : (key: string) => key
  const fallback: string = isTranslateFn
    ? t(fallbackKey)
    : ((tOrFallback as string | undefined) ?? 'An unexpected error occurred.')

  if (e == null || typeof e !== 'object') return fallback

  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail

  if (detail && typeof detail === 'object') {
    // Pydantic 422 validation errors: detail is an array of {loc, msg, type}
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string; loc?: unknown[] }
      if (typeof first.msg === 'string') {
        const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
        const msg = field ? `${field}: ${first.msg}` : first.msg
        if (msg.length <= 200) return msg
        return fallback
      }
    }
    const code =
      (detail as Record<string, unknown>).error_code ?? (detail as Record<string, unknown>).code
    if (code && typeof code === 'string' && isTranslateFn) {
      const key = `errors.${code}`
      const translated = t(key)
      if (translated !== key) return translated
    }
    const msg = (detail as Record<string, unknown>).message
    if (typeof msg === 'string' && msg) {
      // P3: Don't expose raw server internals — cap length and filter SQL/paths
      if (msg.length > 200 || /SELECT |INSERT |UPDATE |DELETE |FROM |WHERE /i.test(msg)) {
        return fallback
      }
      return msg
    }
  }

  if (typeof detail === 'string' && detail) {
    if (detail.length > 200 || /SELECT |INSERT |UPDATE |DELETE |FROM |WHERE /i.test(detail)) {
      return fallback
    }
    return detail
  }

  return fallback
}
