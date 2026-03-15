<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToastStore } from '@/stores/toast'
import { createAlbum } from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const router = useRouter()
const toast = useToastStore()

const title = ref('')
const description = ref('')
const saving = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''
  if (!title.value.trim()) {
    error.value = 'Title is required.'
    return
  }
  saving.value = true
  try {
    const { data } = await createAlbum({
      title: title.value.trim(),
      description: description.value.trim() || undefined,
    })
    toast.show('Album created successfully', 'success')
    router.push(`/albums/${data.id}`)
  } catch (e: unknown) {
    error.value = getErrorMessage(e, 'Failed to create album')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-xl mx-auto">
    <BaseBreadcrumb
      :items="[
        { label: 'Home', to: '/' },
        { label: 'Albums', to: '/albums' },
        { label: 'Create Album' },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-6">Create Album</h1>

    <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

    <BaseCard padding="lg" class="space-y-4">
      <BaseInput
        v-model="title"
        label="Title"
        placeholder="Enter album title"
      />
      <BaseTextarea
        v-model="description"
        label="Description (optional)"
        :rows="4"
        placeholder="Describe this album..."
      />
      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="router.push('/albums')">Cancel</BaseButton>
        <BaseButton :loading="saving" @click="handleSubmit">Create Album</BaseButton>
      </div>
    </BaseCard>
  </div>
</template>
