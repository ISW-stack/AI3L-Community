<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLocale } from '@/composables/useLocale'
import type { Post } from '@/types'
import { listPosts } from '@/api/posts'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import { usePagination } from '@/composables/usePagination'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import QACard from '@/components/qa/QACard.vue'

const PAGE_SIZE = 20

const { t } = useLocale()
const router = useRouter()
const toast = useToastStore()
const auth = useAuthStore()

const questions = ref<Post[]>([])
const loading = ref(false)

const {
  page,
  total,
  totalPages,
  setPage,
  updateFromResponse,
} = usePagination(PAGE_SIZE)

async function fetchQuestions() {
  loading.value = true
  try {
    const data = await listPosts({
      page: page.value,
      page_size: PAGE_SIZE,
      sort: 'newest',
      type: 'question',
    })
    questions.value = data.posts
    updateFromResponse(data.total ?? 0)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchQuestions()
}

function goToCreate() {
  router.push('/qa/create')
}

onMounted(fetchQuestions)
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 px-4">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.qa') }]"
    />
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('qa.title') }}</h1>
      <BaseButton
        v-if="auth.isAuthenticated && !auth.isGuest"
        @click="goToCreate"
      >
        {{ t('qa.askQuestion') }}
      </BaseButton>
    </div>

    <div v-if="total > 0" class="text-sm text-muted mb-4">
      {{ t('qa.questionCount', { count: total }, total) }}
    </div>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <EmptyState
      v-else-if="questions.length === 0"
      :title="t('qa.noQuestions')"
      :message="t('qa.emptyMessage')"
      :action-label="t('qa.askQuestion')"
      action-to="/qa/create"
    />

    <div v-else class="space-y-3">
      <QACard v-for="q in questions" :key="q.id" :question="q" />
    </div>

    <BasePagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      class="mt-6"
      @update:current-page="goToPage"
    />
  </div>
</template>
