<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePagination } from '@/composables/usePagination'
import { User, Settings, Trash2 } from 'lucide-vue-next'
import type { Notification } from '@/types'
import {
  listNotifications,
  markRead as apiMarkRead,
  deleteNotification,
  bulkDeleteNotifications,
} from '@/api/notifications'
import { relativeTime } from '@/utils/datetime'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useNotificationStore } from '@/stores/notifications'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const { t } = useI18n()
const router = useRouter()
const toast = useToastStore()
const notificationStore = useNotificationStore()
const notifications = ref<Notification[]>([])
const { page, totalPages, pageSize, setPage, updateFromResponse } = usePagination()
const loading = ref(false)
const filter = ref<'all' | 'unread'>('all')
const showClearAllConfirm = ref(false)
let fetchId = 0

function changeFilter(f: 'all' | 'unread') {
  filter.value = f
  setPage(1)
  fetchNotifications()
}

async function fetchNotifications() {
  const localFetchId = ++fetchId
  loading.value = true
  try {
    const data = await listNotifications({
      page: page.value,
      page_size: pageSize,
      ...(filter.value === 'unread' && { unread: true }),
    })
    if (localFetchId !== fetchId) return
    notifications.value = data.notifications
    updateFromResponse(data.total)
    notificationStore.unreadCount = data.unread_count
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('notifications.fetchError')), 'error')
  } finally {
    if (localFetchId === fetchId) {
      loading.value = false
    }
  }
}

async function markRead(notif: Notification) {
  if (!notif.is_read) {
    try {
      await apiMarkRead(notif.id)
      notif.is_read = true
      notificationStore.unreadCount = Math.max(0, notificationStore.unreadCount - 1)
    } catch (e: unknown) {
      toast.show(getErrorMessage(e, t('notifications.markReadError')), 'error')
    }
  }
  navigateToEntity(notif)
}

async function markAllRead() {
  try {
    await notificationStore.markAllRead()
    notifications.value.forEach((n) => (n.is_read = true))
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('notifications.markReadError')), 'error')
  }
}

function navigateToEntity(notif: Notification) {
  if (notif.entity_type === 'friendship') {
    router.push('/friends')
  } else if (notif.action_type === 'CO_AUTHOR_INVITE') {
    router.push('/profile?tab=social')
  } else if (notif.entity_id) {
    router.push(`/forum/${notif.entity_id}`)
  }
}

async function handleDeleteNotification(id: string) {
  try {
    await deleteNotification(id)
    notifications.value = notifications.value.filter((n) => n.id !== id)
    await notificationStore.fetchUnreadCount()
  } catch {
    toast.show(t('notifications.deleteError'), 'error')
  }
}

function handleClearAll() {
  showClearAllConfirm.value = true
}

async function confirmClearAll() {
  showClearAllConfirm.value = false
  try {
    await bulkDeleteNotifications()
    notifications.value = []
    await notificationStore.fetchUnreadCount()
    toast.show(t('notifications.deleteSuccess'), 'success')
  } catch {
    toast.show(t('notifications.deleteError'), 'error')
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchNotifications()
}

onMounted(fetchNotifications)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.notifications') }]"
    />
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('notifications.title') }}</h1>
      <div class="flex items-center gap-3">
        <button
          v-if="notificationStore.unreadCount > 0"
          @click="markAllRead"
          class="text-sm text-brand-600 hover:text-brand-800 hover:underline"
        >
          {{ t('notifications.markAllRead') }} ({{ notificationStore.unreadCount }})
        </button>
        <BaseButton
          v-if="notifications.length > 0"
          variant="soft-danger"
          size="sm"
          @click="handleClearAll"
        >
          {{ t('notifications.clearAllBtn') }}
        </BaseButton>
      </div>
    </div>

    <!-- Filter Tabs -->
    <div class="flex gap-1 mb-4 border-b border-border" role="tablist">
      <button
        id="tab-all"
        role="tab"
        :aria-selected="filter === 'all'"
        aria-controls="panel-notifications"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          filter === 'all'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="changeFilter('all')"
      >
        {{ t('notifications.filter.all') }}
      </button>
      <button
        id="tab-unread"
        role="tab"
        :aria-selected="filter === 'unread'"
        aria-controls="panel-notifications"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          filter === 'unread'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="changeFilter('unread')"
      >
        {{ t('notifications.filter.unread') }}
        <span
          v-if="notificationStore.unreadCount > 0"
          class="ml-1 text-xs bg-brand-100 text-brand-700 rounded-full px-1.5"
          >{{ notificationStore.unreadCount }}</span
        >
      </button>
    </div>

    <div
      id="panel-notifications"
      role="tabpanel"
      :aria-labelledby="filter === 'all' ? 'tab-all' : 'tab-unread'"
    >
      <SkeletonLoader v-if="loading" :lines="5" variant="list" />

      <EmptyState
        v-else-if="notifications.length === 0"
        :message="t('notifications.emptyMessage')"
        :title="t('notifications.emptyTitle')"
      />

      <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
        <div
          v-for="notif in notifications"
          :key="notif.id"
          role="button"
          tabindex="0"
          @click="markRead(notif)"
          @keydown.enter="markRead(notif)"
          class="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-surface-alt transition cursor-pointer"
          :class="{ 'bg-brand-50/40': !notif.is_read }"
        >
          <!-- Avatar -->
          <div
            class="flex-shrink-0 w-10 h-10 rounded-full bg-surface-alt flex items-center justify-center overflow-hidden border border-border"
          >
            <img
              v-if="notif.trigger_user?.avatar_url"
              :src="notif.trigger_user.avatar_url"
              class="w-10 h-10 rounded-full object-cover"
              alt=""
              loading="lazy"
              width="40"
              height="40"
            />
            <component
              :is="notif.action_type === 'SYSTEM' ? Settings : User"
              v-else
              class="w-5 h-5 text-muted"
            />
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <p class="text-sm text-foreground">{{ notif.message }}</p>
            <p class="text-xs text-muted mt-1">{{ relativeTime(notif.created_at) }}</p>
          </div>

          <!-- Unread dot -->
          <div
            v-if="!notif.is_read"
            class="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-brand-600 mt-2"
          ></div>

          <!-- Delete button -->
          <button
            @click.stop="handleDeleteNotification(notif.id)"
            class="flex-shrink-0 p-1 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
            :title="t('common.delete')"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </div>

      <BasePagination
        v-if="totalPages > 1"
        :current-page="page"
        :total-pages="totalPages"
        @update:current-page="goToPage"
        class="mt-6"
      />
    </div>

    <!-- Clear All Confirmation Modal -->
    <BaseModal v-model="showClearAllConfirm" :title="t('notifications.clearAllBtn')" size="sm">
      <p class="text-sm text-muted">
        {{ t('notifications.confirmClearAll', { count: notifications.length }) }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showClearAllConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="confirmClearAll">{{ t('common.confirm') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
