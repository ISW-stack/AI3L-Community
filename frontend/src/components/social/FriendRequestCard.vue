<script setup lang="ts">
import type { FriendRequest } from '@/types/social'
import { relativeTime } from '@/utils/datetime'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'

defineProps<{
  request: FriendRequest
  type: 'incoming' | 'outgoing'
}>()

const emit = defineEmits<{
  accept: [id: string]
  reject: [id: string]
}>()

function handleAccept(id: string) {
  emit('accept', id)
}

function handleReject(id: string) {
  emit('reject', id)
}
</script>

<template>
  <div
    class="flex items-center gap-4 px-4 py-3 bg-surface rounded-lg border border-border"
    data-testid="friend-request-card"
  >
    <router-link
      :to="`/users/${type === 'incoming' ? request.requester_id : request.addressee_id}`"
    >
      <BaseAvatar
        :src="type === 'incoming' ? request.requester_avatar_url : request.addressee_avatar_url"
        :name="type === 'incoming' ? request.requester_name : request.addressee_name"
        size="md"
      />
    </router-link>

    <div class="flex-1 min-w-0">
      <router-link
        :to="`/users/${type === 'incoming' ? request.requester_id : request.addressee_id}`"
        class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
      >
        {{ type === 'incoming' ? request.requester_name : request.addressee_name }}
      </router-link>
      <p class="text-xs text-muted truncate">
        @{{ type === 'incoming' ? request.requester_username : request.addressee_username }}
      </p>
      <p class="text-xs text-muted mt-0.5">{{ relativeTime(request.created_at) }}</p>
    </div>

    <div v-if="type === 'incoming'" class="flex items-center gap-2 shrink-0">
      <BaseButton size="sm" @click="handleAccept(request.id)">Accept</BaseButton>
      <BaseButton size="sm" variant="secondary" @click="handleReject(request.id)">
        Decline
      </BaseButton>
    </div>

    <div v-else class="shrink-0">
      <BaseBadge variant="neutral" size="md">Pending</BaseBadge>
    </div>
  </div>
</template>
