<script setup lang="ts">
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import { ZoomIn, ZoomOut, RotateCw, Move } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    file: File | null
    aspectRatio?: number
    outputWidth?: number
    outputHeight?: number
    outputType?: string
    outputQuality?: number
  }>(),
  {
    aspectRatio: 1,
    outputWidth: 600,
    outputHeight: 600,
    outputType: 'image/jpeg',
    outputQuality: 0.9,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [file: File]
}>()

const { t } = useI18n()
const imageRef = ref<HTMLImageElement | null>(null)
let cropper: Cropper | null = null
let objectUrl = ''

function cleanup() {
  if (cropper) {
    cropper.destroy()
    cropper = null
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open && props.file) {
      await nextTick()
      if (!imageRef.value) return
      objectUrl = URL.createObjectURL(props.file)
      imageRef.value.src = objectUrl
      await nextTick()
      cropper = new Cropper(imageRef.value, {
        aspectRatio: props.aspectRatio,
        viewMode: 1,
        dragMode: 'move',
        autoCropArea: 0.9,
        responsive: true,
        background: true,
        guides: true,
        center: true,
        cropBoxResizable: true,
        cropBoxMovable: true,
      })
    } else {
      cleanup()
    }
  },
)

onBeforeUnmount(cleanup)

function handleZoomIn() {
  cropper?.zoom(0.1)
}

function handleZoomOut() {
  cropper?.zoom(-0.1)
}

function handleRotate() {
  cropper?.rotate(90)
}

function handleReset() {
  cropper?.reset()
}

function handleConfirm() {
  if (!cropper) return
  const canvas = cropper.getCroppedCanvas({
    width: props.outputWidth,
    height: props.outputHeight,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: 'high',
  })
  canvas.toBlob(
    (blob) => {
      if (!blob) return
      const ext = props.outputType === 'image/png' ? 'png' : 'jpg'
      const croppedFile = new File([blob], `cropped.${ext}`, { type: props.outputType })
      emit('confirm', croppedFile)
      emit('update:modelValue', false)
    },
    props.outputType,
    props.outputQuality,
  )
}

function handleCancel() {
  emit('update:modelValue', false)
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="t('imageCropper.title')" size="lg" persistent @update:model-value="emit('update:modelValue', $event)">
    <div class="space-y-4">
      <!-- Cropper area -->
      <div class="relative w-full h-80 bg-black/5 rounded-lg overflow-hidden">
        <img ref="imageRef" alt="" class="block max-w-full" />
      </div>

      <!-- Controls -->
      <div class="flex items-center justify-center gap-2">
        <button
          type="button"
          class="p-2 rounded-lg border border-border bg-surface hover:bg-surface-alt transition"
          :title="t('imageCropper.zoomIn')"
          @click="handleZoomIn"
        >
          <ZoomIn :size="18" />
        </button>
        <button
          type="button"
          class="p-2 rounded-lg border border-border bg-surface hover:bg-surface-alt transition"
          :title="t('imageCropper.zoomOut')"
          @click="handleZoomOut"
        >
          <ZoomOut :size="18" />
        </button>
        <button
          type="button"
          class="p-2 rounded-lg border border-border bg-surface hover:bg-surface-alt transition"
          :title="t('imageCropper.rotate')"
          @click="handleRotate"
        >
          <RotateCw :size="18" />
        </button>
        <button
          type="button"
          class="p-2 rounded-lg border border-border bg-surface hover:bg-surface-alt transition"
          :title="t('imageCropper.reset')"
          @click="handleReset"
        >
          <Move :size="18" />
        </button>
      </div>

      <p class="text-xs text-muted text-center">
        {{ t('imageCropper.hint') }}
      </p>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="handleCancel">
        {{ t('common.cancel') }}
      </BaseButton>
      <BaseButton @click="handleConfirm">
        {{ t('imageCropper.confirm') }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<style>
/* Scope cropperjs styles within this component's modal */
.cropper-container {
  max-height: 320px;
}
</style>
