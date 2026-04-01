import api from '@/composables/api'
import type {
  OrgChartResponse,
  MembersListResponse,
  ClassifiedMembersResponse,
  CategoryDetailResponse,
} from '@/types/orgchart'

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

export async function updateMemberBio(sigId: string, orgChartBio: string | null): Promise<void> {
  await api.put(`/about/org-chart/sigs/${sigId}/members/me/bio`, {
    org_chart_bio: orgChartBio,
  })
}

export interface AboutIntroData {
  photo_url: string
  bio: string
  chair_photo_url: string
  chair_bio: string
}

export async function getAboutIntro(): Promise<AboutIntroData> {
  const res = await api.get('/about/intro')
  return res.data
}

export async function updateAboutIntroPhoto(file: File): Promise<{ photo_url: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.put('/about/admin/intro/photo', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function updateAboutIntroBio(bio: string): Promise<void> {
  await api.put('/about/admin/intro/bio', { bio })
}

export async function updateChairPhoto(file: File): Promise<{ photo_url: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.put('/about/admin/chair/photo', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function updateChairBio(bio: string): Promise<void> {
  await api.put('/about/admin/chair/bio', { bio })
}

export interface LeadershipUser {
  user_id: string
  display_name: string
  avatar_url: string | null
}

export interface LeadershipData {
  chair: LeadershipUser | null
  co_chairs: LeadershipUser[]
}

export async function getLeadership(): Promise<LeadershipData> {
  const res = await api.get('/about/leadership')
  return res.data
}

export async function setLeadershipChair(userId: string): Promise<void> {
  await api.put('/about/admin/leadership/chair', { user_id: userId })
}

export async function removeLeadershipChair(): Promise<void> {
  await api.delete('/about/admin/leadership/chair')
}

export async function setLeadershipCoChairs(userIds: string[]): Promise<void> {
  await api.put('/about/admin/leadership/co-chairs', { user_ids: userIds })
}

// ── Member Classifications ──

export async function getClassifiedMembers(): Promise<ClassifiedMembersResponse> {
  const res = await api.get('/about/classified-members')
  return res.data
}

export async function getCategoryMembers(category: string): Promise<CategoryDetailResponse> {
  const res = await api.get(`/about/classified-members/${category}`)
  return res.data
}

export async function assignClassification(
  userId: string,
  category: string,
  displayOrder: number = 0,
): Promise<void> {
  await api.put('/about/admin/classifications', {
    user_id: userId,
    category,
    display_order: displayOrder,
  })
}

export async function removeClassification(userId: string): Promise<void> {
  await api.delete(`/about/admin/classifications/${userId}`)
}
