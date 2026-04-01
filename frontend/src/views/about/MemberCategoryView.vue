<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getCategoryMembers } from '@/api/about'
import type { ClassifiedMember } from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { getErrorMessage } from '@/utils/error'
import { ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const members = ref<ClassifiedMember[]>([])
const categoryLabel = ref('')
const loading = ref(true)
const error = ref('')
const failedAvatars = ref<Set<string>>(new Set())

const CATEGORY_LABELS: Record<string, string> = {
  chair: 'Chair',
  co_chair: 'Co-Chair(s)',
  ec_member: 'EC Members',
  sig_chair: 'SIG Chairs',
  sre: 'Site Reliability Engineer',
  member: 'Members',
}

function handleAvatarError(userId: string) {
  failedAvatars.value.add(userId)
}

function navigateToProfile(userId: string) {
  router.push(`/users/${userId}`)
}

async function fetchMembers() {
  const category = route.params.category as string
  categoryLabel.value = CATEGORY_LABELS[category] || category
  loading.value = true
  error.value = ''
  failedAvatars.value.clear()
  try {
    const data = await getCategoryMembers(category)
    members.value = data.members
    categoryLabel.value = data.label
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    loading.value = false
  }
}

watch(() => route.params.category, fetchMembers)
onMounted(fetchMembers)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <!-- Back link -->
    <button
      class="flex items-center gap-1 text-sm text-muted hover:text-foreground transition mb-6"
      @click="router.push('/about/members')"
    >
      <ArrowLeft :size="16" />
      {{ t('members.title') }}
    </button>

    <h1 class="text-2xl sm:text-3xl font-bold text-foreground mb-2">{{ categoryLabel }}</h1>

    <div v-if="error" class="text-danger-600 mb-4">{{ error }}</div>

    <div v-if="loading">
      <SkeletonLoader variant="list" :lines="6" />
    </div>

    <template v-else>
      <p class="text-muted text-sm mb-8">
        {{ t('about.membersSection.categorySubtitle', { count: members.length }) }}
      </p>

      <div v-if="members.length === 0" class="text-muted text-center py-12">
        {{ t('about.membersSection.categoryEmpty') }}
      </div>

      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-6">
        <button
          v-for="member in members"
          :key="member.user_id"
          class="flex flex-col items-center text-center group cursor-pointer"
          @click="navigateToProfile(member.user_id)"
        >
          <div class="mb-2">
            <img
              v-if="member.avatar_url && !failedAvatars.has(member.user_id)"
              :src="member.avatar_url"
              :alt="member.display_name"
              class="w-20 h-20 rounded-full object-cover border-2 border-border group-hover:border-brand-400 transition"
              loading="lazy"
              width="80"
              height="80"
              @error="handleAvatarError(member.user_id)"
            />
            <div
              v-else
              class="w-20 h-20 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-2xl font-semibold border-2 border-border group-hover:border-brand-400 transition"
            >
              {{ member.display_name.charAt(0).toUpperCase() }}
            </div>
          </div>
          <span
            class="text-sm font-medium text-foreground group-hover:text-brand-600 transition truncate w-full"
          >
            {{ member.display_name }}
          </span>
        </button>
      </div>
    </template>
  </div>
</template>
