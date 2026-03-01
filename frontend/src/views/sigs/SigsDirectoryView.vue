<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listSigs } from '@/api/sigs'
import type { Sig } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'

const sigs = ref<Sig[]>([])
const total = ref(0)
const loading = ref(false)

async function fetchSigs() {
  loading.value = true
  try { const data = await listSigs(); sigs.value = data.sigs; total.value = data.total } catch { /* silent */ } finally { loading.value = false }
}

onMounted(fetchSigs)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Special Interest Groups</h1>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />
    <EmptyState v-else-if="sigs.length === 0" message="No SIGs have been created yet." title="No SIGs" />

    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <router-link v-for="sig in sigs" :key="sig.id" :to="`/sigs/${sig.id}`" class="block">
        <BaseCard hoverable class="h-full">
          <h2 class="text-lg font-semibold text-foreground mb-1">{{ sig.name }}</h2>
          <p v-if="sig.description" class="text-sm text-muted mb-3 line-clamp-2">{{ sig.description }}</p>
          <div class="flex items-center justify-between text-xs text-muted">
            <span>{{ sig.member_count }} member(s)</span>
            <span>{{ new Date(sig.created_at).toLocaleDateString() }}</span>
          </div>
        </BaseCard>
      </router-link>
    </div>

    <p class="mt-4 text-xs text-muted">{{ total }} SIG(s) total</p>
  </div>
</template>
