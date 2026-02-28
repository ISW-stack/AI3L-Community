<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'

interface Sig {
  id: string
  name: string
  description: string | null
  created_by: string
  creator_display_name: string | null
  member_count: number
  created_at: string
}

const sigs = ref<Sig[]>([])
const total = ref(0)
const loading = ref(false)

async function fetchSigs() {
  loading.value = true
  try {
    const { data } = await api.get('/sigs')
    sigs.value = data.sigs
    total.value = data.total
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

onMounted(fetchSigs)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Special Interest Groups</h1>

    <div v-if="loading" class="text-center text-gray-400 py-12">Loading...</div>

    <div v-else-if="sigs.length === 0" class="text-center text-gray-400 py-12">
      No SIGs have been created yet.
    </div>

    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <router-link
        v-for="sig in sigs"
        :key="sig.id"
        :to="`/sigs/${sig.id}`"
        class="block bg-white rounded-xl shadow hover:shadow-md transition p-5"
      >
        <h2 class="text-lg font-semibold text-gray-900 mb-1">{{ sig.name }}</h2>
        <p v-if="sig.description" class="text-sm text-gray-500 mb-3 line-clamp-2">
          {{ sig.description }}
        </p>
        <div class="flex items-center justify-between text-xs text-gray-400">
          <span>{{ sig.member_count }} member(s)</span>
          <span>{{ new Date(sig.created_at).toLocaleDateString() }}</span>
        </div>
      </router-link>
    </div>

    <p class="mt-4 text-xs text-gray-400">{{ total }} SIG(s) total</p>
  </div>
</template>
