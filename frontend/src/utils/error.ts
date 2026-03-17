export function getErrorMessage(
  e: unknown,
  tOrFallback?: ((key: string) => string) | string,
  fallbackKey = 'errors.unknown',
): string {
  const isTranslateFn = typeof tOrFallback === 'function'
  const t = isTranslateFn ? tOrFallback : (key: string) => key
  const fallback: string = isTranslateFn
    ? t(fallbackKey)
    : (tOrFallback as string | undefined) ?? 'An unexpected error occurred.'

  if (e == null || typeof e !== 'object') return fallback

  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail

  if (detail && typeof detail === 'object') {
    const code = (detail as Record<string, unknown>).error_code ?? (detail as Record<string, unknown>).code
    if (code && typeof code === 'string' && isTranslateFn) {
      const key = `errors.${code}`
      const translated = t(key)
      if (translated !== key) return translated
    }
    const msg = (detail as Record<string, unknown>).message
    if (typeof msg === 'string' && msg) return msg
  }

  if (typeof detail === 'string' && detail) return detail

  return fallback
}
