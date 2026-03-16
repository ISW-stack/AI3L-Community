<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import { createAlbum } from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useLocale()
const router = useRouter()
const toast = useToastStore()

const title = ref('')
const description = ref('')
const saving = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''
  if (!title.value.trim()) {
    error.value = t('albums.titleRequired')
    return
  }
  saving.value = true
  try {
    const { data } = await createAlbum({
      title: title.value.trim(),
      description: description.value.trim() || undefined,
    })
    toast.show(t('albums.createSuccess'), 'success')
    router.push(`/albums/${data.id}`)
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('albums.createError'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-xl mx-auto">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('albums.title'), to: '/albums' },
        { label: t('albums.createAlbum') },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('albums.createAlbum') }}</h1>

    <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

    <BaseCard padding="lg" class="space-y-4">
      <BaseInput
        v-model="title"
        :label="t('albums.titleLabel')"
        :placeholder="t('albums.titlePlaceholder')"
      />
      <BaseTextarea
        v-model="description"
        :label="t('albums.descriptionLabel')"
        :rows="4"
        :placeholder="t('albums.descriptionPlaceholder')"
      />
      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="router.push('/albums')">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton :loading="saving" @click="handleSubmit">{{
          t('albums.createAlbum')
        }}</BaseButton>
      </div>
    </BaseCard>
  </div>
</template>
