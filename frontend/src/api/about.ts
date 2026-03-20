import api from '@/composables/api'
import type { OrgChartResponse, MembersListResponse } from '@/types/orgchart'

export async function getOrgChart(): Promise<OrgChartResponse> {
  const res = await api.get('/about/org-chart')
  return res.data
}

export async function getMembers(params: {
  page?: number
  page_size?: number
  search?: string
}): Promise<MembersListResponse> {
  const res = await api.get('/about/members', { params })
  return res.data
}

export async function updateOverride(
  entityType: string,
  entityId: string,
  data: {
    custom_title?: string | null
    custom_description?: string | null
    display_order?: number | null
    is_visible?: boolean | null
  },
): Promise<void> {
  await api.put(`/about/org-chart/override/${entityType}/${entityId}`, data)
}

export async function updateSigDescription(
  sigId: string,
  orgChartDescription: string | null,
): Promise<void> {
  await api.put(`/about/org-chart/sigs/${sigId}/description`, {
    org_chart_description: orgChartDescription,
  })
}

export async function updateMemberBio(
  sigId: string,
  orgChartBio: string | null,
): Promise<void> {
  await api.put(`/about/org-chart/sigs/${sigId}/members/me/bio`, {
    org_chart_bio: orgChartBio,
  })
}
