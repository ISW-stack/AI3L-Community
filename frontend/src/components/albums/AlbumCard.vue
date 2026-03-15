<script setup lang="ts">
import type { Album } from '@/types/album'
import BaseCard from '@/components/base/BaseCard.vue'
import { Camera, Users } from 'lucide-vue-next'

defineProps<{
  album: Album
}>()
</script>

<template>
  <BaseCard hoverable class="h-full !p-0 overflow-hidden">
    <div class="h-36 relative">
      <img
        v-if="album.cover_photo_url"
        :src="album.cover_photo_url"
        :alt="album.title"
        loading="lazy"
        class="w-full h-full object-cover"
      />
      <div
        v-else
        class="w-full h-full bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center"
      >
        <Camera class="w-10 h-10 text-white/60" />
      </div>
      <div
        v-if="album.is_archived"
        class="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded"
      >
        Archived
      </div>
    </div>
    <div class="p-4">
      <h3 class="text-base font-semibold text-foreground mb-1 line-clamp-1">{{ album.title }}</h3>
      <p v-if="album.description" class="text-sm text-muted mb-3 line-clamp-2">
        {{ album.description }}
      </p>
      <div class="flex items-center gap-4 text-xs text-muted">
        <span class="flex items-center gap-1">
          <Camera class="w-3.5 h-3.5" />
          {{ album.photo_count }}
        </span>
        <span class="flex items-center gap-1">
          <Users class="w-3.5 h-3.5" />
          {{ album.member_count }}
        </span>
      </div>
    </div>
  </BaseCard>
</template>
