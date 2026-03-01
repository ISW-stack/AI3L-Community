<script setup lang="ts">
defineProps<{
  message: string
  title?: string
  actionLabel?: string
  actionTo?: string
}>()
</script>

<template>
  <div class="text-center py-12">
    <svg
      class="mx-auto h-12 w-12 text-gray-300 mb-4"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      stroke-width="1.5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
      />
    </svg>
    <h3 v-if="title" class="text-sm font-medium text-gray-900 mb-1">{{ title }}</h3>
    <p class="text-sm text-gray-400">{{ message }}</p>
    <router-link
      v-if="actionLabel && actionTo"
      :to="actionTo"
      class="mt-4 inline-block bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition"
    >
      {{ actionLabel }}
    </router-link>
  </div>
</template>
