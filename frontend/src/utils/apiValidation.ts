/**
 * Lightweight runtime shape checker for API responses.
 * Logs a warning in development if expected keys are missing.
 * Never throws — this is a safety net, not hard validation.
 */
export function assertShape<T>(data: unknown, requiredKeys: string[], context: string): T {
  if (import.meta.env.DEV && data && typeof data === 'object') {
    const actualKeys = Object.keys(data)
    const missingKeys = requiredKeys.filter((key) => !(key in data))
    if (missingKeys.length > 0) {
      console.warn(
        `[API] Shape mismatch in "${context}": missing keys [${missingKeys.join(', ')}]. ` +
          `Expected: [${requiredKeys.join(', ')}]. ` +
          `Received: [${actualKeys.join(', ')}].`,
      )
    }
    const requiredSet = new Set(requiredKeys)
    const extraKeys = actualKeys.filter((key) => !requiredSet.has(key))
    if (extraKeys.length > 0) {
      console.warn(
        `[API] Shape mismatch in "${context}": unexpected keys [${extraKeys.join(', ')}]. ` +
          `Expected: [${requiredKeys.join(', ')}]. ` +
          `Received: [${actualKeys.join(', ')}].`,
      )
    }
  }
  return data as T
}
