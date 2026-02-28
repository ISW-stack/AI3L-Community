<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import { watch } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Image,
    Link.configure({ openOnClick: false }),
  ],
  onUpdate({ editor: e }) {
    emit('update:modelValue', e.getHTML())
  },
})

watch(
  () => props.modelValue,
  (val) => {
    if (editor.value && editor.value.getHTML() !== val) {
      editor.value.commands.setContent(val, false)
    }
  },
)

function setLink() {
  const url = prompt('Enter URL')
  if (!url || !editor.value) return
  editor.value.chain().focus().setLink({ href: url }).run()
}

function addImage() {
  const url = prompt('Enter image URL')
  if (!url || !editor.value) return
  editor.value.chain().focus().setImage({ src: url }).run()
}
</script>

<template>
  <div class="border border-gray-300 rounded-lg overflow-hidden">
    <!-- Toolbar -->
    <div v-if="editor" class="flex flex-wrap gap-1 p-2 border-b border-gray-200 bg-gray-50">
      <button type="button" @click="editor.chain().focus().toggleBold().run()"
        :class="{ 'bg-gray-300': editor.isActive('bold') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200 font-bold">B</button>
      <button type="button" @click="editor.chain().focus().toggleItalic().run()"
        :class="{ 'bg-gray-300': editor.isActive('italic') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200 italic">I</button>

      <span class="w-px bg-gray-300 mx-1"></span>

      <button type="button" @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
        :class="{ 'bg-gray-300': editor.isActive('heading', { level: 1 }) }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">H1</button>
      <button type="button" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
        :class="{ 'bg-gray-300': editor.isActive('heading', { level: 2 }) }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">H2</button>
      <button type="button" @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
        :class="{ 'bg-gray-300': editor.isActive('heading', { level: 3 }) }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">H3</button>

      <span class="w-px bg-gray-300 mx-1"></span>

      <button type="button" @click="editor.chain().focus().toggleBulletList().run()"
        :class="{ 'bg-gray-300': editor.isActive('bulletList') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">UL</button>
      <button type="button" @click="editor.chain().focus().toggleOrderedList().run()"
        :class="{ 'bg-gray-300': editor.isActive('orderedList') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">OL</button>
      <button type="button" @click="editor.chain().focus().toggleBlockquote().run()"
        :class="{ 'bg-gray-300': editor.isActive('blockquote') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">Quote</button>
      <button type="button" @click="editor.chain().focus().toggleCodeBlock().run()"
        :class="{ 'bg-gray-300': editor.isActive('codeBlock') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">Code</button>

      <span class="w-px bg-gray-300 mx-1"></span>

      <button type="button" @click="setLink"
        :class="{ 'bg-gray-300': editor.isActive('link') }"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">Link</button>
      <button type="button" @click="addImage"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200">Image</button>

      <span class="w-px bg-gray-300 mx-1"></span>

      <button type="button" @click="editor.chain().focus().undo().run()"
        :disabled="!editor.can().undo()"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200 disabled:opacity-30">Undo</button>
      <button type="button" @click="editor.chain().focus().redo().run()"
        :disabled="!editor.can().redo()"
        class="px-2 py-1 text-sm rounded hover:bg-gray-200 disabled:opacity-30">Redo</button>
    </div>

    <!-- Editor content -->
    <EditorContent :editor="editor" class="prose prose-sm max-w-none p-3 min-h-[200px] focus:outline-none" />
  </div>
</template>
