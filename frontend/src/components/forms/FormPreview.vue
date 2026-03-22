<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import type { Question } from '@/types'
import BaseAlert from '@/components/base/BaseAlert.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()

defineProps<{
  title: string
  description: string
  bannerUrl: string
  questions: Question[]
  previewMode: 'desktop' | 'mobile'
}>()

const emit = defineEmits<{
  'set-desktop': []
  'set-mobile': []
}>()
</script>

<template>
  <div class="space-y-4">
    <!-- Preview mode toggle -->
    <div class="flex items-center justify-center gap-2 mb-2">
      <button
        class="px-3 py-1 text-sm rounded-l-lg border transition"
        :class="
          previewMode === 'desktop'
            ? 'bg-brand-600 text-white border-brand-600'
            : 'bg-surface text-muted border-border hover:text-foreground'
        "
        @click="emit('set-desktop')"
      >
        {{ t('forms.builder.previewDesktop') }}
      </button>
      <button
        class="px-3 py-1 text-sm rounded-r-lg border transition"
        :class="
          previewMode === 'mobile'
            ? 'bg-brand-600 text-white border-brand-600'
            : 'bg-surface text-muted border-border hover:text-foreground'
        "
        @click="emit('set-mobile')"
      >
        {{ t('forms.builder.previewMobile') }}
      </button>
    </div>

    <BaseAlert type="info" class="text-center">
      {{ t('forms.builder.previewMode') }}
    </BaseAlert>

    <!-- Phone frame for mobile preview -->
    <div
      :class="
        previewMode === 'mobile'
          ? 'mx-auto border-2 border-gray-400 rounded-4xl p-3 bg-gray-50 max-w-full sm:max-w-[375px]'
          : ''
      "
    >
      <div :class="previewMode === 'mobile' ? 'rounded-xl overflow-hidden bg-surface' : ''">
        <div class="space-y-4" :class="previewMode === 'mobile' ? 'p-3' : ''">
          <div v-if="bannerUrl" class="rounded-lg overflow-hidden">
            <img
              :src="bannerUrl"
              alt="Banner"
              loading="lazy"
              class="w-full h-32 object-cover"
              width="768"
              height="128"
            />
          </div>
          <div
            v-if="description"
            class="prose prose-sm max-w-none text-muted"
            v-html="DOMPurify.sanitize(description)"
          ></div>

          <div
            v-for="(q, i) in questions"
            :key="q.id"
            class="bg-surface-alt rounded-lg p-4 border border-border"
          >
            <p class="text-sm font-medium text-foreground mb-2">
              {{ i + 1 }}. {{ q.label || t('forms.builder.untitledQuestion') }}
              <span v-if="q.required" class="text-danger-500">*</span>
            </p>

            <!-- Text -->
            <input
              v-if="q.type === 'text'"
              type="text"
              disabled
              :name="`preview-${q.id}`"
              :placeholder="q.placeholder || t('forms.builder.shortTextPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
            />

            <!-- Textarea -->
            <textarea
              v-else-if="q.type === 'textarea'"
              disabled
              :name="`preview-${q.id}`"
              :placeholder="q.placeholder || t('forms.builder.longTextPlaceholder')"
              :rows="3"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
            />

            <!-- Single choice -->
            <div v-else-if="q.type === 'single_choice'" class="space-y-2">
              <label
                v-for="opt in q.options"
                :key="opt.id"
                class="flex items-center gap-2 text-sm text-foreground"
              >
                <input
                  type="radio"
                  disabled
                  :name="`preview-radio-${q.id}`"
                  class="text-brand-600"
                />
                {{ opt.label || 'Option' }}
              </label>
            </div>

            <!-- Multiple choice -->
            <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
              <label
                v-for="opt in q.options"
                :key="opt.id"
                class="flex items-center gap-2 text-sm text-foreground"
              >
                <input type="checkbox" disabled :name="`preview-check-${q.id}`" class="rounded" />
                {{ opt.label || 'Option' }}
              </label>
            </div>

            <!-- Dropdown -->
            <select
              v-else-if="q.type === 'dropdown'"
              disabled
              :name="`preview-${q.id}`"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
            >
              <option value="">{{ t('forms.builder.selectPlaceholder') }}</option>
              <option v-for="opt in q.options" :key="opt.id">{{ opt.label }}</option>
            </select>

            <!-- Rating -->
            <div v-else-if="q.type === 'rating'" class="flex gap-2">
              <button
                v-for="n in (q.max ?? 5) - (q.min ?? 1) + 1"
                :key="n"
                disabled
                class="w-8 h-8 rounded bg-surface border border-border text-sm text-muted"
              >
                {{ (q.min ?? 1) + n - 1 }}
              </button>
            </div>

            <!-- File upload -->
            <div v-else-if="q.type === 'file_upload'" class="text-sm text-muted opacity-60">
              <input type="file" disabled :name="`preview-file-${q.id}`" />
            </div>
          </div>

          <EmptyState
            v-if="questions.length === 0"
            :message="t('forms.builder.noQuestionsAdded')"
          />
        </div>
      </div>
    </div>
  </div>
</template>
