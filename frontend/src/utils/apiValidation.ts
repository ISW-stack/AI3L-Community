/**
 * Lightweight runtime shape checker for API responses.
 * Logs a warning in development if expected keys are missing.
 * Never throws — this is a safety net, not hard validation.
 */
export function assertShape<T>(data: unknown, requiredKeys: string[], context: string): T {
  if (import.meta.env.DEV && data && typeof data === 'object') {
    for (const key of requiredKeys) {
      if (!(key in data)) {
        console.warn(`[API] Missing key "${key}" in response for ${context}`)
      }
    }
  }
  return data as T
}
