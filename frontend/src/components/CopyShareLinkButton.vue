<script setup lang="ts">
import { ref } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'

const props = withDefaults(
  defineProps<{
    url: string
    label?: string
  }>(),
  { label: 'Copy Link' },
)

const toastStore = useToastStore()
const copied = ref(false)

async function copyLink() {
  try {
    await navigator.clipboard.writeText(props.url)
    copied.value = true
    toastStore.show('Link copied to clipboard.', 'success')
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    toastStore.show('Failed to copy link.', 'error')
  }
}
</script>

<template>
  <BaseButton variant="secondary" size="sm" @click="copyLink">
    <component :is="copied ? Check : Copy" class="w-4 h-4 mr-1" />
    {{ copied ? 'Copied!' : label }}
  </BaseButton>
</template>
