<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Sig } from '@/types'
import { getSig } from '@/api/sigs'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const props = defineProps<{ sigId: string }>()

const sig = ref<Sig | null>(null)
const loading = ref(true)
const errorState = ref(false)

onMounted(async () => {
  try {
    sig.value = await getSig(props.sigId)
  } catch {
    errorState.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <SkeletonLoader v-if="loading" :lines="2" variant="card" />
  <p v-else-if="errorState" class="text-xs text-muted italic">[SIG not found]</p>
  <router-link v-else-if="sig" :to="`/sigs/${sig.id}`" class="block no-underline">
    <BaseCard class="border-l-4 border-brand-500 hover:shadow-md transition">
      <div class="flex items-start gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <BaseBadge variant="brand">SIG</BaseBadge>
            <span class="font-semibold text-foreground text-sm">{{ sig.name }}</span>
          </div>
          <p v-if="sig.description" class="text-xs text-muted line-clamp-2 mb-1">
            {{ sig.description }}
          </p>
          <div class="flex items-center gap-3 text-xs text-muted">
            <span>{{ sig.member_count }} member(s)</span>
            <span>Created by {{ sig.creator_display_name || 'Unknown' }}</span>
          </div>
        </div>
      </div>
    </BaseCard>
  </router-link>
</template>
