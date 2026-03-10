<script setup lang="ts">
import { ref, onMounted, computed, inject, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import {
  getSigMembers,
  removeMember as removeMemberApi,
  assignSubAdmin as assignSubAdminApi,
} from '@/api/sigs'
import { getErrorMessage } from '@/utils/error'
import type { SigMember } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const toastStore = useToastStore()

const sigId = computed(() => route.params.id as string)
const userSigRole = inject<Ref<string | null>>('userSigRole', ref(null))

const members = ref<SigMember[]>([])
const total = ref(0)
const loading = ref(true)

const isSigAdmin = computed(
  () => userSigRole?.value === 'ADMIN' || userSigRole?.value === 'SUB_ADMIN',
)
const canEdit = computed(() => auth.isAdmin || isSigAdmin.value)

const memberRoleBadge: Record<string, 'orange' | 'purple' | 'brand'> = {
  ADMIN: 'orange',
  SUB_ADMIN: 'purple',
  MEMBER: 'brand',
}

async function fetchMembers() {
  loading.value = true
  try {
    const data = await getSigMembers(sigId.value)
    members.value = data.members
    total.value = data.total
  } catch (e) {
    console.error('Failed to fetch members:', e)
  } finally {
    loading.value = false
  }
}

function canRemoveMember(m: SigMember) {
  if (m.user_id === auth.user?.id) return false
  return auth.isAdmin || isSigAdmin.value
}

async function handleRemoveMember(userId: string) {
  try {
    await removeMemberApi(sigId.value, userId)
    await fetchMembers()
    toastStore.show(t('sigs.members.removeSuccess'), 'info')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.removeError')), 'error')
  }
}

async function handleAssignSubAdmin(userId: string) {
  try {
    await assignSubAdminApi(sigId.value, userId)
    await fetchMembers()
    toastStore.show(t('sigs.members.promoteSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.promoteError')), 'error')
  }
}

onMounted(fetchMembers)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-foreground">
      {{ t('sigs.members.title') }} ({{ total }})
    </h2>

    <div v-if="loading" class="space-y-3">
      <SkeletonLoader variant="card" :lines="4" />
    </div>

    <EmptyState
      v-else-if="members.length === 0"
      :title="t('sigs.members.emptyTitle')"
      :message="t('sigs.members.emptyMessage')"
    />

    <div v-else class="space-y-4">
      <!-- Desktop Table View -->
      <div
        class="hidden md:block bg-surface border border-border rounded-xl overflow-hidden shadow-sm"
      >
        <table class="w-full text-sm">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.name') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.username') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.role') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.joined') }}
              </th>
              <th
                v-if="canEdit"
                class="text-right px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.actions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="m in members" :key="m.id" class="hover:bg-brand-50/30 transition-colors">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-3">
                  <router-link :to="`/users/${m.user_id}`">
                    <BaseAvatar :src="m.avatar_url" :name="m.display_name" size="sm" />
                  </router-link>
                  <router-link
                    :to="`/users/${m.user_id}`"
                    class="font-medium text-foreground hover:text-brand-600 transition-colors"
                  >
                    {{ m.display_name }}
                  </router-link>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-muted">@{{ m.username }}</td>
              <td class="px-6 py-4 whitespace-nowrap">
                <BaseBadge :variant="memberRoleBadge[m.role] || 'brand'" size="sm">
                  {{ m.role.replace('_', ' ') }}
                </BaseBadge>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs text-muted">
                {{ new Date(m.created_at).toLocaleDateString() }}
              </td>
              <td v-if="canEdit" class="px-6 py-4 whitespace-nowrap text-right space-x-3 text-xs">
                <button
                  v-if="auth.isAdmin && m.role === 'MEMBER'"
                  @click="handleAssignSubAdmin(m.user_id)"
                  class="text-brand-600 hover:text-brand-700 font-medium hover:underline"
                >
                  {{ t('sigs.members.promoteBtn') }}
                </button>
                <button
                  v-if="canRemoveMember(m)"
                  @click="handleRemoveMember(m.user_id)"
                  class="text-danger-600 hover:text-danger-700 font-medium hover:underline"
                >
                  {{ t('sigs.members.removeBtn') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile Card View -->
      <div class="grid gap-3 md:hidden">
        <BaseCard v-for="m in members" :key="m.id" padding="md">
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <BaseAvatar :src="m.avatar_url" :name="m.display_name" size="md" />
              <div class="min-w-0">
                <router-link
                  :to="`/users/${m.user_id}`"
                  class="font-bold text-foreground hover:text-brand-600 block truncate"
                >
                  {{ m.display_name }}
                </router-link>
                <div class="text-xs text-muted">@{{ m.username }}</div>
              </div>
            </div>
            <BaseBadge :variant="memberRoleBadge[m.role] || 'brand'" size="sm">
              {{ m.role.replace('_', ' ') }}
            </BaseBadge>
          </div>

          <div class="mt-4 pt-3 border-t border-border flex items-center justify-between">
            <span class="text-[10px] text-muted">
              {{ t('sigs.members.tableHeader.joined') }}
              {{ new Date(m.created_at).toLocaleDateString() }}
            </span>

            <div v-if="canEdit" class="flex gap-3">
              <button
                v-if="auth.isAdmin && m.role === 'MEMBER'"
                @click="handleAssignSubAdmin(m.user_id)"
                class="text-xs text-brand-600 font-medium"
              >
                {{ t('sigs.members.promoteBtn') }}
              </button>
              <button
                v-if="canRemoveMember(m)"
                @click="handleRemoveMember(m.user_id)"
                class="text-xs text-danger-600 font-medium"
              >
                {{ t('sigs.members.removeBtn') }}
              </button>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>
