import api from '@/composables/api'
import type { Category } from '@/types'

export interface CategoriesResponse {
  categories: Category[]
}

export async function listCategories() {
  const { data } = await api.get('/categories')
  return data.categories as Category[]
}
