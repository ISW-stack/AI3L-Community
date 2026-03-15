import { inject, type Ref } from 'vue'
import type { Album } from '@/types/album'

export function useAlbumLayout() {
  const album = inject<Ref<Album | null>>('album')
  const userAlbumRole = inject<Ref<string | null>>('userAlbumRole')

  // Check != null (not !== null) because missing inject returns undefined
  if (album == null || userAlbumRole == null) {
    throw new Error('useAlbumLayout must be used inside AlbumLayout')
  }

  return { album, userAlbumRole }
}
