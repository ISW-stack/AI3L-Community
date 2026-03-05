<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'

interface Contributor {
  id: number
  display_name: string
  role: string
  avatar_url: string
}

const contributors = ref<Contributor[]>([])
const loading = ref(true)

function getInitial(name: string): string {
  return name.charAt(0).toUpperCase()
}

function handleAvatarError(event: Event) {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
  const parent = img.parentElement
  if (parent) {
    const fallback = parent.querySelector('.avatar-fallback') as HTMLElement | null
    if (fallback) {
      fallback.style.display = 'flex'
    }
  }
}

async function fetchContributors() {
  try {
    const response = await api.get('/about/contributors')
    contributors.value = response.data.contributors
  } catch {
    contributors.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchContributors()
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <!-- Header Section -->
    <div class="mb-10">
      <h1 class="text-3xl font-bold text-foreground mb-4">About AI3L Community</h1>
      <p class="text-base text-muted leading-relaxed max-w-2xl">
        AI3L Community is a small academic exchange platform for AI in Language Learning and
        Literacy. It is organized and convened by
        <strong class="text-foreground">Professor Yu-Ju Lan (藍玉如)</strong>
        from the National Taiwan Normal University (NTNU). This community-driven project aims to
        bring together researchers and practitioners who share an interest in exploring how AI can
        support language education and literacy development.
      </p>
    </div>

    <!-- Contributors Section -->
    <div>
      <h2 class="text-2xl font-semibold text-foreground mb-6">Contributors</h2>

      <div v-if="loading" class="text-muted">Loading contributors...</div>

      <div v-else-if="contributors.length === 0" class="text-muted">
        No contributor information available.
      </div>

      <div v-else class="flex flex-wrap gap-8">
        <div
          v-for="contributor in contributors"
          :key="contributor.id"
          class="flex flex-col items-center text-center w-28"
        >
          <div class="relative w-16 h-16 mb-2">
            <img
              :src="contributor.avatar_url"
              :alt="contributor.display_name"
              class="w-16 h-16 rounded-full object-cover border border-border"
              @error="handleAvatarError"
            />
            <div
              class="avatar-fallback w-16 h-16 rounded-full bg-surface border border-border items-center justify-center text-xl font-semibold text-muted absolute inset-0"
              style="display: none"
            >
              {{ getInitial(contributor.display_name) }}
            </div>
          </div>
          <span class="text-sm font-medium text-foreground leading-tight">{{
            contributor.display_name
          }}</span>
          <span class="text-xs text-muted leading-tight mt-0.5">{{ contributor.role }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
