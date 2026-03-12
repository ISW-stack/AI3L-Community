<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { uploadEditorFile, getFileScanStatus } from '@/api/files'
import { useToastStore } from '@/stores/toast'
import {
  Bold,
  Italic,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Quote,
  Code,
  Link as LinkIcon,
  ImagePlus,
  Undo2,
  Redo2,
  Table as TableIcon,
  ShieldCheck,
  ShieldAlert,
  Loader2,
} from 'lucide-vue-next'

const { t } = useI18n()

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit.configure({ link: false }),
    Image,
    Link.configure({ openOnClick: false }),
    Table.configure({ resizable: true }),
    TableRow,
    TableCell,
    TableHeader,
  ],
  onUpdate({ editor: e }) {
    emit('update:modelValue', e.getHTML())
  },
})

watch(
  () => props.modelValue,
  (val) => {
    if (editor.value && editor.value.getHTML() !== val) {
      editor.value.commands.setContent(
        val,
        false as unknown as import('@tiptap/core').SetContentOptions,
      )
    }
  },
)

const toastStore = useToastStore()
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const scanStatus = ref<'pending' | 'clean' | 'malicious' | 'unknown' | 'error' | 'skipped' | null>(
  null,
)
const scanKey = ref('')
let scanPollTimer: ReturnType<typeof setTimeout> | null = null
let scanDismissTimer: ReturnType<typeof setTimeout> | null = null

function clearScanTimers() {
  if (scanPollTimer) {
    clearTimeout(scanPollTimer)
    scanPollTimer = null
  }
  if (scanDismissTimer) {
    clearTimeout(scanDismissTimer)
    scanDismissTimer = null
  }
}

async function pollScanStatus() {
  if (!scanKey.value) return
  try {
    const data = await getFileScanStatus(scanKey.value)
    scanStatus.value = data.status

    if (data.status === 'pending') {
      // Still scanning — poll again in 5 seconds
      scanPollTimer = setTimeout(pollScanStatus, 5000)
      return
    }

    // Terminal state reached — stop polling
    if (data.status === 'malicious') {
      toastStore.show(t('editor.maliciousFile'), 'error')
    } else if (data.status === 'clean') {
      // Auto-dismiss clean status after 10 seconds
      scanDismissTimer = setTimeout(() => {
        if (scanStatus.value === 'clean') scanStatus.value = null
      }, 10000)
    } else if (data.status === 'skipped') {
      // Auto-dismiss skipped status after 10 seconds
      scanDismissTimer = setTimeout(() => {
        if (scanStatus.value === 'skipped') scanStatus.value = null
      }, 10000)
    }
    // 'unknown' and 'error' stay visible until next upload
  } catch {
    scanStatus.value = null
  }
}

onUnmounted(() => {
  clearScanTimers()
})

function setLink() {
  const url = prompt(t('editor.promptLinkUrl'))
  if (!url || !editor.value) return
  editor.value.chain().focus().setLink({ href: url }).run()
}

function insertTable() {
  if (!editor.value) return
  editor.value.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
}

function addImage() {
  fileInputRef.value?.click()
}

const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20 MB

async function handleFileUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !editor.value) return

  if (file.size > MAX_FILE_SIZE) {
    toastStore.show(t('editor.fileTooLarge'), 'error')
    if (fileInputRef.value) fileInputRef.value.value = ''
    return
  }

  uploading.value = true
  try {
    const data = await uploadEditorFile(file)
    const isImage = file.type.startsWith('image/')
    if (isImage) {
      editor.value.chain().focus().setImage({ src: data.url }).run()
    } else {
      editor.value
        .chain()
        .focus()
        .insertContent(
          `<a href="${data.url}" target="_blank" rel="noopener noreferrer">${file.name}</a>`,
        )
        .run()
    }
    if (data.scan_task_id && data.key) {
      clearScanTimers()
      scanKey.value = data.key
      scanStatus.value = 'pending'
      scanPollTimer = setTimeout(pollScanStatus, 5000)
    }
  } catch {
    toastStore.show(t('editor.uploadFailed'), 'error')
  } finally {
    uploading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}
