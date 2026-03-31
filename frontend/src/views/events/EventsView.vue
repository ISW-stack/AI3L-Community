<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useLocale } from '@/composables/useLocale'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { listEvents } from '@/api/events'
import { getErrorMessage } from '@/utils/error'
import { formatDate } from '@/utils/date'
import { usePagination } from '@/composables/usePagination'
import type { Event } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'

const { t, currentLocale } = useLocale()
const auth = useAuthStore()
const toast = useToastStore()

const events = ref<Event[]>([])
const loading = ref(false)
const initialLoading = ref(true)
const PAGE_SIZE = 20
let _fetchId = 0

const { page, total, totalPages, setPage, updateFromResponse } = usePagination(PAGE_SIZE)

const canCreate = computed(() => auth.isAdmin)

async function fetchEvents() {
  const fetchId = ++_fetchId
  loading.value = true
  try {
    const data = await listEvents({ page: page.value, page_size: PAGE_SIZE })
    if (fetchId !== _fetchId) return
    events.value = data.events
    updateFromResponse(data.total, data.total_pages)
  } catch (e: unknown) {
    if (fetchId !== _fetchId) return
    toast.show(getErrorMessage(e, t('events.fetchError')), 'error')
  } finally {
    if (fetchId === _fetchId) {
      loading.value = false
      initialLoading.value = false
    }
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

function visibilityLabel(role: string): string {
  const map: Record<string, string> = {
    GUEST: t('events.roleGuest'),
    MEMBER: t('events.roleMember'),
    ADMIN: t('events.roleAdmin'),
    SUPER_ADMIN: t('events.roleSuperAdmin'),
  }
  return map[role] || role
}

onMounted(fetchEvents)
watch(page, fetchEvents)
</script>

<template>
  <div class="w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
    <div class="max-w-[1340px] mx-auto">
      <BaseBreadcrumb
        :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.events') }]"
      />
      <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center mb-6">
        <h1 class="text-2xl font-bold text-foreground">{{ t('events.title') }}</h1>
        <router-link v-if="canCreate" to="/events/create" class="shrink-0">
          <BaseButton>{{ t('events.createEvent') }}</BaseButton>
        </router-link>
      </div>

      <SkeletonLoader v-if="initialLoading" :lines="3" variant="card" />

      <div v-else class="min-h-[400px]">
        <div
          :class="{ 'opacity-50 pointer-events-none': loading }"
          class="transition-opacity duration-150"
        >
          <EmptyState
            v-if="events.length === 0"
            :title="t('events.noEvents')"
            :message="t('events.noEventsMessage')"
          />

          <template v-else>
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <BaseCard
                v-for="ev in events"
                :key="ev.id"
                class="h-full group hover:border-brand-300 transition-all flex flex-col"
              >
                <div class="flex items-start justify-between mb-2">
                  <router-link
                    :to="`/events/${ev.id}`"
                    class="font-bold text-foreground group-hover:text-brand-600 transition-colors leading-tight"
                  >
                    {{ ev.title }}
                  </router-link>
                </div>

                <div class="flex flex-wrap gap-1 mb-3">
                  <BaseBadge v-for="role in ev.visibility" :key="role" variant="brand" size="sm">
                    {{ visibilityLabel(role) }}
                  </BaseBadge>
                </div>

                <div class="mt-auto">
                  <div
                    class="flex items-center flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted font-medium uppercase tracking-tight"
                  >
                    <span>{{ t('common.by') }} {{ ev.author.display_name }}</span>
                    <span>{{ formatDate(ev.created_at, currentLocale) }}</span>
                    <span v-if="ev.comment_count > 0">
                      {{ ev.comment_count }} {{ t('events.comments') }}
                    </span>
                    <router-link
                      v-if="ev.sig_name"
                      :to="`/sigs/${ev.sig_id}`"
                      class="text-brand-600 hover:underline"
                    >
                      {{ ev.sig_name }}
                    </router-link>
                  </div>
                </div>
              </BaseCard>
            </div>

            <div class="mt-6">
              <BasePagination
                v-if="totalPages > 1"
                :current-page="page"
                :total-pages="totalPages"
                :page-size="PAGE_SIZE"
                :total="total"
                @update:current-page="handlePageChange"
              />
            </div>
          </template>
        </div>
      </div>

      <FloatingCreateButton v-if="canCreate" to="/events/create" />
    </div>
  </div>
</template>
