<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import {
  updateProfile,
  uploadAvatar as apiUploadAvatar,
  changePassword as apiChangePassword,
  deleteAccount as apiDeleteAccount,
} from '@/api/users'
import { createInviteCode } from '@/api/admin'
import { getStorageUsage } from '@/api/files'
import { isContentEmpty } from '@/utils/html'
import { listMyInvitations, acceptInvitation, rejectInvitation } from '@/api/coauthors'
import type { CoAuthorInvitation } from '@/types/coauthor'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import ProfileEditForm from '@/components/profile/ProfileEditForm.vue'
import PasswordChangeForm from '@/components/profile/PasswordChangeForm.vue'
import DangerZone from '@/components/profile/DangerZone.vue'
import { getErrorMessage } from '@/utils/error'
import { useLocale } from '@/composables/useLocale'

const { t } = useLocale()
const auth = useAuthStore()
const router = useRouter()

const activeTab = ref<'general' | 'social' | 'security' | 'danger'>('general')

const displayName = ref('')
const bio = ref('')
const affiliation = ref('')
const orcid = ref('')
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error' | 'info'>('info')

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)
const passwordMessage = ref('')
const passwordError = ref(false)

const toast = useToastStore()

// Storage usage
const storageUsed = ref(0)
const storageQuota = ref(1_073_741_824)
const storageLoading = ref(false)
const storageError = ref(false)
const storagePercent = computed(() =>
  storageQuota.value > 0 ? Math.round((storageUsed.value / storageQuota.value) * 100) : 0,
)

async function fetchStorageUsage() {
  storageLoading.value = true
  storageError.value = false
  try {
    const data = await getStorageUsage()
    storageUsed.value = data.used_bytes
    storageQuota.value = data.quota_bytes
  } catch {
    storageError.value = true
  } finally {
    storageLoading.value = false
  }
}

// Co-author invitations
const coAuthorInvitations = ref<CoAuthorInvitation[]>([])
const coAuthorLoading = ref(false)
const coAuthorActionLoading = ref(false)

const coAuthorError = ref(false)

async function fetchCoAuthorInvitations() {
  coAuthorLoading.value = true
  coAuthorError.value = false
  try {
    const result = await listMyInvitations()
    coAuthorInvitations.value = result.invitations
  } catch {
    coAuthorError.value = true
  } finally {
    coAuthorLoading.value = false
  }
}

async function handleAcceptInvitation(id: string) {
  coAuthorActionLoading.value = true
  try {
    await acceptInvitation(id)
    coAuthorInvitations.value = coAuthorInvitations.value.filter((inv) => inv.id !== id)
    toast.show(t('coauthors.acceptSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  } finally {
    coAuthorActionLoading.value = false
  }
}

async function handleRejectInvitation(id: string) {
  coAuthorActionLoading.value = true
  try {
    await rejectInvitation(id)
    coAuthorInvitations.value = coAuthorInvitations.value.filter((inv) => inv.id !== id)
    toast.show(t('coauthors.rejectSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('common.unknownError')), 'error')
  } finally {
    coAuthorActionLoading.value = false
  }
}

const generatedCode = ref('')
const generatingCode = ref(false)
const codeCopied = ref(false)

let codeCopiedTimer: ReturnType<typeof setTimeout> | undefined
let logoutTimer: ReturnType<typeof setTimeout> | undefined

function switchTab(tab: 'general' | 'social' | 'security' | 'danger') {
  activeTab.value = tab
}

async function generateInviteCode() {
  generatingCode.value = true
  try {
    const data = await createInviteCode()
    generatedCode.value = data.invite_code
    toast.show(t('profile.security.inviteCodes.success'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('profile.security.inviteCodes.generateError')), 'error')
  } finally {
    generatingCode.value = false
  }
}

async function copyInviteCode() {
  try {
    await navigator.clipboard.writeText(generatedCode.value)
    codeCopied.value = true
    toast.show(t('profile.security.inviteCodes.copySuccess'), 'success')
    codeCopiedTimer = setTimeout(() => {
      codeCopied.value = false
    }, 2000)
  } catch {
    toast.show(t('profile.security.inviteCodes.copyError'), 'error')
  }
}

onMounted(() => {
  if (auth.user) {
    displayName.value = auth.user.display_name
    bio.value = auth.user.bio || ''
    affiliation.value = auth.user.affiliation || ''
    orcid.value = auth.user.orcid || ''
  }
  if (!auth.isGuest) {
    fetchStorageUsage()
    fetchCoAuthorInvitations()
  }
})

onUnmounted(() => {
  if (codeCopiedTimer) clearTimeout(codeCopiedTimer)
  if (logoutTimer) clearTimeout(logoutTimer)
})

async function saveProfile() {
  saving.value = true
  message.value = ''
  try {
    const data = await updateProfile({
      display_name: displayName.value.trim() || undefined,
      bio: isContentEmpty(bio.value) ? null : bio.value,
      affiliation: affiliation.value.trim() === '' ? null : affiliation.value.trim(),
      orcid: orcid.value.trim() === '' ? null : orcid.value.trim(),
    })
    auth.user = data
    message.value = t('profile.saveSuccess')
    messageType.value = 'success'
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('profile.saveError'))
    messageType.value = 'error'
  } finally {
    saving.value = false
  }
}

async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  message.value = ''
  try {
    const data = await apiUploadAvatar(file)
    auth.user = data
    message.value = t('profile.avatarSuccess')
    messageType.value = 'success'
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('profile.avatarError'))
    messageType.value = 'error'
  }
}

async function changePassword() {
  passwordMessage.value = ''
  passwordError.value = false

  if (newPassword.value !== confirmPassword.value) {
    passwordMessage.value = t('profile.security.changePassword.mismatch')
    passwordError.value = true
    return
  }

  changingPassword.value = true
  try {
    await apiChangePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    passwordMessage.value = t('profile.security.changePassword.success')
    passwordError.value = false
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    logoutTimer = setTimeout(async () => {
      await auth.logout()
      router.push({ name: 'login' })
    }, 1500)
  } catch (e: unknown) {
    passwordMessage.value = getErrorMessage(e, t('profile.security.changePassword.error'))
    passwordError.value = true
  } finally {
    changingPassword.value = false
  }
}

const deletingAccount = ref(false)
const dangerZoneRef = ref<InstanceType<typeof DangerZone> | null>(null)

async function handleDeleteAccount() {
  deletingAccount.value = true
  try {
    await apiDeleteAccount()
    auth.clearSession()
    router.push({ name: 'login' })
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('common.unknownError'))
    messageType.value = 'error'
  } finally {
    deletingAccount.value = false
    if (dangerZoneRef.value) {
      dangerZoneRef.value.showDeleteConfirm = false
    }
  }
}
</script>

