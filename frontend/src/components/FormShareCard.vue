<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { FormData } from '@/types'
import { getForm } from '@/api/forms'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const props = defineProps<{ formId: string }>()

const form = ref<FormData | null>(null)
const loading = ref(true)
const errorState = ref(false)

onMounted(async () => {
  try {
    form.value = await getForm(props.formId)
  } catch {
    errorState.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <SkeletonLoader v-if="loading" :lines="2" variant="card" />
  <p v-else-if="errorState" class="text-xs text-muted italic">[Form not found]</p>
  <router-link v-else-if="form" :to="`/forms/${form.id}`" class="block no-underline">
    <BaseCard class="border-l-4 border-purple-500 hover:shadow-md transition">
      <div class="flex items-start gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <BaseBadge variant="purple">Form</BaseBadge>
            <span class="font-semibold text-foreground text-sm">{{ form.title }}</span>
            <BaseBadge :variant="form.is_active ? 'success' : 'danger'" class="ml-auto shrink-0">
              {{ form.is_active ? 'Active' : 'Closed' }}
            </BaseBadge>
          </div>
          <p v-if="form.description" class="text-xs text-muted line-clamp-2 mb-1">
            {{ form.description }}
          </p>
          <div class="flex items-center gap-3 text-xs text-muted">
            <span>{{ form.response_count }} response(s)</span>
            <span v-if="form.deadline">
              Deadline: {{ new Date(form.deadline).toLocaleDateString() }}
            </span>
            <span>By {{ form.created_by_name }}</span>
          </div>
        </div>
      </div>
    </BaseCard>
  </router-link>
</template>
