<script setup lang="ts">
</script>

<template>
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="text-center">
      <h1 class="text-6xl font-bold text-gray-300 mb-4">404</h1>
      <p class="text-xl text-gray-500 mb-8">Page not found</p>
      <router-link
        to="/"
        class="inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm hover:bg-blue-700 transition"
      >
        Back to Home
      </router-link>
    </div>
  </div>
</template>
