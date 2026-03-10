import api from '@/composables/api'
import type { Contributor, ContributorCreate, ContributorUpdate } from '@/types/contributor'

export async function listContributors(): Promise<Contributor[]> {
  const { data } = await api.get('/about/admin/contributors')
  return data.contributors as Contributor[]
}

export async function createContributor(payload: ContributorCreate): Promise<Contributor> {
  const { data } = await api.post('/about/admin/contributors', payload)
  return data as Contributor
}

export async function updateContributor(
  id: string,
  payload: ContributorUpdate,
): Promise<Contributor> {
  const { data } = await api.put(`/about/admin/contributors/${id}`, payload)
  return data as Contributor
}

export async function deleteContributor(id: string): Promise<void> {
  await api.delete(`/about/admin/contributors/${id}`)
}
