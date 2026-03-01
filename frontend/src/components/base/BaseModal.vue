<script setup lang="ts">
import { computed, watch, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  persistent?: boolean
}>(), {
  size: 'md',
  persistent: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const sizeClass = computed(() => {
  const map: Record<string, string> = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl max-h-[80vh] overflow-y-auto',
  }
  return map[props.size]
})

function close() {
  if (!props.persistent) {
    emit('update:modelValue', false)
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

watch(() => props.modelValue, (open) => {
  if (open) {
    document.addEventListener('keydown', onKeydown)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title ? 'modal-title' : undefined"
        @click.self="close"
      >
        <div :class="['bg-surface rounded-lg shadow-xl p-6 w-full', sizeClass]">
          <div v-if="title || !persistent" class="flex items-center justify-between mb-4">
            <h3 v-if="title" id="modal-title" class="text-lg font-semibold text-foreground">{{ title }}</h3>
            <button
              v-if="!persistent"
              class="text-muted hover:text-foreground text-xl leading-none transition ml-auto"
              aria-label="Close"
              @click="close"
            >
              &times;
            </button>
          </div>
          <slot />
          <div v-if="$slots.footer" class="mt-4 flex items-center justify-end gap-3">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
