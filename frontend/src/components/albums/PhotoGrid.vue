<script setup lang="ts">
import type { AlbumPhoto } from '@/types/album'

defineProps<{
  photos: AlbumPhoto[]
}>()

const emit = defineEmits<{
  select: [photo: AlbumPhoto]
}>()

function handleSelect(photo: AlbumPhoto) {
  emit('select', photo)
}
</script>

<template>
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
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
      <div
        class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors duration-200 flex items-end"
      >
        <span
          class="text-white text-xs px-2 py-1 truncate w-full opacity-0 group-hover:opacity-100 transition-opacity duration-200"
        >
          {{ photo.original_filename || 'Untitled' }}
        </span>
      </div>
    </button>
  </div>
</template>
