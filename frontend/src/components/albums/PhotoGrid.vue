<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ImageIcon } from 'lucide-vue-next'
import type { AlbumPhoto } from '@/types/album'

const { t } = useI18n()

const props = defineProps<{
  photos: AlbumPhoto[]
  coverStorageUrl?: string | null
  canSetCover?: boolean
}>()

const emit = defineEmits<{
  select: [photo: AlbumPhoto]
  'set-cover': [photo: AlbumPhoto]
}>()

function handleSelect(photo: AlbumPhoto) {
  emit('select', photo)
}

function handleSetCover(e: Event, photo: AlbumPhoto) {
  e.stopPropagation()
  emit('set-cover', photo)
}

function isCoverPhoto(photo: AlbumPhoto): boolean {
  if (!props.coverStorageUrl || !photo.storage_url) return false
  // Compare the significant part of presigned URLs (before query params)
  const coverBase = props.coverStorageUrl.split('?')[0]
  const photoBase = photo.storage_url.split('?')[0]
  return coverBase === photoBase
}
</script>

<template>
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5 sm:gap-3">
    <button
      v-for="photo in photos"
      :key="photo.id"
      type="button"
      class="relative group aspect-square rounded-lg overflow-hidden bg-surface-alt focus:outline-none focus:ring-2 focus:ring-brand-500"
      @click="handleSelect(photo)"
    >
      <img
        :src="photo.thumbnail_url || photo.storage_url || ''"
        :alt="photo.original_filename || 'Photo'"
        loading="lazy"
        class="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
      />
      <!-- Cover badge -->
      <div
        v-if="isCoverPhoto(photo)"
        class="absolute top-2 left-2 z-10 flex items-center gap-1 bg-brand-600 text-white text-xs px-2 py-0.5 rounded"
      >
        <ImageIcon class="w-3 h-3" />
        {{ t('albums.currentCover') }}
      </div>
      <div
        class="absolute inset-0 bg-black/20 md:bg-black/0 md:group-hover:bg-black/30 transition-colors duration-200 flex items-end justify-between"
      >
        <span
          class="text-white text-xs px-2 py-1 truncate flex-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-200"
        >
          {{ photo.original_filename || 'Untitled' }}
        </span>
        <!-- Set as cover button -->
        <button
          v-if="canSetCover && !isCoverPhoto(photo)"
          type="button"
          class="text-white text-xs px-2 py-1 bg-black/50 hover:bg-brand-600 rounded-tl opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 shrink-0"
          :title="t('albums.setCover')"
          @click="handleSetCover($event, photo)"
        >
          {{ t('albums.setCover') }}
        </button>
      </div>
    </button>
  </div>
</template>
