<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import type { AlbumPhoto } from '@/types/album'

const props = defineProps<{
  photos: AlbumPhoto[]
  currentIndex: number
  visible: boolean
  canDelete?: boolean
  canSetCover?: boolean
}>()

const emit = defineEmits<{
  close: []
  navigate: [index: number]
  delete: [photo: AlbumPhoto]
  'set-cover': [photo: AlbumPhoto]
}>()

const currentPhoto = computed(() => {
  if (props.currentIndex >= 0 && props.currentIndex < props.photos.length) {
    return props.photos[props.currentIndex]
  }
  return null
})

const hasPrev = computed(() => props.currentIndex > 0)
const hasNext = computed(() => props.currentIndex < props.photos.length - 1)

function goToPrev() {
  if (hasPrev.value) {
    emit('navigate', props.currentIndex - 1)
  }
}

function goToNext() {
  if (hasNext.value) {
    emit('navigate', props.currentIndex + 1)
  }
}

function handleClose() {
  emit('close')
}

function handleKeydown(e: KeyboardEvent) {
  if (!props.visible) return
  if (e.key === 'Escape') {
    handleClose()
  } else if (e.key === 'ArrowLeft') {
    goToPrev()
  } else if (e.key === 'ArrowRight') {
    goToNext()
  }
}

function handleOverlayClick(e: MouseEvent) {
  if ((e.target as HTMLElement).classList.contains('lightbox-overlay')) {
    handleClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="visible && currentPhoto"
        class="lightbox-overlay fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
        role="dialog"
        aria-modal="true"
        aria-label="Photo viewer"
        @click="handleOverlayClick"
      >
        <!-- Top-right actions -->
        <div class="absolute top-4 right-4 z-10 flex items-center gap-2">
          <button
            v-if="canSetCover && currentPhoto"
            type="button"
            class="text-white/80 hover:text-brand-400 p-2 rounded-full bg-black/30 hover:bg-black/50 transition"
            aria-label="Set as cover"
            @click="emit('set-cover', currentPhoto)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-6 h-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </button>
          <button
            v-if="canDelete && currentPhoto"
            type="button"
            class="text-white/80 hover:text-red-400 p-2 rounded-full bg-black/30 hover:bg-black/50 transition"
            aria-label="Delete photo"
            @click="emit('delete', currentPhoto)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-6 h-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
          <button
            type="button"
            class="text-white/80 hover:text-white p-2 rounded-full bg-black/30 hover:bg-black/50 transition"
            aria-label="Close"
            @click="handleClose"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-6 h-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <!-- Previous button -->
        <button
          v-if="hasPrev"
          type="button"
          class="absolute left-4 top-1/2 -translate-y-1/2 z-10 text-white/80 hover:text-white p-3 rounded-full bg-black/30 hover:bg-black/50 transition"
          aria-label="Previous photo"
          @click="goToPrev"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-6 h-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>

        <!-- Image -->
        <div class="max-w-[90vw] max-h-[85vh] flex flex-col items-center">
          <img
            :src="currentPhoto.storage_url || ''"
            :alt="currentPhoto.description || currentPhoto.original_filename || 'Photo'"
            class="max-w-full max-h-[80vh] object-contain rounded"
          />
          <div
            v-if="currentPhoto.description || currentPhoto.original_filename"
            class="mt-3 text-center"
          >
            <p v-if="currentPhoto.description" class="text-white text-sm">
              {{ currentPhoto.description }}
            </p>
            <p class="text-white/60 text-xs mt-1">
              {{ currentPhoto.original_filename }}
              <span v-if="photos.length > 1" class="ml-2">
                {{ currentIndex + 1 }} / {{ photos.length }}
              </span>
            </p>
          </div>
        </div>

        <!-- Next button -->
        <button
          v-if="hasNext"
          type="button"
          class="absolute right-4 top-1/2 -translate-y-1/2 z-10 text-white/80 hover:text-white p-3 rounded-full bg-black/30 hover:bg-black/50 transition"
          aria-label="Next photo"
          @click="goToNext"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-6 h-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.lightbox-enter-active,
.lightbox-leave-active {
  transition: opacity 0.2s ease;
}
.lightbox-enter-from,
.lightbox-leave-to {
  opacity: 0;
}
</style>
