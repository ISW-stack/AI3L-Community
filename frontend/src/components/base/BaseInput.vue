<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue?: string | number
  type?: string
  label?: string
  error?: string
  disabled?: boolean
  placeholder?: string
  maxlength?: number
  id?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const inputId = computed(
  () =>
    props.id ||
    (props.label ? `input-${props.label.toLowerCase().replace(/\s+/g, '-')}` : undefined),
)
</script>

<template>
  <div>
    <label v-if="label" :for="inputId" class="block text-sm font-medium text-foreground mb-1">
      {{ label }}
    </label>
    <input
      :id="inputId"
      :type="type || 'text'"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxlength"
      :class="[
        'w-full px-3 py-2 border rounded-lg outline-none transition text-foreground placeholder:text-muted text-base sm:text-sm',
        error
          ? 'border-danger-500 focus:ring-2 focus:ring-danger-500 focus:border-transparent'
          : 'border-border focus:ring-2 focus:ring-brand-500 focus:border-transparent',
        disabled && 'bg-surface-alt text-muted cursor-not-allowed',
      ]"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="mt-1 text-sm text-danger-600">{{ error }}</p>
  </div>
</template>
