<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listSigs } from '@/api/sigs'
import type { Sig } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'

const { t } = useI18n()
const auth = useAuthStore()

const sigs = ref<Sig[]>([])
const total = ref(0)
const loading = ref(false)
const searchQuery = ref('')

const filteredSigs = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return sigs.value
  return sigs.value.filter(
    (sig) =>
      sig.name.toLowerCase().includes(q) ||
      (sig.description && sig.description.toLowerCase().includes(q)),
  )
})

async function fetchSigs() {
  loading.value = true
  try {
    const data = await listSigs()
    sigs.value = data.sigs
    total.value = data.total
  } catch {
    /* silent */
  } finally {
    loading.value = false
  }
}

onMounted(fetchSigs)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('sigs.directory.title') }}</h1>
      <router-link v-if="auth.isAdmin" to="/sigs/create">
        <BaseButton>{{ t('sigs.directory.createBtn') }}</BaseButton>
      </router-link>
    </div>

    <div class="mb-4">
      <BaseInput v-model="searchQuery" :placeholder="t('sigs.directory.searchPlaceholder')" />
    </div>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />
    <EmptyState
      v-else-if="filteredSigs.length === 0"
      :message="t('sigs.directory.emptyMessage')"
      :title="t('sigs.directory.emptyTitle')"
    />

    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <router-link v-for="sig in filteredSigs" :key="sig.id" :to="`/sigs/${sig.id}`" class="block">
        <BaseCard hoverable class="h-full">
          <h2 class="text-lg font-semibold text-foreground mb-1">{{ sig.name }}</h2>
          <p v-if="sig.description" class="text-sm text-muted mb-3 line-clamp-2">
            {{ sig.description }}
          </p>
          <div class="flex items-center justify-between text-xs text-muted">
            <span>{{ sig.member_count }} {{ t('sigs.directory.memberCount') }}</span>
            <span>{{ new Date(sig.created_at).toLocaleDateString() }}</span>
          </div>
        </BaseCard>
      </router-link>
    </div>

    <p class="mt-4 text-xs text-muted">{{ total }} {{ t('sigs.directory.totalCount') }}</p>
  </div>
</template>
