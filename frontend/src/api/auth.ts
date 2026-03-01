import api from '@/composables/api'

export interface CaptchaResponse {
  captcha_id: string
  image_base64: string
}

export async function getCaptcha() {
  const { data } = await api.get('/auth/captcha')
  return data as CaptchaResponse
}
