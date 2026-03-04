import api from '@/composables/api'
import type { Category } from '@/types'

export interface CategoriesResponse {
  categories: Category[]
  total: number
}

export async function listCategories() {
  const { data } = await api.get('/categories')
  return data.categories as Category[]
}

export async function getCategory(categoryId: string) {
  const { data } = await api.get(`/categories/${categoryId}`)
  return data as Category
}

export async function createCategory(payload: { name: string; description?: string }) {
  const { data } = await api.post('/categories', payload)
  return data as Category
}

export async function updateCategory(
  categoryId: string,
  payload: { name: string; description?: string },
) {
  const { data } = await api.put(`/categories/${categoryId}`, payload)
  return data as Category
}

export async function deleteCategory(categoryId: string) {
  await api.delete(`/categories/${categoryId}`)
}