<template>
  <div class="w-full lg:px-layout px-4 py-6 sm:py-8 min-h-screen">
    <div class="max-w-2xl mx-auto">
      <BaseBreadcrumb
        :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.profile') }]"
      />
      <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('profile.title') }}</h1>

      <BaseAlert v-if="message" :type="messageType" class="mb-4">{{ message }}</BaseAlert>

      <!-- Tab Navigation -->
      <div class="flex gap-1 mb-6 border-b border-border" role="tablist">
        <button
          id="tab-general"
          role="tab"
          :aria-selected="activeTab === 'general'"
          aria-controls="panel-general"
          class="px-4 py-2 text-sm font-medium border-b-2 transition"
          :class="
            activeTab === 'general'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-muted hover:text-foreground'
          "
          @click="switchTab('general')"
        >
          {{ t('profile.tabs.general') }}
        </button>
        <button
          v-if="!auth.isGuest"
          id="tab-social"
          role="tab"
          :aria-selected="activeTab === 'social'"
          aria-controls="panel-social"
          class="px-4 py-2 text-sm font-medium border-b-2 transition"
          :class="
            activeTab === 'social'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-muted hover:text-foreground'
          "
          @click="switchTab('social')"
        >
          {{ t('profile.tabs.social') }}
        </button>
        <button
          v-if="!auth.isGuest"
          id="tab-security"
          role="tab"
          :aria-selected="activeTab === 'security'"
          aria-controls="panel-security"
          class="px-4 py-2 text-sm font-medium border-b-2 transition"
          :class="
            activeTab === 'security'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-muted hover:text-foreground'
          "
          @click="switchTab('security')"
        >
          {{ t('profile.tabs.security') }}
        </button>
        <button
          v-if="!auth.isGuest"
          id="tab-danger"
          role="tab"
          :aria-selected="activeTab === 'danger'"
          aria-controls="panel-danger"
          class="px-4 py-2 text-sm font-medium border-b-2 transition"
          :class="
            activeTab === 'danger'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-muted hover:text-foreground'
          "
          @click="switchTab('danger')"
        >
          {{ t('profile.tabs.dangerZone') }}
        </button>
      </div>

      <!-- General Tab -->
      <ProfileEditForm
        v-if="activeTab === 'general'"
        id="panel-general"
        role="tabpanel"
        aria-labelledby="tab-general"
        v-model:display-name="displayName"
        v-model:bio="bio"
        v-model:affiliation="affiliation"
        v-model:orcid="orcid"
        :username="auth.user?.username || ''"
        :avatar-url="auth.user?.avatar_url ?? null"
        :role="auth.role"
        :storage-used="storageUsed"
        :storage-quota="storageQuota"
        :storage-percent="storagePercent"
        :storage-loading="storageLoading"
        :storage-error="storageError"
        :is-guest="auth.isGuest"
        :saving="saving"
        :display-name-initial="(auth.user?.display_name || '?')[0]"
        @save="saveProfile"
        @upload-avatar="uploadAvatar"
      />

      <!-- Social Tab -->
      <div v-if="activeTab === 'social' && !auth.isGuest" id="panel-social" role="tabpanel" aria-labelledby="tab-social" class="space-y-6">
        <!-- Quick Links -->
        <div class="space-y-3">
          <h3 class="text-sm font-semibold text-foreground">
            {{ t('profile.social.quickLinks') }}
          </h3>
          <div class="flex flex-wrap gap-3">
            <router-link
              to="/friends"
              class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-brand-600 bg-brand-50 rounded-lg hover:bg-brand-100 transition"
            >
              {{ t('social.friends') }}
            </router-link>
            <router-link
              to="/following"
              class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-brand-600 bg-brand-50 rounded-lg hover:bg-brand-100 transition"
            >
              {{ t('social.following') }}
            </router-link>
            <router-link
              to="/blocked-users"
              class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-muted bg-surface-alt rounded-lg hover:bg-border transition"
            >
              {{ t('social.blockedUsers') }}
            </router-link>
          </div>
        </div>

        <!-- Co-Author Invitations -->
        <div>
          <h3 class="text-sm font-semibold text-foreground mb-3">
            {{ t('coauthors.invitations') }}
          </h3>
          <div v-if="coAuthorLoading" class="text-sm text-muted">{{ t('common.loading') }}</div>
          <div
            v-else-if="coAuthorError"
            class="text-sm text-danger-600 py-3 bg-surface-alt rounded-lg px-4"
          >
            {{ t('profile.coAuthorFetchError') }}
          </div>
          <div
            v-else-if="coAuthorInvitations.length === 0"
            class="text-sm text-muted py-3 bg-surface-alt rounded-lg px-4"
          >
            {{ t('coauthors.noInvitations') }}
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="inv in coAuthorInvitations"
              :key="inv.id"
              class="flex items-center justify-between gap-3 p-3 bg-surface-alt rounded-lg"
            >
              <div class="min-w-0">
                <router-link
                  :to="`/forum/${inv.post_id}`"
                  class="text-sm font-medium text-foreground hover:text-brand-600 hover:underline block truncate"
                >
                  {{ inv.post_title }}
                </router-link>
                <p class="text-xs text-muted mt-0.5">
                  {{ t('coauthors.invitedBy') }} {{ inv.invited_by_name }}
                </p>
              </div>
              <div class="flex gap-2 shrink-0">
                <button
                  class="px-3 py-1 text-xs font-medium text-white bg-brand-600 rounded hover:bg-brand-700 transition disabled:opacity-50"
                  :disabled="coAuthorActionLoading"
                  @click="handleAcceptInvitation(inv.id)"
                >
                  {{ t('social.acceptRequest') }}
                </button>
                <button
                  class="px-3 py-1 text-xs font-medium text-muted bg-surface rounded border border-border hover:bg-surface-alt transition disabled:opacity-50"
                  :disabled="coAuthorActionLoading"
                  @click="handleRejectInvitation(inv.id)"
                >
                  {{ t('social.declineRequest') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Security Tab -->
      <PasswordChangeForm
        v-if="activeTab === 'security' && !auth.isGuest"
        id="panel-security"
        role="tabpanel"
        aria-labelledby="tab-security"
        v-model:current-password="currentPassword"
        v-model:new-password="newPassword"
        v-model:confirm-password="confirmPassword"
        :password-message="passwordMessage"
        :password-error="passwordError"
        :changing-password="changingPassword"
        :generated-code="generatedCode"
        :generating-code="generatingCode"
        :code-copied="codeCopied"
        @change-password="changePassword"
        @generate-invite-code="generateInviteCode"
        @copy-invite-code="copyInviteCode"
      />

      <!-- Danger Zone Tab -->
      <DangerZone
        v-if="activeTab === 'danger' && !auth.isGuest"
        id="panel-danger"
        role="tabpanel"
        aria-labelledby="tab-danger"
        ref="dangerZoneRef"
        :deleting-account="deletingAccount"
        @delete-account="handleDeleteAccount"
      />
    </div>
  </div>
</template>
