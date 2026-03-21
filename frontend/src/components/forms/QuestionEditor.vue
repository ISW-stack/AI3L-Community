<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Question } from '@/types'

const QUESTION_TYPES = [
  { value: 'text', key: 'forms.builder.questionType.shortText' },
  { value: 'textarea', key: 'forms.builder.questionType.longText' },
  { value: 'single_choice', key: 'forms.builder.questionType.singleChoice' },
  { value: 'multiple_choice', key: 'forms.builder.questionType.multipleChoice' },
  { value: 'dropdown', key: 'forms.builder.questionType.dropdown' },
  { value: 'rating', key: 'forms.builder.questionType.rating' },
  { value: 'file_upload', key: 'forms.builder.questionType.fileUpload' },
]

function getTypeBadgeText(type: string): string {
  const found = QUESTION_TYPES.find((qt) => qt.value === type)
  return found ? t(found.key) : type
}

const { t } = useI18n()

defineProps<{
  question: Question
  index: number
  totalQuestions: number
  isSchemaLocked: boolean
  isCollapsed: boolean
  dragIndex: number | null
  dropTargetIndex: number | null
}>()

const emit = defineEmits<{
  remove: []
  'move-up': []
  'move-down': []
  duplicate: []
  'toggle-collapse': []
  'add-option': []
  'remove-option': [optionIndex: number]
  'move-option': [optionIndex: number, direction: number]
  'update-allowed-types': [event: Event]
  'insert-at': []
  'drag-start': [event: DragEvent]
  'drag-over': [event: DragEvent]
  'drag-leave': []
  drop: [event: DragEvent]
  'drag-end': []
  'touch-start': [event: TouchEvent]
  'touch-move': [event: TouchEvent]
  'touch-end': [event: TouchEvent]
}>()

function onDragStart(event: DragEvent) {
  emit('drag-start', event)
}
function onDragOver(event: DragEvent) {
  emit('drag-over', event)
}
function onDragLeave() {
  emit('drag-leave')
}
function onDrop(event: DragEvent) {
  emit('drop', event)
}
function onDragEnd() {
  emit('drag-end')
}
function onTouchStart(event: TouchEvent) {
  emit('touch-start', event)
}
function onTouchMove(event: TouchEvent) {
  emit('touch-move', event)
}
function onTouchEnd(event: TouchEvent) {
  emit('touch-end', event)
}
</script>

