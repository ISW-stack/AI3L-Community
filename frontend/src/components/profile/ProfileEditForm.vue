<script setup lang="ts">
import { useLocale } from '@/composables/useLocale'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import TiptapEditor from '@/components/TiptapEditor.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const { t } = useLocale()

const displayName = defineModel<string>('displayName', { required: true })
const bio = defineModel<string>('bio', { required: true })
const affiliation = defineModel<string>('affiliation', { required: true })
const orcid = defineModel<string>('orcid', { required: true })

const emit = defineEmits<{
  save: []
  'upload-avatar': [event: Event]
}>()

defineProps<{
  username: string
  avatarUrl: string | null
  userRole: string | null | undefined
  storageUsed: number
  storageQuota: number
  storagePercent: number
  storageLoading: boolean
  storageError: boolean
  isGuest: boolean
  saving: boolean
  displayNameInitial: string
}>()

function roleBadgeVariant(
  role: string | null | undefined,
): 'brand' | 'success' | 'warning' | 'purple' | 'neutral' {
  switch (role) {
    case 'SUPER_ADMIN':
      return 'purple'
    case 'ADMIN':
      return 'warning'
    case 'MEMBER':
      return 'brand'
    case 'GUEST':
      return 'neutral'
    default:
      return 'neutral'
  }
}

function roleBadgeLabel(role: string | null | undefined): string {
  switch (role) {
    case 'SUPER_ADMIN':
      return t('common.role.superAdmin')
    case 'ADMIN':
      return t('common.role.admin')
    case 'MEMBER':
      return t('common.role.member')
    case 'GUEST':
      return t('common.role.guest')
    default:
      return role || 'Unknown'
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}
</script>

<template>
  <div>
    <!-- Avatar -->
    <div class="flex flex-col sm:flex-row items-center sm:items-start gap-4 mb-6">
    <div
      class="w-20 h-20 rounded-full bg-surface-alt flex items-center justify-center overflow-hidden border border-border"
    >
      <img
        v-if="avatarUrl"
        :src="avatarUrl"
        class="w-full h-full object-cover"
        alt="Avatar"
        loading="lazy"
        width="80"
        height="80"
      />
      <span v-else class="text-2xl text-muted">{{ displayNameInitial }}</span>
    </div>
    <label class="text-sm text-brand-600 hover:underline cursor-pointer">
      {{ t('profile.changeAvatar') }}
      <input
        type="file"
        accept="image/png,image/jpeg"
        class="hidden"
        @change="emit('upload-avatar', $event)"
      />
    </label>
  </div>

  <!-- Member Info -->
  <BaseCard padding="lg" class="mb-6">
    <h2 class="text-sm font-medium text-muted mb-3">{{ t('profile.memberInfo') }}</h2>
    <div class="flex items-center gap-3">
      <span class="text-sm text-foreground font-medium">{{ username || '---' }}</span>
      <BaseBadge :variant="roleBadgeVariant(userRole)">{{ roleBadgeLabel(userRole) }}</BaseBadge>
    </div>
  </BaseCard>

  <!-- Storage Usage -->
  <BaseCard v-if="!isGuest" padding="lg" class="mb-6">
    <h2 class="text-sm font-medium text-muted mb-3">{{ t('profile.storage.title') }}</h2>
    <div v-if="storageLoading" class="text-sm text-muted">{{ t('common.loading') }}</div>
    <div v-else-if="storageError" class="text-sm text-danger-600">
      {{ t('profile.storage.fetchError') }}
    </div>
    <div v-else>
      <div class="flex justify-between text-sm text-foreground mb-1.5">
        <span>{{
          t('profile.storage.used', {
            used: formatBytes(storageUsed),
            total: formatBytes(storageQuota),
          })
        }}</span>
        <span class="text-muted">{{ storagePercent }}%</span>
      </div>
      <div class="w-full bg-surface-alt rounded-full h-2">
        <div
          class="h-2 rounded-full transition-all"
          :class="
            storagePercent >= 90
              ? 'bg-danger-500'
              : storagePercent >= 70
                ? 'bg-warning-500'
                : 'bg-brand-500'
          "
          :style="{ width: `${Math.min(storagePercent, 100)}%` }"
        ></div>
      </div>
    </div>
  </BaseCard>

  <!-- Profile Form -->
  <BaseCard padding="lg" class="mb-8">
    <form @submit.prevent="emit('save')" class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('profile.form.usernameLabel')
        }}</label>
        <input
          :value="username"
          disabled
          class="w-full px-3 py-2 bg-surface-alt border border-border rounded-lg text-muted"
        />
      </div>

      <BaseInput
        v-model="displayName"
        :label="t('profile.form.displayNameLabel')"
        :maxlength="100"
      />
      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('profile.form.bioLabel')
        }}</label>
        <TiptapEditor v-model="bio" />
      </div>
      <BaseInput
        v-model="affiliation"
        :label="t('profile.form.affiliationLabel')"
        :maxlength="200"
      />
      <BaseInput
        v-model="orcid"
        :label="t('profile.form.orcidLabel')"
        :maxlength="50"
        :placeholder="t('profile.form.orcidPlaceholder')"
      />

      <!-- Language selector -->
      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('profile.form.languageLabel')
        }}</label>
        <LanguageSwitcher variant="form" />
      </div>

      <BaseButton type="submit" :loading="saving">{{ t('profile.form.saveBtn') }}</BaseButton>
    </form>
  </BaseCard>
  </div>
</template>
