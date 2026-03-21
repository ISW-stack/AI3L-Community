<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getMembers } from '@/api/about'
import { usePagination } from '@/composables/usePagination'
import type { MemberCard } from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { getErrorMessage } from '@/utils/error'
import { Search } from 'lucide-vue-next'

const { t } = useI18n()
const router = useRouter()
const members = ref<MemberCard[]>([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const { page, total, totalPages, setPage, updateFromResponse } = usePagination(24)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const roleBadgeVariant: Record<string, 'danger' | 'orange' | 'brand' | 'neutral'> = {
  SUPER_ADMIN: 'danger',
  ADMIN: 'orange',
  MEMBER: 'brand',
}

const roleLabel: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  MEMBER: 'Member',
}

async function fetchMembers() {
  loading.value = true
  error.value = ''
  try {
    const data = await getMembers({
      page: page.value,
      page_size: 24,
      search: searchQuery.value || undefined,
    })
    members.value = data.members
    updateFromResponse(data.total, Math.ceil(data.total / 24))
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    setPage(1)
    fetchMembers()
  }, 300)
}

onUnmounted(() => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})

function navigateToProfile(userId: string) {
  router.push(`/users/${userId}`)
}

function handleAvatarError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
  const parent = img.parentElement
  if (parent) {
    const fallback = parent.querySelector('.avatar-fallback') as HTMLElement | null
    if (fallback) fallback.style.display = 'flex'
  }
}

watch(page, fetchMembers)
onMounted(fetchMembers)
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold text-foreground mb-2">{{ t('members.title') }}</h1>
    <p class="text-muted mb-6">{{ t('members.subtitle') }}</p>

    <!-- Search -->
    <div class="relative mb-6 max-w-md">
      <Search
        class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted"
        aria-hidden="true"
      />
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="t('members.searchPlaceholder')"
        class="w-full pl-10 pr-4 py-2 text-sm border border-border rounded-lg bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-200"
        @input="handleSearch"
      />
    </div>

    <div v-if="error" class="text-danger-600 mb-4">{{ error }}</div>

    <div v-if="loading">
      <SkeletonLoader variant="list" :lines="8" />
    </div>

    <template v-else>
      <div v-if="members.length === 0" class="text-muted py-8 text-center">
        {{ t('common.noResults') }}
      </div>

      <div
        v-else
        class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"
      >
        <div
          v-for="member in members"
          :key="member.id"
          class="bg-surface border border-border rounded-xl p-5 hover:shadow-md transition cursor-pointer"
          @click="navigateToProfile(member.id)"
        >
          <div class="flex flex-col items-center text-center">
            <div class="relative w-16 h-16 mb-3">
              <img
                v-if="member.avatar_url"
                :src="member.avatar_url"
                :alt="member.display_name"
                class="w-16 h-16 rounded-full object-cover border border-border"
                loading="lazy"
                width="64"
                height="64"
                @error="handleAvatarError"
              />
              <div
                class="avatar-fallback w-16 h-16 rounded-full bg-brand-100 text-brand-700 items-center justify-center text-xl font-semibold absolute inset-0"
                :style="{ display: member.avatar_url ? 'none' : 'flex' }"
              >
                {{ member.display_name.charAt(0).toUpperCase() }}
              </div>
            </div>
            <h3 class="text-sm font-semibold text-foreground truncate w-full">
              {{ member.display_name }}
            </h3>
            <BaseBadge
              :variant="roleBadgeVariant[member.role] || 'neutral'"
              size="sm"
              class="mt-1"
            >
              {{ roleLabel[member.role] || member.role }}
            </BaseBadge>
            <p
              v-if="member.affiliation"
              class="text-xs text-muted mt-2 truncate w-full"
            >
              {{ member.affiliation }}
            </p>
            <p
              v-if="member.bio"
              class="text-xs text-muted mt-1 line-clamp-2 w-full"
            >
              {{ member.bio }}
            </p>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex justify-center items-center gap-4 mt-8">
        <button
          class="px-4 py-2 text-sm border border-border rounded-lg hover:bg-surface-alt transition disabled:opacity-50"
          :disabled="page <= 1"
          @click="setPage(page - 1)"
        >
          {{ t('common.prev') }}
        </button>
        <span class="text-sm text-muted">
          {{ page }} / {{ totalPages }} ({{ total }})
        </span>
        <button
          class="px-4 py-2 text-sm border border-border rounded-lg hover:bg-surface-alt transition disabled:opacity-50"
          :disabled="page >= totalPages"
          @click="setPage(page + 1)"
        >
          {{ t('common.next') }}
        </button>
      </div>
    </template>
  </div>
</template>
