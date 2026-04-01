<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import api from '@/composables/api'
import { getAboutIntro, getClassifiedMembers } from '@/api/about'
import type { AboutIntroData } from '@/api/about'
import type { MemberCategory } from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { User, ChevronRight, Users } from 'lucide-vue-next'

interface Contributor {
  id: number
  display_name: string
  role: string
  avatar_url: string
}

const { t } = useI18n()
const router = useRouter()
const contributors = ref<Contributor[]>([])
const loading = ref(true)
const intro = ref<AboutIntroData>({
  photo_url: '',
  bio: '',
  chair_photo_url: '',
  chair_bio: '',
})
const introLoading = ref(true)
const memberCategories = ref<MemberCategory[]>([])
const membersLoading = ref(true)

function getInitial(name: string): string {
  return name.charAt(0).toUpperCase()
}

const failedAvatars = ref<Set<number>>(new Set())

function handleAvatarError(id: number) {
  failedAvatars.value.add(id)
}

function navigateToCategory(key: string) {
  router.push(`/about/members/${key}`)
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
    intro.value = { photo_url: '', bio: '', chair_photo_url: '', chair_bio: '' }
  } finally {
    introLoading.value = false
  }
}

async function fetchClassifiedMembers() {
  try {
    const data = await getClassifiedMembers()
    memberCategories.value = data.categories
  } catch {
    memberCategories.value = []
  } finally {
    membersLoading.value = false
  }
}

onMounted(() => {
  fetchContributors()
  fetchIntro()
  fetchClassifiedMembers()
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <!-- Header Section -->
    <div class="mb-10">
      <h1 class="text-2xl sm:text-3xl font-bold text-foreground mb-4">{{ t('about.title') }}</h1>
      <p class="text-base text-muted leading-relaxed max-w-2xl">
        {{ t('about.description') }}
      </p>
    </div>

    <!-- Introduction Section -->
    <div class="mb-10">
      <h2 class="text-2xl font-semibold text-foreground mb-6">{{ t('about.introduction') }}</h2>

      <div v-if="introLoading">
        <SkeletonLoader variant="list" :lines="4" />
      </div>

      <div v-else class="space-y-8">
        <!-- Chair -->
        <div>
          <h3 class="text-lg font-semibold text-foreground mb-4">{{ t('about.chair') }}</h3>
          <div class="flex flex-col sm:flex-row gap-6 items-start">
            <div class="shrink-0 self-center sm:self-start">
              <img
                v-if="intro.chair_photo_url"
                :src="intro.chair_photo_url"
                :alt="t('about.chair')"
                class="w-48 h-48 rounded-lg object-cover border border-border shadow-sm"
              />
              <div
                v-else
                class="w-48 h-48 rounded-lg bg-surface border border-border flex items-center justify-center"
              >
                <User :size="64" class="text-muted/40" />
              </div>
            </div>
            <div
              v-if="intro.chair_bio"
              class="flex-1 text-sm text-foreground leading-relaxed whitespace-pre-line"
            >
              {{ intro.chair_bio }}
            </div>
            <div v-else class="flex-1 text-sm text-muted italic">
              {{ t('about.introEmpty') }}
            </div>
          </div>
        </div>

        <!-- Co-Chair -->
        <div>
          <h3 class="text-lg font-semibold text-foreground mb-4">{{ t('about.coChair') }}</h3>
          <div class="flex flex-col sm:flex-row gap-6 items-start">
            <div class="shrink-0 self-center sm:self-start">
              <img
                v-if="intro.photo_url"
                :src="intro.photo_url"
                :alt="t('about.coChair')"
                class="w-48 h-48 rounded-lg object-cover border border-border shadow-sm"
              />
              <div
                v-else
                class="w-48 h-48 rounded-lg bg-surface border border-border flex items-center justify-center"
              >
                <User :size="64" class="text-muted/40" />
              </div>
            </div>
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
      </div>
    </div>

    <!-- Members Classification Section -->
    <div class="mb-10">
      <h2 class="text-2xl font-semibold text-foreground mb-6 flex items-center gap-2">
        <Users :size="24" class="text-brand-600" />
        {{ t('about.membersSection.title') }}
      </h2>

      <div v-if="membersLoading">
        <SkeletonLoader variant="list" :lines="6" />
      </div>

      <div v-else-if="memberCategories.length === 0" class="text-muted text-sm">
        {{ t('about.membersSection.empty') }}
      </div>

      <div v-else class="space-y-2">
        <button
          v-for="cat in memberCategories"
          :key="cat.key"
          class="w-full flex items-center justify-between px-4 py-3 bg-surface border border-border rounded-lg hover:bg-surface-alt hover:shadow-sm transition cursor-pointer text-left"
          @click="navigateToCategory(cat.key)"
        >
          <div class="flex items-center gap-3">
            <span class="text-sm font-medium text-foreground">{{ cat.label }}</span>
            <span
              class="inline-flex items-center justify-center min-w-[1.5rem] px-1.5 py-0.5 text-xs font-semibold rounded-full bg-brand-100 text-brand-700"
            >
              {{ cat.count }}
            </span>
          </div>
          <ChevronRight :size="16" class="text-muted" />
        </button>
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

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
          <!-- Name + Role stacked vertically for consistent alignment -->
          <div class="min-w-0">
            <div class="text-sm font-medium text-foreground truncate">
              {{ contributor.display_name }}
            </div>
            <div class="text-xs text-muted truncate">{{ contributor.role }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
