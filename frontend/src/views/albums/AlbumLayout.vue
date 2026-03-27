<script setup lang="ts">
import { ref, computed, onMounted, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import {
  getAlbum,
  listAlbumMembers,
  deleteAlbum,
  updateAlbum,
  uploadAlbumCover,
} from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import { formatDate } from '@/utils/date'
import type { Album, AlbumMember } from '@/types/album'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const { t, currentLocale } = useLocale()
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
    const membersData = await listAlbumMembers(albumId.value)
    const me = membersData.members.find((m: AlbumMember) => m.user_id === auth.user?.id)
    userAlbumRole.value = me?.role ?? null
  } catch {
    // Silently fail
  }
}

provide('refreshAlbumRole', refreshAlbumRole)

const canEditAlbum = computed(() => {
  if (!album.value || !auth.user) return false
  return (
    album.value.created_by === auth.user.id ||
    auth.isSuperAdmin ||
    auth.isAdmin ||
    userAlbumRole.value === 'ADMIN'
  )
})

const canDeleteAlbum = computed(() => {
  if (!album.value || !auth.user) return false
  return album.value.created_by === auth.user.id || auth.isSuperAdmin
})

const editing = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const saving = ref(false)

function startEditing() {
  if (!album.value) return
  editTitle.value = album.value.title
  editDescription.value = album.value.description || ''
  editing.value = true
}

function cancelEditing() {
  editing.value = false
}

async function handleSaveEdit() {
  if (!album.value || !editTitle.value.trim()) return
  saving.value = true
  try {
    const updated = await updateAlbum(album.value.id, {
      title: editTitle.value.trim(),
      description: editDescription.value.trim() || null,
    })
    album.value = updated
    editing.value = false
    toastStore.show(t('albums.editAlbumSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('albums.editAlbumError')), 'error')
  } finally {
    saving.value = false
  }
}

const coverFileInput = ref<HTMLInputElement | null>(null)
const uploadingCover = ref(false)

function triggerCoverUpload() {
  coverFileInput.value?.click()
}

async function handleCoverFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !album.value) return
  input.value = ''
  uploadingCover.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const updated = await uploadAlbumCover(album.value.id, formData)
    album.value = updated
    toastStore.show(t('albums.uploadCoverSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('albums.uploadCoverError')), 'error')
  } finally {
    uploadingCover.value = false
  }
}

const deleting = ref(false)
const showDeleteModal = ref(false)

function handleDeleteAlbum() {
  showDeleteModal.value = true
}

async function confirmDeleteAlbum() {
  if (!album.value) return
  deleting.value = true
  try {
    await deleteAlbum(album.value.id)
    showDeleteModal.value = false
    toastStore.show(t('albums.deleteAlbumSuccess'), 'success')
    router.push('/albums')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('albums.deleteAlbumError')), 'error')
  } finally {
    deleting.value = false
  }
}

