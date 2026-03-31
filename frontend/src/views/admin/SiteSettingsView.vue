<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getAboutIntro,
  updateAboutIntroPhoto,
  updateAboutIntroBio,
  updateChairPhoto,
  updateChairBio,
} from '@/api/about'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import ImageCropper from '@/components/ImageCropper.vue'
import { Upload, User } from 'lucide-vue-next'

const { t } = useI18n()
const toast = useToastStore()

const loading = ref(true)

// Chair state
const chairPhotoUrl = ref('')
const chairBio = ref('')
const savingChairPhoto = ref(false)
const savingChairBio = ref(false)
const chairFileInput = ref<HTMLInputElement | null>(null)
const showChairCropper = ref(false)
const chairCropFile = ref<File | null>(null)

// Co-Chair state (previously "intro")
const coChairPhotoUrl = ref('')
const coChairBio = ref('')
const savingCoChairPhoto = ref(false)
const savingCoChairBio = ref(false)
const coChairFileInput = ref<HTMLInputElement | null>(null)
const showCoChairCropper = ref(false)
const coChairCropFile = ref<File | null>(null)

async function fetchIntro() {
  try {
    const data = await getAboutIntro()
    coChairPhotoUrl.value = data.photo_url
    coChairBio.value = data.bio
    chairPhotoUrl.value = data.chair_photo_url
    chairBio.value = data.chair_bio
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

// ── Chair handlers ──

function triggerChairFileInput() {
  chairFileInput.value?.click()
}

function handleChairFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  chairCropFile.value = file
  showChairCropper.value = true
  input.value = ''
}

async function handleChairCropConfirm(croppedFile: File) {
  savingChairPhoto.value = true
  try {
    const result = await updateChairPhoto(croppedFile)
    chairPhotoUrl.value = result.photo_url
    toast.show(t('admin.siteSettings.photoUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.photoFailed')), 'error')
  } finally {
    savingChairPhoto.value = false
  }
}

async function handleSaveChairBio() {
  savingChairBio.value = true
  try {
    await updateChairBio(chairBio.value)
    toast.show(t('admin.siteSettings.bioUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.bioFailed')), 'error')
  } finally {
    savingChairBio.value = false
  }
}

// ── Co-Chair handlers ──

function triggerCoChairFileInput() {
  coChairFileInput.value?.click()
}

function handleCoChairFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  coChairCropFile.value = file
  showCoChairCropper.value = true
  input.value = ''
}

async function handleCoChairCropConfirm(croppedFile: File) {
  savingCoChairPhoto.value = true
  try {
    const result = await updateAboutIntroPhoto(croppedFile)
    coChairPhotoUrl.value = result.photo_url
    toast.show(t('admin.siteSettings.photoUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.photoFailed')), 'error')
  } finally {
    savingCoChairPhoto.value = false
  }
}

async function handleSaveCoChairBio() {
  savingCoChairBio.value = true
  try {
    await updateAboutIntroBio(coChairBio.value)
    toast.show(t('admin.siteSettings.bioUpdated'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.siteSettings.bioFailed')), 'error')
  } finally {
    savingCoChairBio.value = false
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
      <!-- Chair Section -->
      <section class="bg-surface rounded-lg shadow border border-border p-6">
        <h2 class="text-lg font-semibold text-foreground mb-4">
          {{ t('admin.siteSettings.chairIntro') }}
        </h2>

        <!-- Chair Photo -->
        <div class="mb-6">
          <span class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.photoLabel') }}
          </span>
          <div class="flex items-center gap-4">
            <div class="shrink-0">
              <img
                v-if="chairPhotoUrl"
                :src="chairPhotoUrl"
                alt="Chair photo"
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
                :loading="savingChairPhoto"
                :disabled="savingChairPhoto"
                @click="triggerChairFileInput"
              >
                <Upload :size="16" class="mr-1.5" />
                {{
                  chairPhotoUrl
                    ? t('admin.siteSettings.changePhoto')
                    : t('admin.siteSettings.uploadPhoto')
                }}
              </BaseButton>
              <p class="text-xs text-muted mt-1.5">{{ t('admin.siteSettings.photoHint') }}</p>
              <input
                ref="chairFileInput"
                type="file"
                name="chair-photo"
                accept="image/jpeg,image/png,image/webp"
                class="hidden"
                @change="handleChairFileSelect"
              />
            </div>
          </div>
        </div>

        <!-- Chair Bio -->
        <div>
          <label for="chair-bio" class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.bioLabel') }}
          </label>
          <textarea
            id="chair-bio"
            v-model="chairBio"
            name="chair-bio"
            :placeholder="t('admin.siteSettings.bioPlaceholder')"
            rows="8"
            class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
            maxlength="5000"
          />
          <div class="flex items-center justify-between mt-2">
            <span class="text-xs text-muted">{{ chairBio.length }} / 5000</span>
            <BaseButton
              :loading="savingChairBio"
              :disabled="savingChairBio"
              @click="handleSaveChairBio"
            >
              {{ t('admin.siteSettings.saveBio') }}
            </BaseButton>
          </div>
        </div>
      </section>

      <!-- Co-Chair Section -->
      <section class="bg-surface rounded-lg shadow border border-border p-6">
        <h2 class="text-lg font-semibold text-foreground mb-4">
          {{ t('admin.siteSettings.coChairIntro') }}
        </h2>

        <!-- Co-Chair Photo -->
        <div class="mb-6">
          <span class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.photoLabel') }}
          </span>
          <div class="flex items-center gap-4">
            <div class="shrink-0">
              <img
                v-if="coChairPhotoUrl"
                :src="coChairPhotoUrl"
                alt="Co-Chair photo"
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
                :loading="savingCoChairPhoto"
                :disabled="savingCoChairPhoto"
                @click="triggerCoChairFileInput"
              >
                <Upload :size="16" class="mr-1.5" />
                {{
                  coChairPhotoUrl
                    ? t('admin.siteSettings.changePhoto')
                    : t('admin.siteSettings.uploadPhoto')
                }}
              </BaseButton>
              <p class="text-xs text-muted mt-1.5">{{ t('admin.siteSettings.photoHint') }}</p>
              <input
                ref="coChairFileInput"
                type="file"
                name="cochair-photo"
                accept="image/jpeg,image/png,image/webp"
                class="hidden"
                @change="handleCoChairFileSelect"
              />
            </div>
          </div>
        </div>

        <!-- Co-Chair Bio -->
        <div>
          <label for="cochair-bio" class="block text-sm font-medium text-foreground mb-2">
            {{ t('admin.siteSettings.bioLabel') }}
          </label>
          <textarea
            id="cochair-bio"
            v-model="coChairBio"
            name="cochair-bio"
            :placeholder="t('admin.siteSettings.bioPlaceholder')"
            rows="8"
            class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
            maxlength="5000"
          />
          <div class="flex items-center justify-between mt-2">
            <span class="text-xs text-muted">{{ coChairBio.length }} / 5000</span>
            <BaseButton
              :loading="savingCoChairBio"
              :disabled="savingCoChairBio"
              @click="handleSaveCoChairBio"
            >
              {{ t('admin.siteSettings.saveBio') }}
            </BaseButton>
          </div>
        </div>
      </section>
    </div>

    <!-- Image Croppers -->
    <ImageCropper
      v-model="showChairCropper"
      :file="chairCropFile"
      @confirm="handleChairCropConfirm"
    />
    <ImageCropper
      v-model="showCoChairCropper"
      :file="coChairCropFile"
      @confirm="handleCoChairCropConfirm"
    />
  </div>
</template>
