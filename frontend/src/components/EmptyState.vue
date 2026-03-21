<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import { Inbox } from 'lucide-vue-next'

defineProps<{
  message: string
  title?: string
  actionLabel?: string
  actionTo?: string
}>()
</script>

<template>
  <div class="w-full text-center py-12">
    <Inbox class="mx-auto h-12 w-12 text-gray-300 mb-4" aria-hidden="true" />
    <h3 v-if="title" class="text-sm font-medium text-foreground mb-1">{{ title }}</h3>
    <p class="text-sm text-muted">{{ message }}</p>
    <router-link v-if="actionLabel && actionTo" :to="actionTo" class="mt-4 inline-block">
      <BaseButton>{{ actionLabel }}</BaseButton>
    </router-link>
  </div>
</template>
