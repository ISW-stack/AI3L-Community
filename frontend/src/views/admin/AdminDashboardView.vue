<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToastStore } from '@/stores/toast'
import { Users, FileText, UsersRound, ClipboardList, Flag, UserPlus } from 'lucide-vue-next'
import { getErrorMessage } from '@/utils/error'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import type { DashboardStats } from '@/types'
import { getDashboard } from '@/api/admin'

const { t } = useI18n()
const toast = useToastStore()
const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

async function fetchStats() {
  loading.value = true
  try {
    stats.value = await getDashboard()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.dashboard.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

const cards = [
  {
    key: 'users',
    labelKey: 'admin.dashboard.card.users',
    icon: Users,
    bg: 'bg-brand-50',
    text: 'text-brand-700',
    iconColor: 'text-brand-600',
  },
  {
    key: 'posts',
    labelKey: 'admin.dashboard.card.posts',
    icon: FileText,
    bg: 'bg-success-50',
    text: 'text-success-600',
    iconColor: 'text-success-600',
  },
  {
    key: 'sigs',
    labelKey: 'admin.dashboard.card.sigs',
    icon: UsersRound,
    bg: 'bg-info-50',
    text: 'text-info-600',
    iconColor: 'text-info-600',
  },
  {
    key: 'forms',
    labelKey: 'admin.dashboard.card.forms',
    icon: ClipboardList,
    bg: 'bg-info-50',
    text: 'text-info-600',
    iconColor: 'text-info-600',
  },
  {
    key: 'pending_reports',
    labelKey: 'admin.dashboard.card.pendingReports',
    icon: Flag,
    bg: 'bg-warning-50',
    text: 'text-warning-600',
    iconColor: 'text-warning-600',
  },
  {
    key: 'pending_applications',
    labelKey: 'admin.dashboard.card.pendingApplications',
    icon: UserPlus,
    bg: 'bg-danger-50',
    text: 'text-danger-600',
    iconColor: 'text-danger-600',
  },
] as const

onMounted(fetchStats)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.dashboard') },
      ]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('admin.dashboard.title') }}</h1>

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />

    <EmptyState v-else-if="!stats" :message="t('admin.dashboard.noData')" />

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <BaseCard v-for="card in cards" :key="card.key" padding="lg">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">{{ t(card.labelKey) }}</p>
              <p class="text-3xl font-bold" :class="card.text">
                {{ stats[card.key] }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-lg flex items-center justify-center" :class="card.bg">
              <component :is="card.icon" class="w-6 h-6" :class="card.iconColor" />
            </div>
          </div>
        </BaseCard>
      </div>

      <BaseCard padding="lg" class="mt-6">
        <h2 class="text-lg font-semibold text-foreground mb-4">
          {{ t('admin.dashboard.quickActions') }}
        </h2>
        <div class="flex flex-wrap gap-3">
          <router-link to="/admin/users">
            <BaseButton variant="secondary" size="sm">{{
              t('admin.dashboard.action.manageUsers')
            }}</BaseButton>
          </router-link>
          <router-link to="/admin/applications">
            <BaseButton variant="secondary" size="sm">{{
              t('admin.dashboard.action.reviewApplications')
            }}</BaseButton>
          </router-link>
          <router-link to="/admin/reports">
            <BaseButton variant="secondary" size="sm">{{
              t('admin.dashboard.action.viewReports')
            }}</BaseButton>
          </router-link>
        </div>
      </BaseCard>
    </template>
  </div>
</template>
