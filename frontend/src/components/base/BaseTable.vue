<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  columns: Array<{ key: string; label: string; class?: string }>
  rows: Array<Record<string, any>>
  loading?: boolean
  emptyText?: string
}>()
</script>

<template>
  <div class="bg-surface rounded-lg shadow overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm min-w-[600px]">
        <thead class="bg-surface-alt border-b border-border">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="['text-left px-4 py-3 font-medium text-muted', col.class]"
            >
              {{ col.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length" class="px-4 py-8 text-center text-muted">{{ t('common.loading') }}</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="columns.length" class="px-4 py-8 text-center text-muted">
              {{ emptyText || t('common.noData') }}
            </td>
          </tr>
          <template v-else>
            <tr
              v-for="(row, idx) in rows"
              :key="idx"
              class="border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td v-for="col in columns" :key="col.key" class="px-4 py-3">
                <slot :name="col.key" :row="row" :value="row[col.key]">
                  {{ row[col.key] }}
                </slot>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
