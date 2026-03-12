import api from '@/composables/api'
import type { FormData, FormResponse } from '@/types'

export async function getForm(formId: string) {
  const { data } = await api.get(`/forms/${formId}`)
  return data as FormData
}

export async function createForm(
  sigId: string,
  payload: {
    title: string
    description: string | null
    banner_url: string | null
    deadline: string | null
    max_respondents: number | null
    questions: unknown[]
    allow_non_members?: boolean
  },
) {
  const { data } = await api.post(`/sigs/${sigId}/forms`, payload)
  return data as FormData
}

export async function updateForm(
  formId: string,
  payload: {
    title?: string
    description?: string | null
    banner_url?: string | null
    deadline?: string | null
    max_respondents?: number | null
    questions?: unknown[]
    allow_non_members?: boolean
  },
) {
  const { data } = await api.put(`/forms/${formId}`, payload)
  return data as FormData
}

export async function deleteForm(formId: string) {
  await api.delete(`/forms/${formId}`)
}

export async function submitForm(formId: string, answers: Record<string, unknown>) {
  await api.post(`/forms/${formId}/submit`, { answers })
}

export async function exportForm(formId: string) {
  const { data } = await api.post(`/forms/${formId}/export`)
  return data as { task_id: string }
}

export async function listFormResponses(formId: string, page = 1, pageSize = 20) {
  const { data } = await api.get(`/forms/${formId}/responses`, {
    params: { page, page_size: pageSize },
  })
  return data as { responses: FormResponse[]; total: number }
}

export async function getMyResponse(formId: string) {
  const { data } = await api.get(`/forms/${formId}/my-response`)
  return data as FormResponse
}
