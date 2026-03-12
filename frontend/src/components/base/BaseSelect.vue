<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue?: string | number
  label?: string
  error?: string
  disabled?: boolean
  options: Array<{ value: string | number; label: string }>
  placeholder?: string
  id?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selectId = computed(
  () =>
    props.id ||
    (props.label ? `select-${props.label.toLowerCase().replace(/\s+/g, '-')}` : undefined),
)
</script>

<template>
  <div>
    <label v-if="label" :for="selectId" class="block text-sm font-medium text-foreground mb-1">
      {{ label }}
    </label>
    <select
      :id="selectId"
      :value="modelValue"
      :disabled="disabled"
      :class="[
        'w-full px-3 py-2 border rounded-lg outline-none transition text-foreground text-base sm:text-sm',
        error
          ? 'border-danger-500 focus:ring-2 focus:ring-danger-500 focus:border-transparent'
          : 'border-border focus:ring-2 focus:ring-brand-500 focus:border-transparent',
        disabled && 'bg-surface-alt text-muted cursor-not-allowed',
      ]"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <slot>
        <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </slot>
    </select>
    <p v-if="error" class="mt-1 text-sm text-danger-600">{{ error }}</p>
  </div>
</template>