</script>

<template>
  <div class="border border-border rounded-lg overflow-hidden">
    <!-- Hidden file input for image/document upload -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp,.pdf,.docx"
      class="hidden"
      @change="handleFileUpload"
    />

    <!-- Toolbar -->
    <div
      v-if="editor"
      class="flex gap-1 p-2 border-b border-border bg-surface-alt overflow-x-auto no-scrollbar"
    >
      <button
        type="button"
        @click="editor.chain().focus().toggleBold().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('bold') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.bold')"
      >
        <Bold class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleItalic().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('italic') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.italic')"
      >
        <Italic class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 1 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.heading1')"
      >
        <Heading1 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 2 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.heading2')"
      >
        <Heading2 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 3 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.heading3')"
      >
        <Heading3 class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().toggleBulletList().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('bulletList') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.bulletList')"
      >
        <List class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleOrderedList().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('orderedList') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.orderedList')"
      >
        <ListOrdered class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleBlockquote().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('blockquote') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.blockquote')"
      >
        <Quote class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleCodeBlock().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('codeBlock') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.codeBlock')"
      >
        <Code class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="setLink"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('link') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.insertLink')"
      >
        <LinkIcon class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="addImage"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :class="{ 'opacity-50 cursor-wait': uploading }"
        :disabled="uploading"
        :aria-label="t('editor.toolbar.insertFile')"
      >
        <ImagePlus class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="insertTable"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :aria-label="t('editor.toolbar.insertTable')"
      >
        <TableIcon class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().undo().run()"
        :disabled="!editor.can().undo()"
        class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition"
        :aria-label="t('editor.toolbar.undo')"
      >
        <Undo2 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().redo().run()"
        :disabled="!editor.can().redo()"
        class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition"
        :aria-label="t('editor.toolbar.redo')"
      >
        <Redo2 class="w-4 h-4" aria-hidden="true" />
      </button>
    </div>

    <!-- Scan status indicator -->
    <div
      v-if="scanStatus"
      class="flex items-center gap-1.5 px-3 py-1.5 text-xs border-b border-border"
      :class="{
        'bg-warning-50 text-warning-700': scanStatus === 'pending',
        'bg-success-50 text-success-700': scanStatus === 'clean' || scanStatus === 'skipped',
        'bg-danger-50 text-danger-700': scanStatus === 'malicious',
        'bg-gray-50 text-muted': scanStatus === 'unknown' || scanStatus === 'error',
      }"
    >
      <Loader2
        v-if="scanStatus === 'pending'"
        class="w-3.5 h-3.5 animate-spin"
        aria-hidden="true"
      />
      <ShieldCheck v-else-if="scanStatus === 'clean'" class="w-3.5 h-3.5" aria-hidden="true" />
      <ShieldCheck v-else-if="scanStatus === 'skipped'" class="w-3.5 h-3.5" aria-hidden="true" />
      <ShieldAlert v-else-if="scanStatus === 'malicious'" class="w-3.5 h-3.5" aria-hidden="true" />
      <ShieldAlert
        v-else-if="scanStatus === 'unknown' || scanStatus === 'error'"
        class="w-3.5 h-3.5"
        aria-hidden="true"
      />
      <span v-if="scanStatus === 'pending'">{{ t('editor.scan.pending') }}</span>
      <span v-else-if="scanStatus === 'clean'">{{ t('editor.scan.clean') }}</span>
      <span v-else-if="scanStatus === 'skipped'">{{ t('editor.scan.skipped') }}</span>
      <span v-else-if="scanStatus === 'malicious'">{{ t('editor.scan.malicious') }}</span>
      <span v-else-if="scanStatus === 'unknown'">{{ t('editor.scan.unknown') }}</span>
      <span v-else-if="scanStatus === 'error'">{{ t('editor.scan.error') }}</span>
    </div>

    <!-- Editor content -->
    <EditorContent
      :editor="editor"
      class="prose prose-sm max-w-none p-3 min-h-[200px] focus:outline-none"
    />
  </div>
</template>