<template>
  <!-- eslint-disable vue/no-mutating-props -->
  <!-- Insert question divider (between questions) -->
  <div
    v-if="index > 0 && !isSchemaLocked"
    class="group relative flex items-center justify-center py-1"
    @dragover="onDragOver($event)"
    @dragleave="onDragLeave"
    @drop="onDrop($event)"
  >
    <div
      class="w-full border-t border-dashed transition-colors"
      :class="
        dropTargetIndex === index
          ? 'border-brand-500 border-2'
          : 'border-transparent group-hover:border-border'
      "
    ></div>
    <button
      class="absolute opacity-0 group-hover:opacity-100 transition-opacity bg-surface border border-border rounded-full w-6 h-6 flex items-center justify-center text-xs text-muted hover:text-brand-600 hover:border-brand-500 shadow-sm z-10"
      :aria-label="t('forms.builder.insertQuestionHere')"
      @click="emit('insert-at')"
    >
      +
    </button>
  </div>

  <!-- Question card -->
  <div
    :id="`question-card-${index}`"
    :draggable="!isSchemaLocked"
    class="bg-surface rounded-lg shadow p-5 border-l-4 transition-all duration-200"
    :class="[
      isSchemaLocked ? 'border-gray-300 opacity-75' : 'border-brand-500',
      dragIndex === index ? 'opacity-50 scale-95' : '',
    ]"
    @dragstart="onDragStart($event)"
    @dragover="onDragOver($event)"
    @dragleave="onDragLeave"
    @drop="onDrop($event)"
    @dragend="onDragEnd"
  >
    <!-- Question header row -->
    <div class="flex items-center justify-between mb-1 gap-1 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <!-- Drag handle -->
        <span
          v-if="!isSchemaLocked"
          class="cursor-grab active:cursor-grabbing text-muted hover:text-foreground select-none text-lg leading-none shrink-0"
          :aria-label="t('forms.builder.dragHandle')"
          @touchstart="onTouchStart($event)"
          @touchmove="onTouchMove($event)"
          @touchend="onTouchEnd($event)"
          >&#x2261;</span
        >
        <!-- Collapse toggle -->
        <button
          class="text-muted hover:text-foreground transition text-sm px-1 shrink-0"
          :aria-label="
            isCollapsed ? t('forms.builder.expandQuestion') : t('forms.builder.collapseQuestion')
          "
          @click="emit('toggle-collapse')"
        >
          <span v-if="isCollapsed">&#x25B6;</span>
          <span v-else>&#x25BC;</span>
        </button>
        <span class="text-sm font-medium text-muted shrink-0">
          {{ t('forms.builder.questionLabel') }} {{ index + 1 }}
        </span>
        <!-- Collapsed: show type badge + label + required -->
        <template v-if="isCollapsed">
          <span class="text-xs bg-brand-50 text-brand-700 px-1.5 py-0.5 rounded shrink-0">
            {{ getTypeBadgeText(question.type) }}
          </span>
          <span class="text-sm text-foreground truncate">
            {{ question.label || t('forms.builder.untitledQuestion') }}
          </span>
          <span v-if="question.required" class="text-danger-500 text-xs shrink-0">*</span>
        </template>
      </div>
      <div v-if="!isSchemaLocked" class="flex items-center gap-1 shrink-0">
        <button
          @click="emit('move-up')"
          :disabled="index === 0"
          :aria-label="t('accessibility.moveQuestionUp')"
          class="text-muted hover:text-foreground disabled:opacity-30 px-1"
        >
          &uarr;
        </button>
        <button
          @click="emit('move-down')"
          :disabled="index === totalQuestions - 1"
          :aria-label="t('accessibility.moveQuestionDown')"
          class="text-muted hover:text-foreground disabled:opacity-30 px-1"
        >
          &darr;
        </button>
        <!-- Duplicate button -->
        <button
          @click="emit('duplicate')"
          :aria-label="t('forms.builder.duplicateQuestion')"
          class="text-muted hover:text-brand-600 px-1"
          :title="t('forms.builder.duplicateQuestion')"
        >
          &#x2398;
        </button>
        <button
          @click="emit('remove')"
          :aria-label="t('accessibility.deleteQuestion')"
          class="text-danger-500 hover:text-danger-600 px-1 ml-2"
        >
          &times;
        </button>
      </div>
    </div>

    <!-- Expanded content -->
    <div v-if="!isCollapsed" class="mt-2">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div>
          <label class="block text-xs text-muted mb-1">{{ t('forms.builder.typeLabel') }}</label>
          <select
            v-model="question.type"
            :disabled="isSchemaLocked"
            class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option v-for="qt in QUESTION_TYPES" :key="qt.value" :value="qt.value">
              {{ t(qt.key) }}
            </option>
          </select>
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs text-muted mb-1">{{
            t('forms.builder.labelRequired')
          }}</label>
          <input
            v-model="question.label"
            :disabled="isSchemaLocked"
            type="text"
            name="question-label"
            :placeholder="t('forms.builder.labelPlaceholder')"
            class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      <label class="flex items-center gap-2 text-sm text-foreground mb-3">
        <input
          type="checkbox"
          v-model="question.required"
          :disabled="isSchemaLocked"
          class="rounded"
        />
        {{ t('forms.builder.requiredCheckbox') }}
      </label>

      <div v-if="question.type === 'text' || question.type === 'textarea'" class="space-y-2">
        <input
          v-model="question.placeholder"
          :disabled="isSchemaLocked"
          type="text"
          name="question-placeholder"
          :placeholder="t('forms.builder.placeholderLabel')"
          class="w-full border border-border rounded-lg px-2 py-1.5 text-sm"
        />
        <div class="flex items-center gap-2">
          <label class="text-xs text-muted">{{ t('forms.builder.maxLengthLabel') }}</label>
          <input
            v-model.number="question.max_length"
            :disabled="isSchemaLocked"
            type="number"
            name="max-length"
            min="1"
            :placeholder="t('forms.builder.maxLengthPlaceholder')"
            class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      <div
        v-if="['single_choice', 'multiple_choice', 'dropdown'].includes(question.type)"
        class="space-y-2"
      >
        <div
          v-for="(opt, oi) in question.options"
          :key="opt.id"
          class="flex items-center gap-2 min-w-0"
        >
          <!-- Option reorder arrows -->
          <div v-if="!isSchemaLocked" class="flex flex-col">
            <button
              :disabled="oi === 0"
              :aria-label="t('forms.builder.moveOptionUp')"
              class="text-xs text-muted hover:text-foreground disabled:opacity-30 leading-none"
              @click="emit('move-option', oi, -1)"
            >
              &#x25B2;
            </button>
            <button
              :disabled="oi === (question.options?.length ?? 0) - 1"
              :aria-label="t('forms.builder.moveOptionDown')"
              class="text-xs text-muted hover:text-foreground disabled:opacity-30 leading-none"
              @click="emit('move-option', oi, 1)"
            >
              &#x25BC;
            </button>
          </div>
          <input
            v-model="opt.label"
            :disabled="isSchemaLocked"
            type="text"
            name="option-label"
            :placeholder="`Option ${oi + 1}`"
            :aria-label="t('accessibility.optionN', { n: oi + 1 })"
            class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
          />
          <button
            v-if="!isSchemaLocked"
            @click="emit('remove-option', oi)"
            :aria-label="t('accessibility.removeOption')"
            class="text-danger-500 hover:text-danger-600 text-sm"
          >
            &times;
          </button>
        </div>
        <button
          v-if="!isSchemaLocked"
          @click="emit('add-option')"
          class="text-sm text-brand-600 hover:underline"
        >
          {{ t('forms.builder.addOptionBtn') }}
        </button>
      </div>

      <div v-if="question.type === 'rating'">
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2">
            <label class="text-xs text-muted">{{ t('forms.builder.minLabel') }}</label
            ><input
              v-model.number="question.min"
              :disabled="isSchemaLocked"
              type="number"
              name="rating-min"
              class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
            />
          </div>
          <div class="flex items-center gap-2">
            <label class="text-xs text-muted">{{ t('forms.builder.maxLabel') }}</label
            ><input
              v-model.number="question.max"
              :disabled="isSchemaLocked"
              type="number"
              name="rating-max"
              class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        <p v-if="(question.min ?? 1) >= (question.max ?? 5)" class="text-sm text-danger-600 mt-1">
          {{ t('forms.builder.minMaxError') }}
        </p>
      </div>

      <div v-if="question.type === 'file_upload'" class="space-y-2">
        <div class="flex items-center gap-2">
          <label class="text-xs text-muted">{{ t('forms.builder.allowedTypesLabel') }}</label>
          <input
            :value="(question.allowed_types ?? []).join(', ')"
            @input="emit('update-allowed-types', $event)"
            :disabled="isSchemaLocked"
            type="text"
            name="allowed-types"
            :placeholder="t('forms.builder.allowedTypesPlaceholder')"
            class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
          />
        </div>
        <div class="flex items-center gap-2">
          <label class="text-xs text-muted">{{ t('forms.builder.maxSizeLabel') }}</label>
          <input
            v-model.number="question.max_size_mb"
            :disabled="isSchemaLocked"
            type="number"
            name="max-size"
            min="1"
            :placeholder="t('forms.builder.maxSizePlaceholder')"
            class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
          />
        </div>
      </div>
    </div>
  </div>
</template>
