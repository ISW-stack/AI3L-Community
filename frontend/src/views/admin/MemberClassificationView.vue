<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getClassifiedMembers, assignClassification, removeClassification } from '@/api/about'
import type { MemberCategory, ClassifiedMember } from '@/types/orgchart'
import api from '@/composables/api'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { Search, X, ChevronDown, ChevronUp } from 'lucide-vue-next'

const { t } = useI18n()
const toast = useToastStore()

const categories = ref<MemberCategory[]>([])
const loading = ref(true)
const expandedCategories = ref<Set<string>>(new Set())

// Search state per category
const searchQueries = ref<Record<string, string>>({})
const searchResults = ref<
  Record<string, Array<{ id: string; display_name: string; avatar_url: string | null }>>
>({})
const searching = ref<Record<string, boolean>>({})
const searchTimers: Record<string, ReturnType<typeof setTimeout>> = {}

async function fetchCategories() {
  loading.value = true
  try {
    const data = await getClassifiedMembers()
    categories.value = data.categories
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  } finally {
    loading.value = false
  }
}

function toggleCategory(key: string) {
  if (expandedCategories.value.has(key)) {
    expandedCategories.value.delete(key)
  } else {
    expandedCategories.value.add(key)
  }
}

function onSearchInput(categoryKey: string) {
  if (searchTimers[categoryKey]) clearTimeout(searchTimers[categoryKey])
  const query = (searchQueries.value[categoryKey] || '').trim()
  if (!query) {
    searchResults.value[categoryKey] = []
    return
  }
  searchTimers[categoryKey] = setTimeout(async () => {
    searching.value[categoryKey] = true
    try {
      const res = await api.get('/users/search', { params: { q: query, limit: 8 } })
      searchResults.value[categoryKey] = res.data
    } catch {
      searchResults.value[categoryKey] = []
    } finally {
      searching.value[categoryKey] = false
    }
  }, 300)
}

function isUserAlreadyClassified(userId: string): string | null {
  for (const cat of categories.value) {
    // Skip 'member' — those users are auto-populated (unclassified) and can be freely reassigned
    if (cat.key === 'member') continue
    if (cat.members.some((m) => m.user_id === userId)) {
      return cat.label
    }
  }
  return null
}

async function addMember(categoryKey: string, user: { id: string; display_name: string }) {
  const existingCat = isUserAlreadyClassified(user.id)
  if (existingCat) {
    toast.show(
      t('admin.memberClassification.alreadyClassified', {
        name: user.display_name,
        category: existingCat,
      }),
      'error',
    )
    return
  }

  const cat = categories.value.find((c) => c.key === categoryKey)
  const nextOrder = cat ? cat.members.length : 0

  try {
    await assignClassification(user.id, categoryKey, nextOrder)
    searchQueries.value[categoryKey] = ''
    searchResults.value[categoryKey] = []
    toast.show(t('admin.memberClassification.assigned'), 'success')
    await fetchCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  }
}

async function removeMember(userId: string) {
  try {
    await removeClassification(userId)
    toast.show(t('admin.memberClassification.removed'), 'success')
    await fetchCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  }
}

async function moveUp(categoryKey: string, member: ClassifiedMember, index: number) {
  if (index === 0) return
  try {
    await assignClassification(member.user_id, categoryKey, index - 1)
    // Swap the member above to the current position
    const cat = categories.value.find((c) => c.key === categoryKey)
    if (cat && cat.members[index - 1]) {
      await assignClassification(cat.members[index - 1].user_id, categoryKey, index)
    }
    await fetchCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  }
}

async function moveDown(categoryKey: string, member: ClassifiedMember, index: number) {
  const cat = categories.value.find((c) => c.key === categoryKey)
  if (!cat || index >= cat.members.length - 1) return
  try {
    await assignClassification(member.user_id, categoryKey, index + 1)
    await assignClassification(cat.members[index + 1].user_id, categoryKey, index)
    await fetchCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  }
}

onMounted(fetchCategories)

