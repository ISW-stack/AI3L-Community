<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSigPosts } from '@/api/sigs'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useSigLayout } from '@/composables/useSigLayout'
import { usePagination } from '@/composables/usePagination'
import type { Post } from '@/types'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'
import PostCard from '@/components/PostCard.vue'

const { t } = useI18n()
const toast = useToastStore()
const route = useRoute()
const sigId = computed(() => route.params.id as string)
const { sig, userSigRole } = useSigLayout()

const posts = ref<Post[]>([])
const loading = ref(true)
const { page, total, totalPages, pageSize, setPage, resetPage, updateFromResponse } = usePagination()

const isMember = computed(() => userSigRole?.value != null)

async function fetchPosts() {
  loading.value = true
  try {
    const data = await getSigPosts(sigId.value, { page: page.value, page_size: pageSize })
    posts.value = data.posts
    updateFromResponse(data.total, data.total_pages)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('sigs.posts.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchPosts()
}

watch(sigId, () => {
  resetPage()
  fetchPosts()
})

onMounted(fetchPosts)
</script>

<template>
  <div class="space-y-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        { label: sig?.name || '...', to: `/sigs/${sigId}` },
        { label: t('breadcrumb.posts') },
      ]"
    />
    <!-- Header/Actions -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-foreground">
        {{ t('sigs.posts.title') }} ({{ total }})
      </h2>
    </div>

    <!-- Content -->
    <div v-if="loading" class="space-y-3">
      <SkeletonLoader v-for="i in 3" :key="i" variant="card" :lines="2" />
    </div>

    <EmptyState
      v-else-if="posts.length === 0"
      :title="t('sigs.posts.emptyTitle')"
      :message="t('sigs.posts.emptyMessage')"
    />

    <div v-else class="space-y-3">
      <PostCard v-for="p in posts" :key="p.id" :post="p" />
    </div>

    <BasePagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      :page-size="pageSize"
      :total="total"
      class="mt-4"
      @update:current-page="goToPage"
    />

    <FloatingCreateButton v-if="isMember" :to="`/forum/create?sig_id=${sigId}`" />
  </div>
</template>
