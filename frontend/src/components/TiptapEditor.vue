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
import { uploadEditorFile, getTaskStatus } from '@/api/files'
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
} from 'lucide-vue-next'

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
const scanStatus = ref<'idle' | 'scanning' | 'clean' | 'malicious'>('idle')
let scanPollTimer: ReturnType<typeof setTimeout> | null = null

async function pollScanStatus(taskId: string) {
  try {
    const data = await getTaskStatus(taskId)
    if (data.status === 'SUCCESS' && data.result) {
      if (data.result.status === 'malicious') {
        scanStatus.value = 'malicious'
        toastStore.show('Uploaded file was flagged as potentially malicious and removed.', 'error')
      } else {
        scanStatus.value = 'clean'
      }
      return
    }
    if (data.status === 'FAILURE') {
      scanStatus.value = 'idle'
      return
    }
    // Still pending — poll again
    scanPollTimer = setTimeout(() => pollScanStatus(taskId), 5000)
  } catch {
    scanStatus.value = 'idle'
  }
}

onUnmounted(() => {
  if (scanPollTimer) clearTimeout(scanPollTimer)
})

function setLink() {
  const url = prompt('Enter URL')
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

async function handleImageUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !editor.value) return

  uploading.value = true
  try {
    const data = await uploadEditorFile(file)
    editor.value.chain().focus().setImage({ src: data.url }).run()
    if (data.scan_task_id) {
      scanStatus.value = 'scanning'
      pollScanStatus(data.scan_task_id)
    }
  } catch {
    toastStore.show('Failed to upload image.', 'error')
  } finally {
    uploading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}
</script>

<template>
  <div class="border border-border rounded-lg overflow-hidden">
    <!-- Hidden file input for image upload -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp"
      class="hidden"
      @change="handleImageUpload"
    />

    <!-- Toolbar -->
    <div v-if="editor" class="flex flex-wrap gap-1 p-2 border-b border-border bg-surface-alt">
      <button
        type="button"
        @click="editor.chain().focus().toggleBold().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('bold') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Bold"
      >
        <Bold class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleItalic().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('italic') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Italic"
      >
        <Italic class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 1 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Heading 1"
      >
        <Heading1 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 2 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Heading 2"
      >
        <Heading2 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('heading', { level: 3 }) }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Heading 3"
      >
        <Heading3 class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().toggleBulletList().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('bulletList') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Bullet list"
      >
        <List class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleOrderedList().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('orderedList') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Ordered list"
      >
        <ListOrdered class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleBlockquote().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('blockquote') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Blockquote"
      >
        <Quote class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().toggleCodeBlock().run()"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('codeBlock') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Code block"
      >
        <Code class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="setLink"
        :class="{ 'bg-brand-100 text-brand-700': editor.isActive('link') }"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Insert link"
      >
        <LinkIcon class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="addImage"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        :class="{ 'opacity-50 cursor-wait': uploading }"
        :disabled="uploading"
        aria-label="Insert image"
      >
        <ImagePlus class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="insertTable"
        class="p-1.5 rounded hover:bg-gray-200 transition"
        aria-label="Insert table"
      >
        <TableIcon class="w-4 h-4" aria-hidden="true" />
      </button>

      <span class="w-px bg-border mx-1"></span>

      <button
        type="button"
        @click="editor.chain().focus().undo().run()"
        :disabled="!editor.can().undo()"
        class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition"
        aria-label="Undo"
      >
        <Undo2 class="w-4 h-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        @click="editor.chain().focus().redo().run()"
        :disabled="!editor.can().redo()"
        class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition"
        aria-label="Redo"
      >
        <Redo2 class="w-4 h-4" aria-hidden="true" />
      </button>
    </div>

    <!-- Scan status indicator -->
    <div
      v-if="scanStatus !== 'idle'"
      class="px-3 py-1.5 text-xs border-b border-border"
      :class="{
        'bg-warning-50 text-warning-700': scanStatus === 'scanning',
        'bg-success-50 text-success-700': scanStatus === 'clean',
        'bg-danger-50 text-danger-700': scanStatus === 'malicious',
      }"
    >
      <span v-if="scanStatus === 'scanning'">Scanning uploaded file...</span>
      <span v-else-if="scanStatus === 'clean'">File scan complete — no threats detected.</span>
      <span v-else-if="scanStatus === 'malicious'">File flagged as malicious and removed.</span>
    </div>

    <!-- Editor content -->
    <EditorContent
      :editor="editor"
      class="prose prose-sm max-w-none p-3 min-h-[200px] focus:outline-none"
    />
  </div>
</template>
