<script setup lang="ts">
import { ref, watch, nextTick, reactive, computed } from 'vue'
import type { DMMessage } from '@/types/dm'
import { relativeTime } from '@/utils/datetime'
import { useLocale } from '@/composables/useLocale'

const { currentLocale: locale } = useLocale()
import {
  MoreHorizontal,
  Pencil,
  Trash2,
  Check,
  CheckCheck,
  AlertTriangle,
  MessageSquare,
  ArrowDown,
  File,
  FileText,
  Film,
  Music,
} from 'lucide-vue-next'

const props = defineProps<{
  messages: DMMessage[]
  currentUserId: string
  loading: boolean
  hasMore: boolean
}>()

const emit = defineEmits<{
  'load-more': []
  edit: [messageId: string, currentContent: string]
  recall: [messageId: string]
}>()

const scrollContainer = ref<HTMLElement | null>(null)
const openMenuId = ref<string | null>(null)
const avatarFailed = reactive<Record<string, boolean>>({})
const isAtBottom = ref(true)
const showNewMessageHint = ref(false)

function handleScroll() {
  if (!scrollContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value
  isAtBottom.value = scrollTop + clientHeight >= scrollHeight - 50
  if (isAtBottom.value) {
    showNewMessageHint.value = false
  }
}

// Smart auto-scroll: only scroll when user is near bottom
watch(
  () => props.messages.length,
  async (newLen, oldLen) => {
    if (newLen > (oldLen ?? 0)) {
      await nextTick()
      if (isAtBottom.value) {
        scrollToBottom()
      } else {
        showNewMessageHint.value = true
      }
    }
  },
)

function scrollToBottom() {
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

function scrollToNewMessages() {
  scrollToBottom()
  showNewMessageHint.value = false
}

function isMine(msg: DMMessage): boolean {
  return msg.sender.id === props.currentUserId
}

function canEditOrRecall(msg: DMMessage): boolean {
  if (!isMine(msg) || msg.is_recalled) return false
  const hoursSince = (Date.now() - new Date(msg.created_at).getTime()) / (1000 * 60 * 60)
  return hoursSince < 12
}

function toggleMenu(messageId: string) {
  openMenuId.value = openMenuId.value === messageId ? null : messageId
}

function handleEdit(msg: DMMessage) {
  openMenuId.value = null
  if (msg.content) {
    emit('edit', msg.id, msg.content)
  }
}

function handleRecall(msg: DMMessage) {
  openMenuId.value = null
  emit('recall', msg.id)
}

function handleLoadMore() {
  emit('load-more')
}

function handleAvatarError(senderId: string) {
  avatarFailed[senderId] = true
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function isFileExpiringSoon(expiresAt: string | null): boolean {
  if (!expiresAt) return false
  const hoursLeft = (new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60)
  return hoursLeft > 0 && hoursLeft < 24
}

function isFileExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return false
  return new Date(expiresAt).getTime() < Date.now()
}

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp'])
const VIDEO_EXTS = new Set(['mp4', 'webm', 'mov', 'avi'])
const AUDIO_EXTS = new Set(['mp3', 'wav', 'ogg', 'flac'])

function getFileExt(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? ''
}

function isImage(name: string): boolean {
  return IMAGE_EXTS.has(getFileExt(name))
}

function getFileIcon(name: string) {
  const ext = getFileExt(name)
  if (VIDEO_EXTS.has(ext)) return Film
  if (AUDIO_EXTS.has(ext)) return Music
  if (ext === 'pdf') return FileText
  return File
}

function getDateLabel(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const msgDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diff = today.getTime() - msgDay.getTime()
  if (diff === 0) return 'Today'
  if (diff === 86400000) return 'Yesterday'
  return date.toLocaleDateString(locale.value, { month: 'short', day: 'numeric', year: 'numeric' })
}

const messagesWithDateSeparators = computed(() => {
  const result: { type: 'date' | 'message'; key: string; label?: string; message?: DMMessage }[] =
    []
  let lastDate = ''
  for (const msg of props.messages) {
    const dateKey = new Date(msg.created_at).toDateString()
    if (dateKey !== lastDate) {
      lastDate = dateKey
      result.push({ type: 'date', key: 'date-' + dateKey, label: getDateLabel(msg.created_at) })
    }
    result.push({ type: 'message', key: msg.id, message: msg })
  }
  return result
})
</script>

<template>
  <div ref="scrollContainer" @scroll="handleScroll" class="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative">
    <!-- Load more -->
    <div v-if="hasMore" class="text-center pb-3">
      <button
        @click="handleLoadMore"
        class="text-xs text-brand-600 hover:text-brand-700 transition px-3 py-1.5 rounded-md hover:bg-surface-alt"
        :disabled="loading"
      >
        {{ loading ? 'Loading...' : 'Load older messages' }}
      </button>
    </div>

    <!-- Loading spinner -->
    <div v-if="loading && messages.length === 0" class="flex items-center justify-center py-12">
      <div class="flex items-center gap-2 text-sm text-muted">
        <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        Loading messages...
      </div>
    </div>

    <!-- Empty conversation -->
    <div v-else-if="!loading && messages.length === 0" class="flex flex-col items-center justify-center flex-1 py-12 text-center">
      <MessageSquare class="w-10 h-10 text-gray-300 mb-3" aria-hidden="true" />
      <p class="text-sm text-muted">No messages yet</p>
      <p class="text-xs text-muted mt-1">Send the first message to start the conversation.</p>
    </div>

    <template v-else>
      <div v-for="item in messagesWithDateSeparators" :key="item.key">
        <!-- Date separator -->
        <div v-if="item.type === 'date'" class="flex items-center gap-3 py-3" role="separator" :aria-label="item.label">
          <div class="flex-1 border-t border-border"></div>
          <span class="text-xs text-muted font-medium">{{ item.label }}</span>
          <div class="flex-1 border-t border-border"></div>
        </div>

        <!-- Message bubble -->
        <div
          v-else-if="item.message"
          class="flex gap-2 mb-2"
          :class="isMine(item.message) ? 'justify-end' : 'justify-start'"
        >
          <!-- Other user avatar (left side) -->
          <div
            v-if="!isMine(item.message)"
            class="shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden self-end"
          >
            <img
              v-if="item.message.sender.avatar_url && !avatarFailed[item.message.sender.id]"
              :src="item.message.sender.avatar_url"
              class="w-8 h-8 rounded-full object-cover"
              :alt="`${item.message.sender.display_name}'s avatar`"
              @error="handleAvatarError(item.message.sender.id)"
            />
            <span v-else class="text-xs font-semibold text-muted">
              {{ item.message.sender.display_name.charAt(0).toUpperCase() }}
            </span>
          </div>

          <!-- Bubble -->
          <div class="max-w-[70%] relative group">
            <!-- Recalled message -->
            <div
              v-if="item.message.is_recalled"
              class="px-3 py-2 rounded-xl text-sm italic text-muted bg-surface-alt border border-border"
            >
              Message recalled
            </div>

            <!-- Normal message -->
            <div
              v-else
              class="px-3 py-2 rounded-xl text-sm"
              :class="
                isMine(item.message)
                  ? 'bg-brand-600 text-white rounded-br-sm'
                  : 'bg-surface-alt text-foreground border border-border rounded-bl-sm'
              "
            >
              <p v-if="item.message.content" class="whitespace-pre-wrap break-words">
                {{ item.message.content }}
              </p>

              <!-- File attachment -->
              <div v-if="item.message.attachment_name" class="mt-1.5">
                <template v-if="isFileExpired(item.message.attachment_expires_at)">
                  <div class="flex items-center gap-2 text-xs" :class="isMine(item.message) ? 'text-white/80' : 'text-muted'">
                    <AlertTriangle class="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                    <span class="italic">File expired</span>
                  </div>
                </template>
                <template v-else>
                  <!-- Image preview -->
                  <a
                    v-if="isImage(item.message.attachment_name)"
                    :href="item.message.attachment_url ?? '#'"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="block mt-1"
                  >
                    <img
                      :src="item.message.attachment_url ?? ''"
                      :alt="item.message.attachment_name"
                      class="max-h-48 max-w-full rounded-lg object-cover"
                      loading="lazy"
                    />
                  </a>
                  <!-- Non-image file -->
                  <div v-else class="flex items-center gap-2 text-xs" :class="isMine(item.message) ? 'text-white/80' : 'text-muted'">
                    <a
                      :href="item.message.attachment_url ?? '#'"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="flex items-center gap-1.5 hover:underline"
                      :class="isMine(item.message) ? 'text-white/90' : 'text-brand-600'"
                    >
                      <component :is="getFileIcon(item.message.attachment_name)" class="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                      <span class="truncate max-w-[180px]">{{ item.message.attachment_name }}</span>
                      <span v-if="item.message.attachment_size" class="shrink-0">
                        ({{ formatFileSize(item.message.attachment_size) }})
                      </span>
                    </a>
                  </div>
                  <!-- Expiry warning -->
                  <div
                    v-if="isFileExpiringSoon(item.message.attachment_expires_at)"
                    class="flex items-center gap-1 mt-1 text-xs text-amber-500"
                  >
                    <AlertTriangle class="w-3 h-3" aria-hidden="true" />
                    Expires soon
                  </div>
                </template>
              </div>
            </div>

            <!-- Meta line: time, edited, read receipt -->
            <div
              class="flex items-center gap-1.5 mt-0.5 text-[10px] text-muted"
              :class="isMine(item.message) ? 'justify-end' : 'justify-start'"
            >
              <span>{{
                new Date(item.message.created_at).toLocaleTimeString(locale, {
                  hour: '2-digit',
                  minute: '2-digit',
                })
              }}</span>
              <span v-if="item.message.is_edited && !item.message.is_recalled" class="italic">
                (edited)
              </span>
              <!-- Sent but not read (single check) -->
              <Check
                v-if="isMine(item.message) && !item.message.read_at && !item.message.is_recalled"
                class="w-3.5 h-3.5 text-muted"
                aria-label="Sent"
              />
              <!-- Read (double check with tooltip) -->
              <span
                v-if="isMine(item.message) && item.message.read_at && !item.message.is_recalled"
                :title="'Read ' + new Date(item.message.read_at).toLocaleString(locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })"
              >
                <CheckCheck
                  class="w-3.5 h-3.5 text-brand-500"
                  aria-label="Read"
                />
              </span>
            </div>

            <!-- Action menu for own messages -->
            <div
              v-if="canEditOrRecall(item.message)"
              class="absolute top-0 opacity-0 group-hover:opacity-100 transition-opacity"
              :class="isMine(item.message) ? '-left-8' : '-right-8'"
            >
              <button
                @click="toggleMenu(item.message!.id)"
                class="p-1 rounded-full hover:bg-surface-alt text-muted hover:text-foreground transition"
                aria-label="Message actions"
              >
                <MoreHorizontal class="w-4 h-4" aria-hidden="true" />
              </button>

              <!-- Dropdown -->
              <div
                v-if="openMenuId === item.message!.id"
                class="absolute z-10 bg-surface border border-border rounded-lg shadow-lg py-1 w-36"
                :class="isMine(item.message!) ? 'left-0' : 'right-0'"
              >
                <button
                  v-if="item.message!.content"
                  @click="handleEdit(item.message!)"
                  class="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-foreground hover:bg-surface-alt transition"
                >
                  <Pencil class="w-3.5 h-3.5" aria-hidden="true" />
                  Edit
                </button>
                <button
                  @click="handleRecall(item.message!)"
                  class="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-danger-600 hover:bg-surface-alt transition"
                >
                  <Trash2 class="w-3.5 h-3.5" aria-hidden="true" />
                  Recall
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- New message hint -->
    <button
      v-if="showNewMessageHint"
      @click="scrollToNewMessages"
      class="sticky bottom-2 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-brand-600 rounded-full shadow-lg hover:bg-brand-700 transition"
    >
      <ArrowDown class="w-3.5 h-3.5" aria-hidden="true" />
      New message
    </button>
  </div>
</template>
