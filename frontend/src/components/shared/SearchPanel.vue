<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const props = defineProps<{
  keyword: string
  dateFrom: string
  dateTo: string
  logic: string
  showAdvanced: boolean
  isSearchLoading: boolean
  isSearching: boolean
  dateRangeInvalid: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:keyword': [value: string]
  'update:dateFrom': [value: string]
  'update:dateTo': [value: string]
  'update:logic': [value: string]
  'search-input': []
  'immediate-search': []
  'toggle-advanced': []
  'clear-search': []
}>()

const { t } = useI18n()

function handleInput(event: Event) {
  emit('update:keyword', (event.target as HTMLInputElement).value)
  emit('search-input')
}
</script>

<template>
  <BaseCard class="mb-6 space-y-3">
    <div class="flex flex-col sm:flex-row gap-3">
      <div class="relative flex-1">
        <input
          :value="props.keyword"
          type="text"
          name="search-keyword"
          :placeholder="props.placeholder ?? t('common.searchPlaceholder')"
          class="w-full px-3 py-2 pr-9 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
          @input="handleInput"
          @keyup.enter="emit('immediate-search')"
        />
        <svg
          v-if="props.isSearchLoading"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 animate-spin h-4 w-4 text-brand-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          role="status"
          :aria-label="t('common.searching')"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          ></path>
        </svg>
      </div>
      <BaseButton @click="emit('immediate-search')">{{ t('common.search') }}</BaseButton>
      <button
        class="text-sm text-brand-600 hover:text-brand-700 hover:underline shrink-0"
        @click="emit('toggle-advanced')"
      >
        {{ props.showAdvanced ? t('common.hideAdvanced') : t('common.advanced') }}
      </button>
    </div>

    <!-- Advanced Search (collapsible) -->
    <div v-if="props.showAdvanced" class="space-y-3 border-t border-border pt-3">
      <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <input
          :value="props.dateFrom"
          type="date"
          name="date-from"
          class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
          @input="emit('update:dateFrom', ($event.target as HTMLInputElement).value)"
        />
        <span class="text-muted text-sm hidden sm:inline">{{ t('common.to') }}</span>
        <input
          :value="props.dateTo"
          type="date"
          name="date-to"
          class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
          @input="emit('update:dateTo', ($event.target as HTMLInputElement).value)"
        />
        <select
          :value="props.logic"
          name="search-logic"
          class="px-3 py-2 border border-border rounded-lg text-sm w-20 focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
          @change="emit('update:logic', ($event.target as HTMLSelectElement).value)"
        >
          <option value="AND">{{ t('common.searchLogic.and') }}</option>
          <option value="OR">{{ t('common.searchLogic.or') }}</option>
        </select>
      </div>
      <p v-if="props.dateRangeInvalid" class="text-sm text-danger-600">
        {{ t('common.dateRangeError') }}
      </p>
      <div class="flex gap-2">
        <BaseButton :disabled="props.dateRangeInvalid" @click="emit('immediate-search')">
          {{ t('common.applyFilters') }}
        </BaseButton>
        <BaseButton v-if="props.isSearching" variant="secondary" @click="emit('clear-search')">
          {{ t('common.clearFilters') }}
        </BaseButton>
      </div>
    </div>
  </BaseCard>
</template>
