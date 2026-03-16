export function getErrorMessage(
  e: unknown,
  tOrFallback?: ((key: string) => string) | string,
  maybeFallbackKey = 'common.unknownError',
): string {
  // Determine if we're using the new reactive signature (function) or legacy (string)
  const isFunction = typeof tOrFallback === 'function'
  const t = isFunction ? (tOrFallback as (key: string) => string) : (key: string) => key
  const fallback = isFunction
    ? t(maybeFallbackKey)
    : (tOrFallback as string) || 'An unexpected error occurred.'

  if (e == null || typeof e !== 'object') return fallback

  const err = e as any
  const data = err.response?.data || {}
  const detail = data.detail || data.message || data.error

  if (typeof detail === 'object' && detail !== null) {
    const code = detail.error_code || detail.code
    if (code) {
      // Override AUTH_001/002 during login/guest login to be "Invalid Credentials"
      // as some backends use generic auth errors for login failure.
      if (
        (code === 'AUTH_001' || code === 'AUTH_002') &&
        (maybeFallbackKey === 'auth.loginFailed' || maybeFallbackKey === 'auth.guestLoginFailed')
      ) {
        const loginKeys = ['errors.invalid_credentials', 'auth.errors.invalid_credentials']
        for (const key of loginKeys) {
          const trans = t(key)
          if (trans !== key) return trans
        }
      }

      const keys = [`auth.errors.${code}`, `errors.${code}`, code]

      for (const key of keys) {
        const translated = t(key)
        if (isFunction && translated !== key) return translated
      }

      // Special case for SYS_422 (Captcha)
      if (code === 'SYS_422') {
        const captchaKeys = ['errors.captcha_invalid', 'auth.errors.captcha_invalid']
        for (const key of captchaKeys) {
          const translated = t(key)
          if (isFunction && translated !== key) return translated
        }
      }
    }
    if (detail.message) return detail.message
  }

  if (typeof detail === 'string') {
    const lowerDetail = detail.toLowerCase()

    // Heuristics for common English error strings from backend
    // Only works if we have the translation function
    if (isFunction) {
      // 1. Credentials
      if (
        (lowerDetail.includes('invalid') && lowerDetail.includes('credential')) ||
        lowerDetail.includes('incorrect username or password')
      ) {
        const keys = ['errors.invalid_credentials', 'auth.errors.invalid_credentials']
        for (const key of keys) {
          const translated = t(key)
          if (translated !== key) return translated
        }
      }

      // 2. Captcha
      if (
        lowerDetail.includes('captcha') &&
        (lowerDetail.includes('invalid') || lowerDetail.includes('expired'))
      ) {
        const keys = ['errors.captcha_invalid', 'auth.errors.captcha_invalid', 'errors.SYS_422']
        for (const key of keys) {
          const translated = t(key)
          if (translated !== key) return translated
        }
      }

      // 3. Unauthorized
      if (lowerDetail.includes('unauthorized') || lowerDetail.includes('permission denied')) {
        // If we are at login, unauthorized usually means bad credentials
        if (maybeFallbackKey === 'auth.loginFailed') {
          const loginKeys = ['errors.invalid_credentials', 'auth.errors.invalid_credentials']
          for (const key of loginKeys) {
            const trans = t(key)
            if (trans !== key) return trans
          }
        }

        const keys = ['errors.unauthorized', 'auth.errors.unauthorized']
        for (const key of keys) {
          const translated = t(key)
          if (translated !== key) return translated
        }
      }

      // 4. Inactive Account
      if (lowerDetail.includes('inactive') || lowerDetail.includes('disabled')) {
        const keys = ['errors.account_inactive', 'auth.errors.account_inactive']
        for (const key of keys) {
          const translated = t(key)
          if (translated !== key) return translated
        }
      }
    }

    return detail
  }

  return fallback
}
