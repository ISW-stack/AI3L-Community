<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getAboutIntro,
  updateAboutIntroPhoto,
  updateAboutIntroBio,
  updateChairPhoto,
  updateChairBio,
  setLeadershipChair,
  removeLeadershipChair,
  setLeadershipCoChairs,
  getLeadership,
} from '@/api/about'
import type { LeadershipData } from '@/api/about'
import api from '@/composables/api'
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

// Leadership state
const leadershipData = ref<LeadershipData | null>(null)
const leadershipLoading = ref(true)
const chairSearchQuery = ref('')
const coChairSearchQuery = ref('')
const chairSearchResults = ref<Array<{ id: string; display_name: string; avatar_url: string | null }>>([])
const coChairSearchResults = ref<Array<{ id: string; display_name: string; avatar_url: string | null }>>([])
const chairSearching = ref(false)
const coChairSearching = ref(false)

async function fetchLeadership() {
  leadershipLoading.value = true
  try {
    leadershipData.value = await getLeadership()
  } catch {
    leadershipData.value = null
  } finally {
    leadershipLoading.value = false
  }
}

let chairSearchTimer: ReturnType<typeof setTimeout> | null = null
function onChairSearchInput() {
  if (chairSearchTimer) clearTimeout(chairSearchTimer)
  if (!chairSearchQuery.value.trim()) {
    chairSearchResults.value = []
    return
  }
  chairSearchTimer = setTimeout(async () => {
    chairSearching.value = true
    try {
      const res = await api.get('/users/search', { params: { q: chairSearchQuery.value.trim(), limit: 5 } })
      chairSearchResults.value = res.data
    } catch {
      chairSearchResults.value = []
    } finally {
      chairSearching.value = false
    }
  }, 300)
}

async function selectChair(user: { id: string; display_name: string }) {
  try {
    await setLeadershipChair(user.id)
    chairSearchQuery.value = ''
    chairSearchResults.value = []
    await fetchLeadership()
  } catch {
    // silent
  }
}

async function removeChair() {
  try {
    await removeLeadershipChair()
    await fetchLeadership()
  } catch {
    // silent
  }
}

let coChairSearchTimer: ReturnType<typeof setTimeout> | null = null
function onCoChairSearchInput() {
  if (coChairSearchTimer) clearTimeout(coChairSearchTimer)
  if (!coChairSearchQuery.value.trim()) {
    coChairSearchResults.value = []
    return
  }
  coChairSearchTimer = setTimeout(async () => {
    coChairSearching.value = true
    try {
      const res = await api.get('/users/search', { params: { q: coChairSearchQuery.value.trim(), limit: 5 } })
      coChairSearchResults.value = res.data
    } catch {
      coChairSearchResults.value = []
    } finally {
      coChairSearching.value = false
    }
  }, 300)
}

async function addCoChair(user: { id: string }) {
  if (!leadershipData.value) return
  const currentIds = leadershipData.value.co_chairs.map((c) => c.user_id)
  if (currentIds.includes(user.id)) return
  try {
    await setLeadershipCoChairs([...currentIds, user.id])
    coChairSearchQuery.value = ''
    coChairSearchResults.value = []
    await fetchLeadership()
  } catch {
    // silent
  }
}

async function removeCoChair(userId: string) {
  if (!leadershipData.value) return
  const newIds = leadershipData.value.co_chairs.filter((c) => c.user_id !== userId).map((c) => c.user_id)
  try {
    await setLeadershipCoChairs(newIds)
    await fetchLeadership()
  } catch {
    // silent
  }
}

