<script setup lang="ts">
import { reactive } from 'vue'
import type { Conversation } from '@/types/dm'
import { relativeTime } from '@/utils/datetime'
import { MessageSquare } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  conversations: Conversation[]
  activeId: string | null
  loading: boolean
}>()

const emit = defineEmits<{
  select: [conversationId: string, otherUserId: string]
}>()

const avatarFailed = reactive<Record<string, boolean>>({})

function handleSelect(conv: Conversation) {
  emit('select', conv.id, conv.other_user.id)
}

function getLastMessagePreview(conv: Conversation): string {
  if (!conv.last_message) return t('dm.noMessagePreview')
  if (conv.last_message.is_recalled) return t('dm.messageRecalled')
  if (conv.last_message.content) {
    return conv.last_message.content.length > 50
      ? conv.last_message.content.slice(0, 50) + '...'
      : conv.last_message.content
  }
  if (conv.last_message.attachment_name) return t('dm.fileAttachment', { name: conv.last_message.attachment_name })
  return t('dm.attachment')
}

function handleAvatarError(convId: string) {
  avatarFailed[convId] = true
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="px-4 py-3 border-b border-border">
      <h2 class="text-sm font-semibold text-foreground">{{ t('dm.conversations') }}</h2>
    </div>

    <div
      v-if="loading && conversations.length === 0"
      class="px-4 py-8 text-center text-sm text-muted"
    >
      {{ t('common.loading') }}
    </div>

    <div
      v-else-if="conversations.length === 0"
      class="flex flex-col items-center justify-center flex-1 px-4 py-8 text-center"
    >
      <MessageSquare class="w-10 h-10 text-gray-300 mb-3" aria-hidden="true" />
      <p class="text-sm text-muted">{{ t('dm.noConversations') }}</p>
      <p class="text-xs text-muted mt-1">{{ t('dm.noConversationsDesc') }}</p>
    </div>

    <div v-else class="flex-1 overflow-y-auto">
      <button
        v-for="conv in conversations"
        :key="conv.id"
        @click="handleSelect(conv)"
        class="w-full flex items-center gap-3 px-4 py-3.5 sm:py-3 text-left hover:bg-surface-alt active:bg-surface-alt border-b border-border/50 transition touch-manipulation"
        :class="{ 'bg-brand-50/50': activeId === conv.id }"
        :aria-current="activeId === conv.id ? 'true' : undefined"
      >
        <!-- Avatar -->
        <div
          class="shrink-0 w-11 h-11 sm:w-10 sm:h-10 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden"
        >
          <img
            v-if="conv.other_user.avatar_url && !avatarFailed[conv.id]"
            :src="conv.other_user.avatar_url"
            class="w-full h-full rounded-full object-cover"
            :alt="`${conv.other_user.display_name}'s avatar`"
            @error="handleAvatarError(conv.id)"
          />
          <span v-else class="text-sm font-semibold text-muted">
            {{ conv.other_user.display_name.charAt(0).toUpperCase() }}
          </span>
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-foreground truncate">
              {{ conv.other_user.display_name }}
            </span>
            <span class="text-xs text-muted shrink-0 ml-2">
              {{ relativeTime(conv.updated_at) }}
            </span>
          </div>
          <p class="text-xs text-muted truncate mt-0.5">
            {{ getLastMessagePreview(conv) }}
          </p>
        </div>

        <!-- Unread badge -->
        <span
          v-if="conv.unread_count > 0"
          class="shrink-0 flex items-center justify-center min-w-[22px] h-[22px] sm:min-w-[20px] sm:h-5 px-1.5 text-[11px] sm:text-[10px] font-bold text-white bg-danger-500 rounded-full"
          role="status"
          :aria-label="t('dm.unreadMessages', { count: conv.unread_count }, conv.unread_count)"
        >
          {{ conv.unread_count > 99 ? '99+' : conv.unread_count }}
        </span>
      </button>
    </div>
  </div>
</template>
