<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToastStore } from '@/stores/toast'
import { useFetchPaginated } from '@/composables/useFetchPaginated'
import { getErrorMessage } from '@/utils/error'
import type { IpBan } from '@/api/admin'
import { listIpBans, createIpBan, deleteIpBan } from '@/api/admin'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useI18n()
const toast = useToastStore()

const {
  items: bans,
  loading,
  error: fetchError,
  page,
  total,
  totalPages,
  fetchPage: fetchBans,
  setPage,
} = useFetchPaginated<IpBan>(async (p, ps) => {
  const data = await listIpBans({ page: p, page_size: ps })
  return { items: data.bans, total: data.total }
})

// Create ban modal
const showCreateModal = ref(false)
const newIp = ref('')
const newReason = ref('')
const newExpiresAt = ref('')
const creating = ref(false)

async function handleCreate() {
  if (!newIp.value.trim()) return
  creating.value = true
  try {
    const payload: { ip_address: string; reason?: string; expires_at?: string } = {
      ip_address: newIp.value.trim(),
    }
    if (newReason.value.trim()) payload.reason = newReason.value.trim()
    if (newExpiresAt.value) payload.expires_at = new Date(newExpiresAt.value).toISOString()
    await createIpBan(payload)
    showCreateModal.value = false
    newIp.value = ''
    newReason.value = ''
    newExpiresAt.value = ''
    toast.show(t('admin.ipBans.message.created'), 'success')
    await fetchBans()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.ipBans.message.createFailed')), 'error')
  } finally {
    creating.value = false
  }
}

// Unban
const unbanning = ref<string | null>(null)

async function handleUnban(ban: IpBan) {
  unbanning.value = ban.id
  try {
    await deleteIpBan(ban.id)
    toast.show(t('admin.ipBans.message.removed', { ip: ban.ip_address }), 'success')
    await fetchBans()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.ipBans.message.removeFailed')), 'error')
  } finally {
    unbanning.value = null
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchBans()
}

function formatDate(d: string) {
  return new Date(d).toLocaleString()
}

onMounted(fetchBans)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.admin'), to: '/admin' }, { label: t('admin.ipBans.title') }]"
    />
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.ipBans.title') }}</h1>
      <BaseButton @click="showCreateModal = true">{{ t('admin.ipBans.banBtn') }}</BaseButton>
    </div>

    <BaseAlert v-if="fetchError" type="error" class="mb-4">{{ fetchError }}</BaseAlert>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="bans.length === 0"
      :title="t('admin.ipBans.emptyTitle')"
      :message="t('admin.ipBans.emptyMessage')"
    />

    <div v-else>
      <!-- Mobile card view -->
      <div class="grid gap-3 md:hidden">
        <div
          v-for="ban in bans"
          :key="ban.id"
          class="bg-surface rounded-lg shadow border border-border p-4"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <span class="font-mono font-medium text-foreground">{{ ban.ip_address }}</span>
              <p v-if="ban.reason" class="text-xs text-muted mt-1">{{ ban.reason }}</p>
            </div>
            <BaseButton
              size="sm"
              variant="success"
              :loading="unbanning === ban.id"
              @click="handleUnban(ban)"
              >{{ t('admin.ipBans.unbanBtn') }}</BaseButton
            >
          </div>
          <div class="mt-2 text-xs text-muted">
            <span>{{ formatDate(ban.created_at) }}</span>
            <span v-if="ban.expires_at">
              · {{ t('admin.ipBans.expiresAt') }}: {{ formatDate(ban.expires_at) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Desktop table -->
      <div class="hidden md:block bg-surface rounded-lg shadow overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.ipBans.table.ip') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.ipBans.table.reason') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.ipBans.table.expires') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.ipBans.table.created') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.ipBans.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="ban in bans"
              :key="ban.id"
              class="border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td class="px-4 py-3 font-mono text-foreground">{{ ban.ip_address }}</td>
              <td class="px-4 py-3 text-muted max-w-xs truncate">{{ ban.reason || '-' }}</td>
              <td class="px-4 py-3 text-muted">
                {{ ban.expires_at ? formatDate(ban.expires_at) : t('admin.ipBans.permanent') }}
              </td>
              <td class="px-4 py-3 text-muted">{{ formatDate(ban.created_at) }}</td>
              <td class="px-4 py-3">
                <BaseButton
                  size="sm"
                  variant="success"
                  :loading="unbanning === ban.id"
                  @click="handleUnban(ban)"
                  >{{ t('admin.ipBans.unbanBtn') }}</BaseButton
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="mt-4 flex items-center justify-between">
      <p class="text-sm text-muted">{{ t('admin.ipBans.total', { count: total }) }}</p>
      <BasePagination
        v-if="totalPages > 1"
        :current-page="page"
        :total-pages="totalPages"
        @update:current-page="goToPage"
      />
    </div>

    <!-- Create IP Ban Modal -->
    <BaseModal v-model="showCreateModal" :title="t('admin.ipBans.createModal.title')" size="sm">
      <form class="space-y-3" @submit.prevent="handleCreate">
        <BaseInput
          v-model="newIp"
          :label="t('admin.ipBans.createModal.ipLabel')"
          required
          placeholder="192.168.1.1"
        />
        <BaseTextarea
          v-model="newReason"
          :label="t('admin.ipBans.createModal.reasonLabel')"
          :rows="2"
          :placeholder="t('admin.ipBans.createModal.reasonPlaceholder')"
        />
        <div>
          <label for="ban-expires-at" class="block text-sm font-medium text-foreground mb-1">{{
            t('admin.ipBans.createModal.expiresLabel')
          }}</label>
          <input
            id="ban-expires-at"
            v-model="newExpiresAt"
            type="datetime-local"
            name="expires-at"
            class="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
          />
          <p class="text-xs text-muted mt-1">{{ t('admin.ipBans.createModal.expiresHint') }}</p>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton :loading="creating" @click="handleCreate">{{
          t('admin.ipBans.createModal.confirmBtn')
        }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
