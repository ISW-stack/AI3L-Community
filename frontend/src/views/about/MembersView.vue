<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getClassifiedMembers } from '@/api/about'
import type { MemberCategory } from '@/types/orgchart'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { ChevronRight, Users } from 'lucide-vue-next'

const { t } = useI18n()
const router = useRouter()
const categories = ref<MemberCategory[]>([])
const loading = ref(true)

function navigateToCategory(key: string) {
  router.push(`/about/members/${key}`)
}

async function fetchCategories() {
  try {
    const data = await getClassifiedMembers()
    categories.value = data.categories
  } catch {
    categories.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-2xl sm:text-3xl font-bold text-foreground mb-2 flex items-center gap-2">
      <Users :size="28" class="text-brand-600" />
      {{ t('members.title') }}
    </h1>
    <p class="text-muted text-sm mb-8">{{ t('members.subtitle') }}</p>

    <div v-if="loading">
      <SkeletonLoader variant="list" :lines="6" />
    </div>

    <div v-else-if="categories.length === 0" class="text-muted text-sm text-center py-12">
      {{ t('about.membersSection.empty') }}
    </div>

    <div v-else class="space-y-2">
      <button
        v-for="cat in categories"
        :key="cat.key"
        class="w-full flex items-center justify-between px-5 py-4 bg-surface border border-border rounded-lg hover:bg-surface-alt hover:shadow-sm transition cursor-pointer text-left"
        @click="navigateToCategory(cat.key)"
      >
        <div class="flex items-center gap-3">
          <span class="text-base font-medium text-foreground">{{ cat.label }}</span>
          <span
            class="inline-flex items-center justify-center min-w-[1.75rem] px-2 py-0.5 text-xs font-semibold rounded-full bg-brand-100 text-brand-700"
          >
            {{ cat.count }}
          </span>
        </div>
        <ChevronRight :size="18" class="text-muted" />
      </button>
    </div>
  </div>
</template>
