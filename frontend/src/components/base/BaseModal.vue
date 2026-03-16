<script lang="ts">
let openModalCount = 0

/** Exposed for testing — reset the shared counter between tests. */
export function _resetModalCount() {
  openModalCount = 0
}
</script>

<script setup lang="ts">
import { computed, watch, onUnmounted, ref, nextTick } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    size?: 'sm' | 'md' | 'lg' | 'xl'
    persistent?: boolean
  }>(),
  {
    size: 'md',
    persistent: false,
  },
)

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

const modalRef = ref<HTMLElement | null>(null)
let previouslyFocused: HTMLElement | null = null

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function trapFocus(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    close()
    return
  }
  if (e.key !== 'Tab' || !modalRef.value) return

  const focusable = Array.from(modalRef.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (focusable.length === 0) return

  const first = focusable[0]
  const last = focusable[focusable.length - 1]

  if (e.shiftKey) {
    if (document.activeElement === first) {
      e.preventDefault()
      last.focus()
    }
  } else {
    if (document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement
      document.addEventListener('keydown', trapFocus)
      openModalCount++
      if (openModalCount === 1) {
        document.body.style.overflow = 'hidden'
      }
      await nextTick()
      if (modalRef.value) {
        const first = modalRef.value.querySelector<HTMLElement>(FOCUSABLE)
        ;(first ?? modalRef.value).focus()
      }
    } else {
      document.removeEventListener('keydown', trapFocus)
      openModalCount--
      if (openModalCount <= 0) {
        openModalCount = 0
        document.body.style.overflow = ''
      }
      previouslyFocused?.focus()
      previouslyFocused = null
    }
  },
)

onUnmounted(() => {
  document.removeEventListener('keydown', trapFocus)
  if (props.modelValue) {
    openModalCount--
    if (openModalCount <= 0) {
      openModalCount = 0
      document.body.style.overflow = ''
    }
  }
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
        :aria-label="title ? undefined : 'Dialog'"
        @click.self="close"
      >
        <div
          ref="modalRef"
          :class="[
            'bg-surface rounded-lg shadow-xl p-4 sm:p-6 w-full max-w-[calc(100vw-2rem)]',
            sizeClass,
          ]"
          tabindex="-1"
        >
          <div v-if="title || !persistent" class="flex items-center justify-between mb-4">
            <h3 v-if="title" id="modal-title" class="text-lg font-semibold text-foreground">
              {{ title }}
            </h3>
            <button
              v-if="!persistent"
              class="p-1 -m-1 text-muted hover:text-foreground text-xl leading-none transition ml-auto"
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
