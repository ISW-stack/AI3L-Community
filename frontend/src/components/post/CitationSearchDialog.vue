<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { searchForCitation } from '@/api/citations'
import { getErrorMessage } from '@/utils/error'
import BaseModal from '@/components/base/BaseModal.vue'
import { Search } from 'lucide-vue-next'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  insert: [citation: { postId: string; title: string }]
}>()

interface SearchResult {
  id: string
  title: string
  author_name: string
}

const query = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)
const error = ref('')

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let isMounted = true

onBeforeUnmount(() => {
  isMounted = false
  if (debounceTimer) clearTimeout(debounceTimer)
})

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (!query.value.trim()) {
    results.value = []
    return
  }
  loading.value = true
  error.value = ''
  debounceTimer = setTimeout(async () => {
    if (!isMounted) return
    try {
      const res = await searchForCitation(query.value.trim())
      if (!isMounted) return
      results.value = res as SearchResult[]
    } catch (e: unknown) {
      if (!isMounted) return
      error.value = getErrorMessage(e, 'Search failed.')
      results.value = []
    } finally {
      if (isMounted) loading.value = false
    }
  }, 300)
}

function selectCitation(result: SearchResult) {
  emit('insert', { postId: result.id, title: result.title })
  emit('update:modelValue', false)
  query.value = ''
  results.value = []
}

function closeDialog() {
  emit('update:modelValue', false)
}

// Reset state when dialog closes
watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      query.value = ''
      results.value = []
      error.value = ''
    }
  },
)
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="t('citations.insertTitle')"
    size="lg"
    @update:model-value="closeDialog"
  >
    <div class="space-y-4">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
        <input
          v-model="query"
          type="text"
          name="citation-search"
          :placeholder="t('citations.searchPlaceholder')"
          class="w-full pl-9 pr-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
          @input="onSearchInput"
        />
      </div>

      <div v-if="loading" class="text-sm text-muted text-center py-4">
        {{ t('citations.searching') }}
      </div>

      <div v-if="error" class="text-sm text-danger-600 text-center py-2">{{ error }}</div>

      <div
        v-if="results.length > 0"
        class="divide-y divide-border max-h-60 overflow-y-auto rounded-lg border border-border"
      >
        <button
          v-for="result in results"
          :key="result.id"
          type="button"
          class="w-full text-left px-4 py-3 hover:bg-surface-alt transition"
          @click="selectCitation(result)"
        >
          <p class="text-sm font-medium text-foreground line-clamp-1">{{ result.title }}</p>
          <p class="text-xs text-muted mt-0.5">{{ result.author_name }}</p>
        </button>
      </div>

      <div
        v-if="query.trim() && !loading && results.length === 0 && !error"
        class="text-sm text-muted text-center py-4"
      >
        {{ t('citations.noResults') }}
      </div>
    </div>
  </BaseModal>
</template>
