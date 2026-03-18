<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToastStore } from '@/stores/toast'
import { useAlbumLayout } from '@/composables/useAlbumLayout'
import {
  listAlbumPhotos,
  uploadAlbumPhoto,
  deleteAlbumPhoto,
  setAlbumCoverFromPhoto,
} from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import type { AlbumPhoto } from '@/types/album'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import PhotoGrid from '@/components/albums/PhotoGrid.vue'
import PhotoLightbox from '@/components/albums/PhotoLightbox.vue'
import PhotoUploadModal from '@/components/albums/PhotoUploadModal.vue'

const { t } = useI18n()
const toast = useToastStore()
const auth = useAuthStore()
const { album, userAlbumRole } = useAlbumLayout()

const photos = ref<AlbumPhoto[]>([])
const loading = ref(false)
const uploading = ref(false)
const showUploadModal = ref(false)
const lightboxVisible = ref(false)
const lightboxIndex = ref(0)
const PAGE_SIZE = 20

const { page, total, totalPages, setPage, resetPage, updateFromResponse } = usePagination(PAGE_SIZE)

async function fetchPhotos() {
  if (!album.value) return
  loading.value = true
  try {
    const result = await listAlbumPhotos(album.value.id, page.value, PAGE_SIZE)
    photos.value = result.photos
    updateFromResponse(result.total)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.fetchPhotosError')), 'error')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

function openLightbox(photo: AlbumPhoto) {
  const idx = photos.value.findIndex((p) => p.id === photo.id)
  if (idx >= 0) {
    lightboxIndex.value = idx
    lightboxVisible.value = true
  }
}

function handleLightboxNavigate(index: number) {
  lightboxIndex.value = index
}

function closeLightbox() {
  lightboxVisible.value = false
}

function openUploadModal() {
  showUploadModal.value = true
}

async function handleUpload(file: File) {
  if (!album.value) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await uploadAlbumPhoto(album.value.id, formData)
    toast.show(t('albums.uploadSuccess'), 'success')
    await fetchPhotos()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.uploadError')), 'error')
  } finally {
    uploading.value = false
  }
}

const canDeletePhoto = computed(() => {
  if (!album.value || !auth.user) return false
  return (
    album.value.created_by === auth.user.id ||
    auth.isAdmin ||
    userAlbumRole.value === 'ADMIN'
  )
})

function canDeleteThisPhoto(photo: AlbumPhoto): boolean {
  if (!auth.user) return false
  if (photo.uploaded_by === auth.user.id) return true
  return canDeletePhoto.value
}

async function handleDeletePhoto(photo: AlbumPhoto) {
  if (!album.value || !confirm(t('albums.confirmDeletePhoto'))) return
  try {
    await deleteAlbumPhoto(album.value.id, photo.id)
    toast.show(t('albums.deletePhotoSuccess'), 'success')
    closeLightbox()
    await fetchPhotos()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.deletePhotoError')), 'error')
  }
}

const canSetCover = computed(() => {
  if (!album.value || !auth.user) return false
  return (
    album.value.created_by === auth.user.id ||
    auth.isAdmin ||
    userAlbumRole.value === 'ADMIN'
  )
})

async function handleSetCover(photo: AlbumPhoto) {
  if (!album.value) return
  try {
    const updated = await setAlbumCoverFromPhoto(album.value.id, photo.id)
    album.value = updated
    toast.show(t('albums.setCoverSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.setCoverError')), 'error')
  }
}

watch(
  () => album.value?.id,
  () => {
    resetPage()
    fetchPhotos()
  },
  { immediate: true },
)
watch(page, fetchPhotos)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-lg font-semibold text-foreground">{{ t('albums.photos') }}</h2>
      <BaseButton v-if="userAlbumRole" size="sm" :loading="uploading" @click="openUploadModal">
        {{ t('albums.uploadPhoto') }}
      </BaseButton>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="card" />

    <EmptyState
      v-else-if="photos.length === 0"
      :title="t('albums.noPhotosTitle')"
      :message="t('albums.noPhotosMessage')"
    />

    <template v-else>
      <PhotoGrid
        :photos="photos"
        :cover-storage-url="album?.cover_photo_url"
        :can-set-cover="canSetCover"
        @select="openLightbox"
        @set-cover="handleSetCover"
      />

      <div class="mt-6">
        <BasePagination
          :current-page="page"
          :total-pages="totalPages"
          :page-size="PAGE_SIZE"
          :total="total"
          @update:current-page="handlePageChange"
        />
      </div>
    </template>

    <PhotoLightbox
      :photos="photos"
      :current-index="lightboxIndex"
      :visible="lightboxVisible"
      :can-delete="photos[lightboxIndex] ? canDeleteThisPhoto(photos[lightboxIndex]) : false"
      :can-set-cover="canSetCover"
      @close="closeLightbox"
      @navigate="handleLightboxNavigate"
      @delete="handleDeletePhoto"
      @set-cover="handleSetCover"
    />

    <PhotoUploadModal v-model="showUploadModal" @upload="handleUpload" />
  </div>
</template>
