<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'
import ToastNotification from '@/components/ToastNotification.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    <main>
      <RouterView />
    </main>
    <ToastNotification />
  </div>
</template>
