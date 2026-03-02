<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createSig } from '@/api/sigs'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

const router = useRouter()
const name = ref('')
const description = ref('')
const saving = ref(false)
const message = ref('')

async function handleCreate() {
  if (!name.value.trim()) {
    message.value = 'Name is required.'
    return
  }
  saving.value = true
  message.value = ''
  try {
    const sig = await createSig({
      name: name.value,
      description: description.value || null,
    })
    router.push(`/sigs/${sig.id}`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.value = err.response?.data?.detail || 'Failed to create SIG.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-6">Create SIG</h1>

    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form @submit.prevent="handleCreate" class="space-y-4">
      <BaseInput v-model="name" label="Name" placeholder="SIG name" required maxlength="200" />
      <BaseTextarea
        v-model="description"
        label="Description (optional)"
        placeholder="Describe the purpose of this SIG..."
        :rows="4"
      />

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">Create SIG</BaseButton>
        <router-link to="/sigs">
          <BaseButton type="button" variant="secondary" size="lg">Cancel</BaseButton>
        </router-link>
      </div>
    </form>
  </div>
</template>
