import { ref, watch, type Ref, isRef } from 'vue'
import type { RelationshipStatus } from '@/types/social'
import { getRelationshipStatus } from '@/api/social'
import { getErrorMessage } from '@/utils/error'

export function useSocialStatus(userId: Ref<string> | string) {
  const status = ref<RelationshipStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStatus() {
    const id = isRef(userId) ? userId.value : userId
    if (!id) return
    loading.value = true
    error.value = null
    try {
      const { data } = await getRelationshipStatus(id)
      status.value = data
    } catch (e: unknown) {
      error.value = getErrorMessage(e, 'Failed to fetch relationship status')
    } finally {
      loading.value = false
    }
  }

  if (isRef(userId)) {
    watch(userId, () => {
      fetchStatus()
    })
  }

  return { status, loading, error, fetchStatus }
}