async function fetchAlbumData() {
  loading.value = true
  try {
    const [albumData, membersData] = await Promise.all([
      getAlbum(albumId.value),
      listAlbumMembers(albumId.value),
    ])
    album.value = albumData
    const me = membersData.members.find((m: AlbumMember) => m.user_id === auth.user?.id)
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
          <!-- Cover image -->
          <div
            v-if="album.cover_photo_url || canEditAlbum"
            class="relative -mx-6 -mt-6 mb-4 h-48 bg-surface-alt rounded-t-xl overflow-hidden"
          >
            <img
              v-if="album.cover_photo_url"
              :src="album.cover_photo_url"
              :alt="album.title"
              class="w-full h-full object-cover"
            />
            <div v-else class="w-full h-full bg-gradient-to-br from-brand-400 to-brand-600" />
            <button
              v-if="canEditAlbum"
              type="button"
              class="absolute bottom-3 right-3 flex items-center gap-1.5 text-xs text-white bg-black/50 hover:bg-black/70 px-3 py-1.5 rounded-lg transition"
              :disabled="uploadingCover"
              @click="triggerCoverUpload"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              {{ uploadingCover ? '...' : t('albums.changeCover') }}
            </button>
            <input
              ref="coverFileInput"
              type="file"
              name="album-cover"
              accept="image/jpeg,image/png,image/webp,image/gif"
              class="hidden"
              @change="handleCoverFileChange"
            />
          </div>
          <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div class="min-w-0 flex-1">
              <!-- Edit mode -->
              <template v-if="editing">
                <div class="space-y-3">
                  <div>
                    <label
                      for="album-edit-title"
                      class="block text-sm font-medium text-foreground mb-1"
                      >{{ t('albums.titleLabel') }}</label
                    >
                    <input
                      id="album-edit-title"
                      v-model="editTitle"
                      type="text"
                      name="album-title"
                      class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
                      :placeholder="t('albums.titlePlaceholder')"
                    />
                  </div>
                  <div>
                    <label
                      for="album-edit-desc"
                      class="block text-sm font-medium text-foreground mb-1"
                      >{{ t('albums.descriptionLabel') }}</label
                    >
                    <textarea
                      id="album-edit-desc"
                      v-model="editDescription"
                      rows="3"
                      name="album-description"
                      class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground resize-none"
                      :placeholder="t('albums.descriptionPlaceholder')"
                    ></textarea>
                  </div>
                  <div class="flex gap-2">
                    <BaseButton
                      size="sm"
                      :loading="saving"
                      :disabled="!editTitle.trim()"
                      @click="handleSaveEdit"
                    >
                      {{ t('common.save') }}
                    </BaseButton>
                    <BaseButton size="sm" variant="secondary" @click="cancelEditing">
                      {{ t('common.cancel') }}
                    </BaseButton>
                  </div>
                </div>
              </template>
              <!-- Display mode -->
              <template v-else>
                <div class="flex items-center gap-3 mb-2">
                  <h1 class="text-2xl font-bold text-foreground break-words">{{ album.title }}</h1>
                  <BaseBadge v-if="album.is_archived" variant="neutral">{{
                    t('albums.archived')
                  }}</BaseBadge>
                  <button
                    v-if="canEditAlbum"
                    type="button"
                    class="text-muted hover:text-brand-600 transition-colors"
                    :title="t('albums.editAlbum')"
                    @click="startEditing"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      class="h-4 w-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
                      />
                    </svg>
                  </button>
                </div>
                <p v-if="album.description" class="text-sm text-muted mb-3">
                  {{ album.description }}
                </p>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
                  <span>{{ t('albums.photosCount', { count: album.photo_count }) }}</span>
                  <span>{{ t('albums.membersCount', { count: album.member_count }) }}</span>
                  <span>{{
                    t('albums.created', { date: formatDate(album.created_at, currentLocale) })
                  }}</span>
                </div>
              </template>
            </div>
            <BaseButton
              v-if="canDeleteAlbum && !editing"
              variant="danger"
              size="sm"
              :loading="deleting"
              @click="handleDeleteAlbum"
            >
              {{ t('albums.deleteAlbum') }}
            </BaseButton>
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
                class="px-3 sm:px-6 py-2.5 sm:py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-all duration-200"
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

    <!-- F-26: Delete confirmation modal (replaces native confirm()) -->
    <BaseModal
      :model-value="showDeleteModal"
      :title="t('albums.deleteAlbum')"
      size="sm"
      @update:model-value="showDeleteModal = false"
    >
      <p class="text-sm text-muted mb-4">{{ t('albums.confirmDeleteAlbum') }}</p>
      <div class="flex justify-end gap-3">
        <button
          @click="showDeleteModal = false"
          class="px-4 py-2 text-sm font-medium text-foreground bg-surface-alt border border-border rounded-lg hover:bg-gray-100 transition"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          @click="confirmDeleteAlbum"
          :disabled="deleting"
          class="px-4 py-2 text-sm font-medium text-white bg-danger-600 rounded-lg hover:bg-danger-700 transition disabled:opacity-50"
        >
          {{ deleting ? '...' : t('albums.deleteAlbum') }}
        </button>
      </div>
    </BaseModal>
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
