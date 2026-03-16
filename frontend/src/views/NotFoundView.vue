<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import { FileQuestion } from 'lucide-vue-next'
import { useLocale } from '@/composables/useLocale'

const { t } = useLocale()
</script>

<template>
  <div class="min-h-[60vh] flex items-center justify-center">
    <div class="text-center">
      <FileQuestion class="mx-auto h-16 w-16 text-gray-300 mb-4" aria-hidden="true" />
      <h1 class="text-6xl font-bold text-gray-300 mb-4">{{ t('notFoundPage.code') }}</h1>
      <p class="text-xl text-muted mb-8">{{ t('notFoundPage.message') }}</p>
      <router-link to="/">
        <BaseButton size="lg">{{ t('notFoundPage.backToHome') }}</BaseButton>
      </router-link>
    </div>
  </div>
</template>
