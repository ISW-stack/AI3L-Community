<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/composables/api'
import { getAboutIntro } from '@/api/about'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { User } from 'lucide-vue-next'

interface Contributor {
  id: number
  display_name: string
  role: string
  avatar_url: string
}

const { t } = useI18n()
const contributors = ref<Contributor[]>([])
const loading = ref(true)
const intro = ref<{ photo_url: string; bio: string }>({ photo_url: '', bio: '' })
const introLoading = ref(true)

function getInitial(name: string): string {
  return name.charAt(0).toUpperCase()
}

const failedAvatars = ref<Set<number>>(new Set())

function handleAvatarError(id: number) {
  failedAvatars.value.add(id)
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

async function fetchIntro() {
  try {
    intro.value = await getAboutIntro()
  } catch {
    intro.value = { photo_url: '', bio: '' }
  } finally {
    introLoading.value = false
  }
}

onMounted(() => {
  fetchContributors()
  fetchIntro()
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <!-- Header Section -->
    <div class="mb-10">
      <h1 class="text-3xl font-bold text-foreground mb-4">{{ t('about.title') }}</h1>
      <p class="text-base text-muted leading-relaxed max-w-2xl">
        {{ t('about.description') }}
      </p>
    </div>

    <!-- Introduction Section (Professor photo + bio) -->
    <div class="mb-10">
      <h2 class="text-2xl font-semibold text-foreground mb-6">{{ t('about.introduction') }}</h2>

      <div v-if="introLoading">
        <SkeletonLoader variant="list" :lines="4" />
      </div>

      <div v-else class="flex flex-col sm:flex-row gap-6 items-start">
        <!-- Photo -->
        <div class="shrink-0 self-center sm:self-start">
          <img
            v-if="intro.photo_url"
            :src="intro.photo_url"
            alt="Professor"
            class="w-48 h-48 rounded-lg object-cover border border-border shadow-sm"
          />
          <div
            v-else
            class="w-48 h-48 rounded-lg bg-surface border border-border flex items-center justify-center"
          >
            <User :size="64" class="text-muted/40" />
          </div>
        </div>

        <!-- Bio -->
        <div
          v-if="intro.bio"
          class="flex-1 text-sm text-foreground leading-relaxed whitespace-pre-line"
        >
          {{ intro.bio }}
        </div>
        <div v-else class="flex-1 text-sm text-muted italic">
          {{ t('about.introEmpty') }}
        </div>
      </div>
    </div>

    <!-- Contributors Section (smaller) -->
    <div>
      <h3 class="text-lg font-semibold text-foreground mb-4">
        {{ t('about.contributors.title') }}
      </h3>

      <div v-if="loading">
        <SkeletonLoader variant="list" :lines="3" />
      </div>

      <div v-else-if="contributors.length === 0" class="text-muted text-sm">
        {{ t('about.contributors.empty') }}
      </div>

      <div v-else class="flex flex-col gap-3">
        <div
          v-for="contributor in contributors"
          :key="contributor.id"
          class="flex items-center gap-3"
        >
          <!-- Avatar -->
          <div class="shrink-0">
            <img
              v-if="!failedAvatars.has(contributor.id)"
              :src="contributor.avatar_url"
              :alt="contributor.display_name"
              class="w-10 h-10 rounded-full object-cover border border-border"
              loading="lazy"
              width="40"
              height="40"
              @error="handleAvatarError(contributor.id)"
            />
            <div
              v-else
              class="w-10 h-10 rounded-full bg-surface border border-border flex items-center justify-center text-sm font-semibold text-muted"
            >
              {{ getInitial(contributor.display_name) }}
            </div>
          </div>
          <!-- Name + Role in one horizontal line, min-w-0 prevents overflow on narrow screens -->
          <div class="min-w-0 flex items-baseline gap-2">
            <span class="text-sm font-medium text-foreground truncate">{{
              contributor.display_name
            }}</span>
            <span class="text-xs text-muted shrink-0">{{ contributor.role }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
