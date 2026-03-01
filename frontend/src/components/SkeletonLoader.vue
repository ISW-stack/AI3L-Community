<script setup lang="ts">
defineProps<{
  lines?: number
  variant?: 'card' | 'list' | 'text'
}>()
</script>

<template>
  <div class="animate-pulse space-y-4">
    <!-- Card variant -->
    <template v-if="variant === 'card'">
      <div v-for="i in lines || 3" :key="i" class="bg-surface rounded-lg shadow p-5 space-y-3">
        <div class="h-5 bg-gray-200 rounded w-3/4"></div>
        <div class="h-3 bg-gray-200 rounded w-full"></div>
        <div class="h-3 bg-gray-200 rounded w-2/3"></div>
        <div class="flex justify-between">
          <div class="h-3 bg-gray-200 rounded w-24"></div>
          <div class="h-3 bg-gray-200 rounded w-16"></div>
        </div>
      </div>
    </template>

    <!-- List variant -->
    <template v-else-if="variant === 'list'">
      <div v-for="i in lines || 5" :key="i" class="flex items-center gap-4 p-4">
        <div class="w-10 h-10 bg-gray-200 rounded-full shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-3/4"></div>
          <div class="h-3 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    </template>

    <!-- Text variant (default) -->
    <template v-else>
      <div
        v-for="i in lines || 4"
        :key="i"
        class="h-4 bg-gray-200 rounded"
        :class="i === (lines || 4) ? 'w-2/3' : 'w-full'"
      ></div>
    </template>
  </div>
</template>
