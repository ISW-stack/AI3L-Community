import { inject, type Ref } from 'vue'
import type { Sig } from '@/types/sig'

export function useSigLayout() {
  const sig = inject<Ref<Sig | null>>('sig')
  const userSigRole = inject<Ref<string | null>>('userSigRole')
  const refreshSigRole = inject<() => Promise<void>>('refreshSigRole')

  // Check != null (not !== null) because missing inject returns undefined
  if (sig == null || userSigRole == null) {
    throw new Error('useSigLayout must be used within SigLayout')
  }

  return { sig, userSigRole, refreshSigRole }
}
