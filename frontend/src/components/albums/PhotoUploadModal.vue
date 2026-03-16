<script setup lang="ts">
import { ref, computed } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  upload: [file: File]
}>()

const selectedFile = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const error = ref('')

const ACCEPTED_TYPES = 'image/jpeg,image/png,image/gif,image/webp,application/zip'

const fileInfo = computed(() => {
  if (!selectedFile.value) return null
  const size = selectedFile.value.size
  let sizeStr: string
  if (size < 1024) sizeStr = `${size} B`
  else if (size < 1024 * 1024) sizeStr = `${(size / 1024).toFixed(1)} KB`
  else sizeStr = `${(size / (1024 * 1024)).toFixed(1)} MB`
  return {
    name: selectedFile.value.name,
    size: sizeStr,
    type: selectedFile.value.type,
  }
})

function handleFileChange(event: Event) {
  error.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }

  selectedFile.value = file

  if (file.type.startsWith('image/')) {
    previewUrl.value = URL.createObjectURL(file)
  }
}

function handleUpload() {
  if (!selectedFile.value) {
    error.value = 'Please select a file first.'
    return
  }
  emit('upload', selectedFile.value)
  resetState()
  emit('update:modelValue', false)
}

function handleClose() {
  resetState()
  emit('update:modelValue', false)
}

function resetState() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  selectedFile.value = null
  previewUrl.value = null
  error.value = ''
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    title="Upload Photo"
    size="md"
    @update:model-value="handleClose"
  >
    <div class="space-y-4">
      <BaseAlert v-if="error" type="error">{{ error }}</BaseAlert>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">Select file</label>
        <input
          type="file"
          :accept="ACCEPTED_TYPES"
          class="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
          @change="handleFileChange"
        />
        <p class="text-xs text-muted mt-1">Accepted: JPEG, PNG, GIF, WebP, or ZIP archive</p>
      </div>

      <div v-if="previewUrl" class="rounded-lg overflow-hidden border border-border">
        <img
          :src="previewUrl"
          alt="Preview"
          class="w-full max-h-48 object-contain bg-surface-alt"
        />
      </div>

      <div v-if="fileInfo" class="text-sm text-muted">
        <p><span class="font-medium text-foreground">File:</span> {{ fileInfo.name }}</p>
        <p><span class="font-medium text-foreground">Size:</span> {{ fileInfo.size }}</p>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="handleClose">Cancel</BaseButton>
      <BaseButton :disabled="!selectedFile" @click="handleUpload">Upload</BaseButton>
    </template>
  </BaseModal>
</template>
