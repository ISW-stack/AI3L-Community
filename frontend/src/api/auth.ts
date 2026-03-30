import api from '@/composables/api'
import { assertShape } from '@/utils/apiValidation'

export interface CaptchaResponse {
  captcha_id: string
  image_base64: string
}

export interface AuthResponse {
  role: string
  expires_in: number
  requires_consent?: boolean
}

export async function getCaptcha(type?: 'math') {
  const params = type ? { type } : undefined
  const { data } = await api.get('/auth/captcha', { params })
  return assertShape<CaptchaResponse>(data, ['captcha_id', 'image_base64'], 'getCaptcha')
}

export async function login(payload: {
  username: string
  password: string
  captcha_id: string
  captcha_code: string
}) {
  const { data } = await api.post('/auth/login', payload)
  return assertShape<AuthResponse>(data, ['role', 'expires_in'], 'login')
}

export async function guestLogin(
  inviteCode: string,
  payload: {
    display_name: string
    captcha_id: string
    captcha_code: string
  },
) {
  const { data } = await api.post(`/auth/guest/${encodeURIComponent(inviteCode)}`, payload)
  return assertShape<AuthResponse>(data, ['role', 'expires_in'], 'guestLogin')
}

export async function register(payload: {
  username: string
  password: string
  display_name: string
  invite_code: string
  captcha_id: string
  captcha_code: string
}) {
  const { data } = await api.post('/auth/register', payload)
  return assertShape<AuthResponse>(data, ['role', 'expires_in'], 'register')
}

export async function logout() {
  await api.post('/auth/logout')
}

export async function heartbeat() {
  await api.post('/auth/heartbeat')
}
