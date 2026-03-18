<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Paperclip, Send, X } from 'lucide-vue-next'

const props = defineProps<{
  disabled?: boolean
  editMode?: boolean
  editContent?: string
}>()

const emit = defineEmits<{
  send: [content: string, file?: File]
  'cancel-edit': []
}>()

const MAX_CHARS = 5000
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB

const content = ref(props.editContent ?? '')

watch(
  () => props.editContent,
  (val) => {
    if (val !== undefined) content.value = val
  },
)

const file = ref<File | null>(null)
const fileError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const textarea = ref<HTMLTextAreaElement | null>(null)
const isOverflowing = ref(false)

function checkOverflow() {
  if (textarea.value) {
    isOverflowing.value = textarea.value.scrollHeight > textarea.value.clientHeight
  }
}

const charsRemaining = computed(() => MAX_CHARS - content.value.length)
const canSend = computed(
  () => (content.value.trim().length > 0 || file.value != null) && charsRemaining.value >= 0,
)

function handleSend() {
  if (!canSend.value || props.disabled) return
  emit('send', content.value.trim(), file.value ?? undefined)
  content.value = ''
  file.value = null
  fileError.value = null
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function handleCancelEdit() {
  emit('cancel-edit')
}

function triggerFileSelect() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const selected = target.files?.[0]
  if (!selected) return
  if (selected.size > MAX_FILE_SIZE) {
    fileError.value = 'File too large (max 50 MB)'
    target.value = ''
    return
  }
  file.value = selected
  fileError.value = null
  target.value = ''
}

function removeFile() {
  file.value = null
  fileError.value = null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="border-t border-border bg-surface px-4 py-3">
    <!-- Edit mode banner -->
    <div
      v-if="editMode"
      class="flex items-center justify-between mb-2 px-3 py-1.5 bg-brand-50 rounded-md text-sm"
    >
      <span class="text-brand-700 font-medium">Editing message</span>
      <button
        @click="handleCancelEdit"
        class="text-muted hover:text-foreground transition"
        aria-label="Cancel edit"
      >
        <X class="w-4 h-4" aria-hidden="true" />
      </button>
    </div>

    <!-- File preview -->
    <div
      v-if="file"
      class="flex items-center gap-2 mb-2 px-3 py-2 bg-surface-alt rounded-md text-sm"
    >
      <Paperclip class="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
      <span class="truncate text-foreground">{{ file.name }}</span>
      <span class="text-xs text-muted shrink-0">({{ formatFileSize(file.size) }})</span>
      <button
        @click="removeFile"
        class="ml-auto text-muted hover:text-danger-600 transition shrink-0"
        aria-label="Remove file"
      >
        <X class="w-4 h-4" aria-hidden="true" />
      </button>
    </div>

    <!-- File error -->
    <p v-if="fileError" class="text-xs text-danger-600 mb-2">{{ fileError }}</p>

    <!-- Input row -->
    <div class="flex items-end gap-2">
      <!-- Attach button -->
      <button
        v-if="!editMode"
        @click="triggerFileSelect"
        class="p-2 text-muted hover:text-foreground transition rounded-md hover:bg-surface-alt shrink-0"
        :disabled="disabled"
        aria-label="Attach file"
      >
        <Paperclip class="w-5 h-5" aria-hidden="true" />
      </button>
      <input
        ref="fileInput"
        type="file"
        class="hidden"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip"
        @change="handleFileChange"
      />

      <!-- Textarea -->
      <div class="flex-1 relative">
        <textarea
          ref="textarea"
          v-model="content"
          @keydown="handleKeydown"
          @input="checkOverflow"
          :placeholder="editMode ? 'Edit your message...' : 'Type a message...'"
          :disabled="disabled"
          :maxlength="MAX_CHARS"
          rows="1"
          class="w-full resize-none rounded-lg border border-border bg-surface-alt px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition disabled:opacity-50 overflow-y-auto"
          style="max-height: 120px; min-height: 38px; field-sizing: content"
        ></textarea>
        <div
          v-if="isOverflowing"
          class="absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-surface-alt to-transparent pointer-events-none rounded-b-lg"
        ></div>
        <span
          v-if="charsRemaining < 500"
          class="absolute bottom-1 right-2 text-[10px]"
          :class="charsRemaining < 0 ? 'text-danger-600' : 'text-muted'"
          aria-live="polite"
          :aria-label="`${charsRemaining} characters remaining`"
        >
          {{ charsRemaining }}
        </span>
      </div>

      <!-- Send button -->
      <button
        @click="handleSend"
        :disabled="!canSend || disabled"
        class="p-2 rounded-lg transition shrink-0"
        :class="
          canSend && !disabled
            ? 'bg-brand-600 text-white hover:bg-brand-700'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        "
        aria-label="Send message"
      >
        <Send class="w-5 h-5" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>
