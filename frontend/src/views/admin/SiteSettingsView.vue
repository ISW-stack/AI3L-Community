<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getAboutIntro, updateAboutIntroPhoto, updateAboutIntroBio } from '@/api/about'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { Upload, User } from 'lucide-vue-next'

const { t } = useI18n()
const toast = useToastStore()

const loading = ref(true)
const photoUrl = ref('')
const bio = ref('')
const savingPhoto = ref(false)
const savingBio = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

async function fetchIntro() {
  try {
    const data = await getAboutIntro()
    photoUrl.value = data.photo_url
    bio.value = data.bio
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function triggerFileInput() {
  fileInput.value?.click()
}

async function handlePhotoChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  savingPhoto.value = true
  try {
    const result = await updateAboutIntroPhoto(file)
    photoUrl.value = result.photo_url
    toast.show(t('admin.siteSettings.photoUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.photoFailed')), 'error')
  } finally {
    savingPhoto.value = false
    input.value = ''
  }
}

async function handleSaveBio() {
  savingBio.value = true
  try {
    await updateAboutIntroBio(bio.value)
    toast.show(t('admin.siteSettings.bioUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.bioFailed')), 'error')
  } finally {
    savingBio.value = false
  }
}

onMounted(fetchIntro)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.siteSettings') },
      ]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('admin.siteSettings.title') }}</h1>

    <SkeletonLoader v-if="loading" :lines="6" variant="list" />

    <div v-else class="space-y-8 max-w-2xl">
      <!-- About Introduction -->
      <section class="bg-surface rounded-lg shadow border border-border p-6">
        <h2 class="text-lg font-semibold text-foreground mb-4">
          {{ t('admin.siteSettings.aboutIntro') }}
        </h2>

        <!-- Photo -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.photoLabel') }}
          </label>
          <div class="flex items-center gap-4">
            <div class="shrink-0">
              <img
                v-if="photoUrl"
                :src="photoUrl"
                alt="Introduction photo"
                class="w-32 h-32 rounded-lg object-cover border border-border"
              />
              <div
                v-else
                class="w-32 h-32 rounded-lg bg-surface-alt border border-border flex items-center justify-center"
              >
                <User :size="48" class="text-muted/40" />
              </div>
            </div>
            <div>
              <BaseButton
                variant="secondary"
                :loading="savingPhoto"
                :disabled="savingPhoto"
                @click="triggerFileInput"
              >
                <Upload :size="16" class="mr-1.5" />
                {{ photoUrl ? t('admin.siteSettings.changePhoto') : t('admin.siteSettings.uploadPhoto') }}
              </BaseButton>
              <p class="text-xs text-muted mt-1.5">{{ t('admin.siteSettings.photoHint') }}</p>
              <input
                ref="fileInput"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                class="hidden"
                @change="handlePhotoChange"
              />
            </div>
          </div>
        </div>

        <!-- Bio -->
        <div>
          <label class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.bioLabel') }}
          </label>
          <textarea
            v-model="bio"
            :placeholder="t('admin.siteSettings.bioPlaceholder')"
            rows="8"
            class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
            maxlength="5000"
          />
          <div class="flex items-center justify-between mt-2">
            <span class="text-xs text-muted">{{ bio.length }} / 5000</span>
            <BaseButton :loading="savingBio" :disabled="savingBio" @click="handleSaveBio">
              {{ t('admin.siteSettings.saveBio') }}
            </BaseButton>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
