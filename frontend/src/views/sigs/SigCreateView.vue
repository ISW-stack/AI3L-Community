<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSig } from '@/api/sigs'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

const { t } = useI18n()
const router = useRouter()
const name = ref('')
const description = ref('')
const saving = ref(false)
const message = ref('')

async function handleCreate() {
  if (!name.value.trim()) {
    message.value = t('sigs.create.nameRequired')
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
    message.value = err.response?.data?.detail || t('sigs.create.error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('sigs.create.title') }}</h1>

    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form @submit.prevent="handleCreate" class="space-y-4">
      <BaseInput v-model="name" :label="t('sigs.create.nameLabel')" :placeholder="t('sigs.create.namePlaceholder')" required :maxlength="200" />
      <BaseTextarea
        v-model="description"
        :label="t('sigs.create.descLabel')"
        :placeholder="t('sigs.create.descPlaceholder')"
        :rows="4"
      />

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">{{ t('sigs.create.createBtn') }}</BaseButton>
        <router-link to="/sigs">
          <BaseButton type="button" variant="secondary" size="lg">{{ t('sigs.create.cancelBtn') }}</BaseButton>
        </router-link>
      </div>
    </form>
  </div>
</template>
