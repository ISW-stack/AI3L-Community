<script setup lang="ts">
import { ref, computed, onMounted, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import { getAlbum, listAlbumMembers } from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import type { Album, AlbumMember } from '@/types/album'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const { t } = useLocale()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toastStore = useToastStore()

const albumId = computed(() => route.params.id as string)

const album = ref<Album | null>(null)
const loading = ref(true)
const userAlbumRole = ref<string | null>(null)

// Shared state for children
provide('album', album)
provide('userAlbumRole', userAlbumRole)

async function refreshAlbumRole() {
  try {
    const { data } = await listAlbumMembers(albumId.value)
    const me = data.members.find((m: AlbumMember) => m.user_id === auth.user?.id)
    userAlbumRole.value = me?.role ?? null
  } catch {
    // Silently fail
  }
}

provide('refreshAlbumRole', refreshAlbumRole)

async function fetchAlbumData() {
  loading.value = true
  try {
    const [albumRes, membersRes] = await Promise.all([
      getAlbum(albumId.value),
      listAlbumMembers(albumId.value),
    ])
    album.value = albumRes.data
    const me = membersRes.data.members.find((m: AlbumMember) => m.user_id === auth.user?.id)
    userAlbumRole.value = me?.role ?? null
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('albums.loadAlbumError')), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(fetchAlbumData)
watch(albumId, fetchAlbumData)

const navItems = computed(() => [
  { label: t('albums.photos'), route: 'album-photos' },
  { label: t('albums.members'), route: 'album-members' },
  { label: t('albums.comments'), route: 'album-comments' },
])

const currentRouteName = computed(() => route.name)
</script>

<template>
  <div class="flex flex-col h-full w-full lg:px-layout px-4 py-6 sm:py-8">
    <!-- Back to Albums -->
    <div class="shrink-0 mb-4">
      <router-link
        to="/albums"
        class="text-sm text-brand-600 hover:underline flex items-center gap-1"
      >
        <span>&larr;</span> {{ t('albums.backToAlbums') }}
      </router-link>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-6">
      <SkeletonLoader variant="card" :lines="2" />
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="w-full lg:w-80 shrink-0">
          <SkeletonLoader variant="card" :lines="6" />
        </div>
        <div class="flex-1">
          <SkeletonLoader variant="card" :lines="6" />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="!album" class="text-center py-12">
      <p class="text-lg text-muted mb-4">{{ t('albums.albumNotFound') }}</p>
      <BaseButton @click="router.push('/albums')">{{ t('albums.returnToAlbums') }}</BaseButton>
    </div>

    <!-- Content -->
    <template v-else>
      <div class="shrink-0">
        <BaseCard padding="lg" class="mb-6">
          <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h1 class="text-2xl font-bold text-foreground break-words">{{ album.title }}</h1>
                <BaseBadge v-if="album.is_archived" variant="neutral">{{
                  t('albums.archived')
                }}</BaseBadge>
              </div>
              <p v-if="album.description" class="text-sm text-muted mb-3">
                {{ album.description }}
              </p>
              <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
                <span>{{ t('albums.photosCount', { count: album.photo_count }) }}</span>
                <span>{{ t('albums.membersCount', { count: album.member_count }) }}</span>
                <span>{{
                  t('albums.created', { date: new Date(album.created_at).toLocaleDateString() })
                }}</span>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Main Layout Grid -->
      <div class="flex flex-col lg:flex-row gap-6 lg:gap-16 flex-1 min-h-0">
        <!-- Sidebar Navigation / Tabs -->
        <aside class="w-full lg:w-48 xl:w-64 shrink-0 flex flex-col">
          <!-- Desktop Sidebar -->
          <nav
            class="hidden lg:flex flex-col space-y-1 bg-surface rounded-xl border border-border overflow-hidden shadow-sm"
          >
            <router-link
              v-for="item in navItems"
              :key="item.route"
              :to="{ name: item.route }"
              class="px-4 py-3 text-sm font-medium border-l-4 transition-all duration-200"
              :class="
                currentRouteName === item.route
                  ? 'bg-brand-50 border-brand-600 text-brand-700'
                  : 'border-transparent text-muted hover:bg-surface-alt hover:text-foreground'
              "
            >
              {{ item.label }}
            </router-link>
          </nav>

          <!-- Mobile Tabs -->
          <div class="lg:hidden relative">
            <nav
              class="flex items-center border-b border-border overflow-x-auto no-scrollbar scroll-smooth"
            >
              <router-link
                v-for="item in navItems"
                :key="item.route"
                :to="{ name: item.route }"
                class="px-6 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-all duration-200"
                :class="
                  currentRouteName === item.route
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-muted hover:text-foreground'
                "
              >
                {{ item.label }}
              </router-link>
            </nav>
            <div
              class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none"
            ></div>
          </div>
        </aside>

        <!-- Dynamic Content Panel -->
        <main class="flex-1 min-w-0 overflow-y-auto pr-2 [scrollbar-gutter:stable] pb-12">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
