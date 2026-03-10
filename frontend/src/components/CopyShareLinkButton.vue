<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Check } from 'lucide-vue-next'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'

const { t } = useI18n()

defineProps<{
  url: string
  label?: string
}>()

const toastStore = useToastStore()
const copied = ref(false)

async function copyLink(url: string) {
  try {
    await navigator.clipboard.writeText(url)
    copied.value = true
    toastStore.show(t('share.copySuccess'), 'success')
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    toastStore.show(t('share.copyError'), 'error')
  }
}
</script>

<template>
  <BaseButton variant="secondary" size="sm" @click="copyLink(url)">
    <component :is="copied ? Check : Copy" class="w-4 h-4 mr-1" />
    {{ copied ? t('share.copied') : label || t('share.copyLink') }}
  </BaseButton>
</template>
