<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import { ref, watch } from 'vue'
import { uploadEditorFile } from '@/api/files'
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
} from 'lucide-vue-next'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = useEditor({
  content: props.modelValue,
  extensions: [StarterKit, Image, Link.configure({ openOnClick: false })],
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

function setLink() {
  const url = prompt('Enter URL')
  if (!url || !editor.value) return
  editor.value.chain().focus().setLink({ href: url }).run()
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

    <!-- Editor content -->
    <EditorContent
      :editor="editor"
      class="prose prose-sm max-w-none p-3 min-h-[200px] focus:outline-none"
    />
  </div>
</template>
