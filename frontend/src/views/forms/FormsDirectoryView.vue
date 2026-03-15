<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { listStandaloneForms } from '@/api/forms'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'
import type { FormData } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const auth = useAuthStore()
const toast = useToastStore()

const forms = ref<FormData[]>([])
const loading = ref(false)
const PAGE_SIZE = 12

const { page, total, totalPages, setPage, updateFromResponse } = usePagination(PAGE_SIZE)

const canCreate = computed(() => auth.isAuthenticated && !auth.isGuest)

async function fetchForms() {
  loading.value = true
  try {
    const data = await listStandaloneForms(page.value, PAGE_SIZE)
    forms.value = data.forms
    updateFromResponse(data.total)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to load forms'), 'error')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

function truncateText(text: string | null, maxLength: number): string {
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
}

function formatDeadline(deadline: string | null): string {
  if (!deadline) return ''
  return new Date(deadline).toLocaleDateString()
}

onMounted(fetchForms)
watch(page, fetchForms)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">Forms</h1>
      <router-link v-if="canCreate" to="/forms/new">
        <BaseButton>Create Form</BaseButton>
      </router-link>
    </div>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <EmptyState
      v-else-if="forms.length === 0"
      title="No forms yet"
      message="There are no standalone forms available at the moment."
    />

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <router-link
          v-for="form in forms"
          :key="form.id"
          :to="`/forms/${form.id}`"
          class="block"
        >
          <BaseCard hoverable class="h-full">
            <div class="flex items-start justify-between gap-2 mb-2">
              <h2 class="text-lg font-semibold text-foreground line-clamp-1">{{ form.title }}</h2>
              <BaseBadge :variant="form.is_active ? 'success' : 'danger'" class="shrink-0">
                {{ form.is_active ? 'Active' : 'Closed' }}
              </BaseBadge>
            </div>
            <p v-if="form.description" class="text-sm text-muted mb-3 line-clamp-2">
              {{ truncateText(form.description, 120) }}
            </p>
            <div class="flex items-center flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <span>{{ form.response_count }} responses</span>
              <span v-if="form.deadline">Due {{ formatDeadline(form.deadline) }}</span>
              <span>By {{ form.created_by_name }}</span>
            </div>
          </BaseCard>
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

    <p class="mt-4 text-xs text-muted">{{ total }} total forms</p>
  </div>
</template>
