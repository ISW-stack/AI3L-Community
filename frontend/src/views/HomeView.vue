<script setup lang="ts">
import { ref, onMounted } from 'vue'

const apiStatus = ref<string>('checking...')

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/health')
    const data = await res.json()
    apiStatus.value = data.status
  } catch {
    apiStatus.value = 'unavailable (backend not running)'
  }
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center">
    <div class="text-center space-y-6 p-8">
      <h1 class="text-4xl font-bold text-gray-900">AI3L Community</h1>
      <p class="text-lg text-gray-600">Academic Exchange Platform</p>

      <div class="mt-8 p-4 bg-white rounded-lg shadow-sm border border-gray-200">
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Stack Status
        </h2>
        <div class="space-y-1 text-sm text-gray-700">
          <p>Vue 3 + TypeScript + Vite + Tailwind CSS</p>
          <p>
            API:
            <span
              :class="{
                'text-green-600 font-medium': apiStatus === 'healthy',
                'text-red-500': apiStatus !== 'healthy',
              }"
            >
              {{ apiStatus }}
            </span>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