onUnmounted(() => {
  Object.values(searchTimers).forEach((timer) => clearTimeout(timer))
})
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('admin.memberClassification.title') },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-2">
      {{ t('admin.memberClassification.title') }}
    </h1>
    <p class="text-muted text-sm mb-6">
      {{ t('admin.memberClassification.subtitle') }}
    </p>

    <div v-if="loading">
      <SkeletonLoader variant="list" :lines="8" />
    </div>

    <div v-else class="space-y-4 max-w-3xl">
      <div
        v-for="cat in categories"
        :key="cat.key"
        class="bg-surface border border-border rounded-xl overflow-hidden"
      >
        <!-- Category header -->
        <button
          class="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-surface-alt transition"
          @click="toggleCategory(cat.key)"
        >
          <div class="flex items-center gap-3">
            <span class="text-base font-semibold text-foreground">{{ cat.label }}</span>
            <span
              class="inline-flex items-center justify-center min-w-[1.5rem] px-1.5 py-0.5 text-xs font-semibold rounded-full bg-brand-100 text-brand-700"
            >
              {{ cat.count }}
            </span>
          </div>
          <component
            :is="expandedCategories.has(cat.key) ? ChevronUp : ChevronDown"
            :size="18"
            class="text-muted"
          />
        </button>

        <!-- Expanded content -->
        <div v-if="expandedCategories.has(cat.key)" class="px-5 pb-5 border-t border-border">
          <!-- Search to add -->
          <div class="relative mt-4 mb-4">
            <Search
              class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted"
              aria-hidden="true"
            />
            <input
              v-model="searchQueries[cat.key]"
              type="text"
              :placeholder="t('admin.memberClassification.searchPlaceholder')"
              class="w-full pl-10 pr-4 py-2 text-sm border border-border rounded-lg bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-200"
              @input="onSearchInput(cat.key)"
            />

            <!-- Search results dropdown -->
            <div
              v-if="(searchResults[cat.key] || []).length > 0"
              class="absolute z-10 mt-1 w-full bg-surface border border-border rounded-lg shadow-lg max-h-48 overflow-auto"
            >
              <button
                v-for="user in searchResults[cat.key]"
                :key="user.id"
                class="w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface-alt transition"
                @click="addMember(cat.key, user)"
              >
                <img
                  v-if="user.avatar_url"
                  :src="user.avatar_url"
                  :alt="user.display_name"
                  class="w-8 h-8 rounded-full object-cover border border-border"
                />
                <div
                  v-else
                  class="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold"
                >
                  {{ user.display_name.charAt(0).toUpperCase() }}
                </div>
                <span>{{ user.display_name }}</span>
                <span v-if="isUserAlreadyClassified(user.id)" class="ml-auto text-xs text-muted">
                  ({{ isUserAlreadyClassified(user.id) }})
                </span>
              </button>
            </div>
          </div>

          <!-- Current members list -->
          <div v-if="cat.members.length === 0" class="text-muted text-sm py-2">
            {{ t('admin.memberClassification.noMembers') }}
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="(member, idx) in cat.members"
              :key="member.user_id"
              class="flex items-center gap-3 px-3 py-2 bg-surface-alt rounded-lg"
            >
              <img
                v-if="member.avatar_url"
                :src="member.avatar_url"
                :alt="member.display_name"
                class="w-9 h-9 rounded-full object-cover border border-border"
              />
              <div
                v-else
                class="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-semibold"
              >
                {{ member.display_name.charAt(0).toUpperCase() }}
              </div>

              <span class="text-sm font-medium text-foreground flex-1 truncate">
                {{ member.display_name }}
              </span>

              <!-- Reorder buttons -->
              <button
                :disabled="idx === 0"
                class="p-1 text-muted hover:text-foreground disabled:opacity-30 transition"
                :title="t('common.moveUp')"
                @click.stop="moveUp(cat.key, member, idx)"
              >
                <ChevronUp :size="14" />
              </button>
              <button
                :disabled="idx === cat.members.length - 1"
                class="p-1 text-muted hover:text-foreground disabled:opacity-30 transition"
                :title="t('common.moveDown')"
                @click.stop="moveDown(cat.key, member, idx)"
              >
                <ChevronDown :size="14" />
              </button>

              <!-- Remove button -->
              <button
                class="p-1 text-danger-600 hover:text-danger-700 transition"
                :title="t('common.remove')"
                @click.stop="removeMember(member.user_id)"
              >
                <X :size="14" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
