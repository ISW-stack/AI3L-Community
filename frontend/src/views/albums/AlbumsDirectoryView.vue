<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { listAlbums } from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'
import type { Album } from '@/types/album'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import AlbumCard from '@/components/albums/AlbumCard.vue'

const auth = useAuthStore()
const toast = useToastStore()

const albums = ref<Album[]>([])
const loading = ref(false)
const PAGE_SIZE = 12

const { page, total, totalPages, setPage, updateFromResponse } = usePagination(PAGE_SIZE)

async function fetchAlbums() {
  loading.value = true
  try {
    const { data } = await listAlbums(page.value, PAGE_SIZE)
    albums.value = data.albums
    updateFromResponse(data.total)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to load albums'), 'error')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

onMounted(fetchAlbums)
watch(page, fetchAlbums)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">Albums</h1>
      <router-link v-if="auth.isAdmin" to="/albums/create">
        <BaseButton>Create Album</BaseButton>
      </router-link>
    </div>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <EmptyState
      v-else-if="albums.length === 0"
      title="No albums yet"
      message="There are no albums available at the moment."
    />

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <router-link
          v-for="album in albums"
          :key="album.id"
          :to="`/albums/${album.id}`"
          class="block"
        >
          <AlbumCard :album="album" />
        </router-link>
      </div>

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

    <p class="mt-4 text-xs text-muted">{{ total }} total albums</p>
  </div>
</template>