onMounted(() => {
  fetchIntro()
  fetchLeadership()
})
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
      <!-- Leadership Assignment -->
      <section class="bg-surface border border-border rounded-xl p-6 mb-8">
        <h2 class="text-xl font-semibold text-foreground mb-6">
          {{ t('admin.siteSettings.leadership') || 'Leadership Assignment' }}
        </h2>

        <div v-if="leadershipLoading" class="text-muted text-sm">Loading...</div>

        <div v-else class="space-y-6">
          <!-- Chair -->
          <div>
            <h3 class="text-base font-medium text-foreground mb-3">Chair</h3>
            <div v-if="leadershipData?.chair" class="flex items-center gap-3 mb-3 p-3 bg-surface-alt rounded-lg">
              <img
                v-if="leadershipData.chair.avatar_url"
                :src="leadershipData.chair.avatar_url"
                :alt="leadershipData.chair.display_name"
                class="w-10 h-10 rounded-full object-cover border border-border"
              />
              <div v-else class="w-10 h-10 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
                {{ leadershipData.chair.display_name.charAt(0).toUpperCase() }}
              </div>
              <span class="text-sm font-medium text-foreground">{{ leadershipData.chair.display_name }}</span>
              <button
                class="ml-auto text-xs text-danger-600 hover:text-danger-700"
                @click="removeChair"
              >
                {{ t('common.remove') || 'Remove' }}
              </button>
            </div>
            <div class="relative">
              <input
                v-model="chairSearchQuery"
                type="text"
                :placeholder="t('admin.siteSettings.searchUser') || 'Search user...'"
                class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface text-foreground"
                @input="onChairSearchInput"
              />
              <div v-if="chairSearchResults.length > 0" class="absolute z-10 mt-1 w-full bg-surface border border-border rounded-lg shadow-lg max-h-48 overflow-auto">
                <button
                  v-for="user in chairSearchResults"
                  :key="user.id"
                  class="w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface-alt transition"
                  @click="selectChair(user)"
                >
                  <img
                    v-if="user.avatar_url"
                    :src="user.avatar_url"
                    :alt="user.display_name"
                    class="w-8 h-8 rounded-full object-cover"
                  />
                  <div v-else class="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold">
                    {{ user.display_name.charAt(0).toUpperCase() }}
                  </div>
                  <span>{{ user.display_name }}</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Co-Chairs -->
          <div>
            <h3 class="text-base font-medium text-foreground mb-3">Co-Chairs</h3>
            <div v-if="leadershipData && leadershipData.co_chairs.length > 0" class="space-y-2 mb-3">
              <div
                v-for="coChair in leadershipData.co_chairs"
                :key="coChair.user_id"
                class="flex items-center gap-3 p-3 bg-surface-alt rounded-lg"
              >
                <img
                  v-if="coChair.avatar_url"
                  :src="coChair.avatar_url"
                  :alt="coChair.display_name"
                  class="w-10 h-10 rounded-full object-cover border border-border"
                />
                <div v-else class="w-10 h-10 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
                  {{ coChair.display_name.charAt(0).toUpperCase() }}
                </div>
                <span class="text-sm font-medium text-foreground">{{ coChair.display_name }}</span>
                <button
                  class="ml-auto text-xs text-danger-600 hover:text-danger-700"
                  @click="removeCoChair(coChair.user_id)"
                >
                  {{ t('common.remove') || 'Remove' }}
                </button>
              </div>
            </div>
            <div class="relative">
              <input
                v-model="coChairSearchQuery"
                type="text"
                :placeholder="t('admin.siteSettings.searchUser') || 'Search user...'"
                class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface text-foreground"
                @input="onCoChairSearchInput"
              />
              <div v-if="coChairSearchResults.length > 0" class="absolute z-10 mt-1 w-full bg-surface border border-border rounded-lg shadow-lg max-h-48 overflow-auto">
                <button
                  v-for="user in coChairSearchResults"
                  :key="user.id"
                  class="w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface-alt transition"
                  @click="addCoChair(user)"
                >
                  <img
                    v-if="user.avatar_url"
                    :src="user.avatar_url"
                    :alt="user.display_name"
                    class="w-8 h-8 rounded-full object-cover"
                  />
                  <div v-else class="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold">
                    {{ user.display_name.charAt(0).toUpperCase() }}
                  </div>
                  <span>{{ user.display_name }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

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
