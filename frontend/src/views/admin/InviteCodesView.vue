<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import type { InviteCode } from '@/types'
import { listInviteCodes, createInviteCode } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

const toastStore = useToastStore()
const codes = ref<InviteCode[]>([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref<string | null>(null)
const generating = ref(false)
const message = ref('')
const copiedId = ref<string | null>(null)

async function fetchCodes() {
  loading.value = true
  try {
    const data = await listInviteCodes({ status: statusFilter.value || undefined })
    codes.value = data.codes
    total.value = data.total
  } catch {
    /* silent */
  } finally {
    loading.value = false
  }
}

async function generateCode() {
  generating.value = true
  message.value = ''
  try {
    const data = await createInviteCode()
    try {
      await navigator.clipboard.writeText(data.invite_code)
      toastStore.show(`Code generated and copied: ${data.invite_code}`, 'success')
    } catch {
      message.value = `Generated: ${data.invite_code}`
    }
    await fetchCodes()
  } catch {
    toastStore.show('Failed to generate code.', 'error')
  } finally {
    generating.value = false
  }
}

async function copyCode(code: string, codeId: string) {
  try {
    await navigator.clipboard.writeText(code)
    copiedId.value = codeId
    toastStore.show('Code copied to clipboard.', 'success')
    setTimeout(() => {
      if (copiedId.value === codeId) copiedId.value = null
    }, 2000)
  } catch {
    toastStore.show('Failed to copy code.', 'error')
  }
}

const statusBadge: Record<string, 'success' | 'neutral' | 'danger'> = {
  active: 'success',
  consumed: 'neutral',
  expired: 'danger',
}

onMounted(fetchCodes)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Invite Codes</h1>
      <BaseButton :loading="generating" @click="generateCode">Generate Code</BaseButton>
    </div>

    <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>

    <!-- Filter -->
    <div class="mb-4">
      <select
        v-model="statusFilter"
        @change="fetchCodes"
        class="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option :value="null">All Statuses</option>
        <option value="active">Active</option>
        <option value="consumed">Consumed</option>
        <option value="expired">Expired</option>
      </select>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState v-else-if="codes.length === 0" message="No invite codes found." title="No Codes" />

    <div v-else class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
      <table class="w-full text-sm min-w-[650px]">
        <thead class="bg-surface-alt text-left border-b border-border">
          <tr>
            <th class="px-4 py-3 font-medium text-muted">Code</th>
            <th class="px-4 py-3 font-medium text-muted">Status</th>
            <th class="px-4 py-3 font-medium text-muted">Created By</th>
            <th class="px-4 py-3 font-medium text-muted">Used By</th>
            <th class="px-4 py-3 font-medium text-muted">Created</th>
            <th class="px-4 py-3 font-medium text-muted">Expires</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          <tr v-for="code in codes" :key="code.id" class="hover:bg-surface-alt transition">
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <code class="font-mono text-xs text-foreground">{{ code.code }}</code>
                <button
                  @click="copyCode(code.code, code.id)"
                  class="p-1 rounded hover:bg-surface-alt text-muted hover:text-foreground transition"
                  :aria-label="`Copy invite code ${code.code}`"
                >
                  <Check v-if="copiedId === code.id" class="w-3.5 h-3.5 text-success-600" aria-hidden="true" />
                  <Copy v-else class="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            </td>
            <td class="px-4 py-3">
              <BaseBadge :variant="statusBadge[code.status] || 'neutral'">{{
                code.status
              }}</BaseBadge>
            </td>
            <td class="px-4 py-3 text-muted">{{ code.creator_username || '—' }}</td>
            <td class="px-4 py-3 text-muted">{{ code.consumed_by_username || '—' }}</td>
            <td class="px-4 py-3 text-muted text-xs">
              {{ new Date(code.created_at).toLocaleDateString() }}
            </td>
            <td class="px-4 py-3 text-muted text-xs">
              {{ code.expires_at ? new Date(code.expires_at).toLocaleDateString() : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mt-4 text-xs text-muted">{{ total }} code(s) total</p>
  </div>
</template>
