<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'

interface BreadcrumbItem {
  label: string
  to?: string
}

defineProps<{
  items: BreadcrumbItem[]
}>()
</script>

<template>
  <nav class="mb-4 flex items-center gap-1 text-sm text-muted" aria-label="Breadcrumb">
    <template v-for="(item, index) in items" :key="index">
      <ChevronRight v-if="index > 0" class="w-4 h-4 shrink-0" aria-hidden="true" />
      <router-link
        v-if="item.to && index < items.length - 1"
        :to="item.to"
        class="text-brand-600 hover:underline"
      >
        {{ item.label }}
      </router-link>
      <span
        v-else
        class="text-muted"
        :aria-current="index === items.length - 1 ? 'page' : undefined"
      >{{ item.label }}</span>
    </template>
  </nav>
</template>
