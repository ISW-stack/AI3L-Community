<script setup lang="ts">
import { ref, computed } from 'vue'
import { useLocale } from '@/composables/useLocale'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

const { t } = useLocale()

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  upload: [file: File]
  uploadZip: [file: File]
}>()

const selectedFile = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const error = ref('')

const ACCEPTED_TYPES =
  'image/jpeg,image/png,image/gif,image/webp,application/zip,application/x-zip-compressed'
const ZIP_TYPES = new Set(['application/zip', 'application/x-zip-compressed'])
const MAX_IMAGE_SIZE = 10 * 1024 * 1024 // 10 MB (single image)
const MAX_ZIP_SIZE = 50 * 1024 * 1024 // 50 MB (zip archive)

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

  const isZip = ZIP_TYPES.has(file.type) || file.name.toLowerCase().endsWith('.zip')
  const maxSize = isZip ? MAX_ZIP_SIZE : MAX_IMAGE_SIZE
  const maxLabel = isZip ? '50 MB' : '10 MB'
  if (file.size > maxSize) {
    error.value = `File too large (max ${maxLabel}). Selected: ${(file.size / (1024 * 1024)).toFixed(1)} MB`
    // M-11: Clear file input so user can re-select
    input.value = ''
    return
  }

  selectedFile.value = file

  if (file.type.startsWith('image/')) {
    previewUrl.value = URL.createObjectURL(file)
  }
}

const isZipFile = computed(() => {
  if (!selectedFile.value) return false
  return (
    ZIP_TYPES.has(selectedFile.value.type) || selectedFile.value.name.toLowerCase().endsWith('.zip')
  )
})

function handleUpload() {
  if (!selectedFile.value) {
    error.value = t('albums.selectFileFirst')
    return
  }
  if (isZipFile.value) {
    emit('uploadZip', selectedFile.value)
  } else {
    emit('upload', selectedFile.value)
  }
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
    :title="t('albums.uploadPhotoTitle')"
    size="md"
    @update:model-value="handleClose"
  >
    <div class="space-y-4">
      <BaseAlert v-if="error" type="error">{{ error }}</BaseAlert>

      <div>
        <label for="photo-upload" class="block text-sm font-medium text-foreground mb-1">{{
          t('albums.selectFile')
        }}</label>
        <input
          id="photo-upload"
          type="file"
          name="photo-upload"
          :accept="ACCEPTED_TYPES"
          class="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
          @change="handleFileChange"
        />
        <p class="text-xs text-muted mt-1">{{ t('albums.acceptedFormats') }}</p>
      </div>

      <div v-if="previewUrl" class="rounded-lg overflow-hidden border border-border">
        <img
          :src="previewUrl"
          alt="Preview"
          class="w-full max-h-48 object-contain bg-surface-alt"
        />
      </div>

      <BaseAlert v-if="isZipFile" type="info">
        {{ t('albums.zipUploadHint') }}
      </BaseAlert>

      <div v-if="fileInfo" class="text-sm text-muted">
        <p>
          <span class="font-medium text-foreground">{{ t('albums.fileLabel') }}</span>
          {{ fileInfo.name }}
        </p>
        <p>
          <span class="font-medium text-foreground">{{ t('albums.sizeLabel') }}</span>
          {{ fileInfo.size }}
        </p>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="handleClose">{{ t('common.cancel') }}</BaseButton>
      <BaseButton :disabled="!selectedFile" @click="handleUpload">{{
        t('albums.upload')
      }}</BaseButton>
    </template>
  </BaseModal>
</template>
