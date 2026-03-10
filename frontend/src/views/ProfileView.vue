<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
import { Eye, EyeOff, Copy, Check } from 'lucide-vue-next'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { getErrorMessage } from '@/utils/error'
import { useLocale } from '@/composables/useLocale'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const { t } = useLocale()
const auth = useAuthStore()
const router = useRouter()

const activeTab = ref<'general' | 'security' | 'danger'>('general')

const displayName = ref('')
const bio = ref('')
const affiliation = ref('')
const orcid = ref('')
const saving = ref(false)
const message = ref('')

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)
const passwordMessage = ref('')
const passwordError = ref(false)
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

const toast = useToastStore()
const generatedCode = ref('')
const generatingCode = ref(false)
const codeCopied = ref(false)

function roleBadgeVariant(
  role: string | null | undefined,
): 'brand' | 'success' | 'warning' | 'purple' | 'neutral' {
  switch (role) {
    case 'SUPER_ADMIN':
      return 'purple'
    case 'ADMIN':
      return 'warning'
    case 'MEMBER':
      return 'brand'
    case 'GUEST':
      return 'neutral'
    default:
      return 'neutral'
  }
}

function roleBadgeLabel(role: string | null | undefined): string {
  switch (role) {
    case 'SUPER_ADMIN':
      return t('common.role.superAdmin')
    case 'ADMIN':
      return t('common.role.admin')
    case 'MEMBER':
      return t('common.role.member')
    case 'GUEST':
      return t('common.role.guest')
    default:
      return role || 'Unknown'
  }
}

function switchTab(tab: 'general' | 'security' | 'danger') {
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
    setTimeout(() => {
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
})

async function saveProfile() {
  saving.value = true
  message.value = ''
  try {
    const data = await updateProfile({
      display_name: displayName.value || undefined,
      bio: bio.value || undefined,
      affiliation: affiliation.value || undefined,
      orcid: orcid.value || undefined,
    })
    auth.user = data
    message.value = t('profile.saveSuccess')
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('profile.saveError'))
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
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('profile.avatarError'))
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
    setTimeout(async () => {
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

const showDeleteConfirm = ref(false)
const deleteConfirmText = ref('')
const deletingAccount = ref(false)

function openDeleteConfirm() {
  showDeleteConfirm.value = true
}

function closeDeleteConfirm() {
  showDeleteConfirm.value = false
}

async function handleDeleteAccount() {
  deletingAccount.value = true
  try {
    await apiDeleteAccount()
    auth.clearSession()
    router.push({ name: 'login' })
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('common.unknownError'))
  } finally {
    deletingAccount.value = false
    showDeleteConfirm.value = false
  }
}

function toggleCurrentPassword() {
  showCurrentPassword.value = !showCurrentPassword.value
}

function toggleNewPassword() {
  showNewPassword.value = !showNewPassword.value
}

function toggleConfirmPassword() {
  showConfirmPassword.value = !showConfirmPassword.value
}
</script>

<template>
  <div class="w-full lg:px-layout px-4 py-6 sm:py-8 min-h-screen">
    <div class="max-w-2xl mx-auto">
      <div class="mb-4 text-left">
        <router-link
          to="/forum"
          class="text-sm text-brand-600 hover:underline flex items-center gap-1"
        >
          <span>&larr;</span> {{ t('profile.backBtn') }}
        </router-link>
      </div>
      <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('profile.title') }}</h1>

      <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

      <!-- Tab Navigation -->
      <div class="flex gap-1 mb-6 border-b border-border">
        <button
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
      <div v-if="activeTab === 'general'">
        <!-- Avatar -->
        <div class="flex items-center gap-4 mb-6">
          <div
            class="w-20 h-20 rounded-full bg-surface-alt flex items-center justify-center overflow-hidden border border-border"
          >
            <img
              v-if="auth.user?.avatar_url"
              :src="auth.user.avatar_url"
              class="w-full h-full object-cover"
              alt="Avatar"
            />
            <span v-else class="text-2xl text-muted">{{
              (auth.user?.display_name || '?')[0]
            }}</span>
          </div>
          <label class="text-sm text-brand-600 hover:underline cursor-pointer">
            {{ t('profile.changeAvatar') }}
            <input
              type="file"
              accept="image/png,image/jpeg"
              class="hidden"
              @change="uploadAvatar"
            />
          </label>
        </div>

        <!-- Member Info -->
        <BaseCard padding="lg" class="mb-6">
          <h2 class="text-sm font-medium text-muted mb-3">{{ t('profile.memberInfo') }}</h2>
          <div class="flex items-center gap-3">
            <span class="text-sm text-foreground font-medium">{{
              auth.user?.username || '---'
            }}</span>
            <BaseBadge :variant="roleBadgeVariant(auth.role)">{{
              roleBadgeLabel(auth.role)
            }}</BaseBadge>
          </div>
        </BaseCard>

        <!-- Profile Form -->
        <BaseCard padding="lg" class="mb-8">
          <form @submit.prevent="saveProfile" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-foreground mb-1">{{
                t('profile.form.usernameLabel')
              }}</label>
              <input
                :value="auth.user?.username"
                disabled
                class="w-full px-3 py-2 bg-surface-alt border border-border rounded-lg text-muted"
              />
            </div>

            <BaseInput
              v-model="displayName"
              :label="t('profile.form.displayNameLabel')"
              :maxlength="100"
            />
            <BaseTextarea
              v-model="bio"
              :label="t('profile.form.bioLabel')"
              :rows="3"
              :maxlength="500"
            />
            <BaseInput
              v-model="affiliation"
              :label="t('profile.form.affiliationLabel')"
              :maxlength="200"
            />
            <BaseInput
              v-model="orcid"
              :label="t('profile.form.orcidLabel')"
              :maxlength="50"
              :placeholder="t('profile.form.orcidPlaceholder')"
            />

            <!-- Language selector -->
            <div>
              <label class="block text-sm font-medium text-foreground mb-1">{{
                t('profile.form.languageLabel')
              }}</label>
              <LanguageSwitcher variant="form" />
            </div>

            <BaseButton type="submit" :loading="saving">{{ t('profile.form.saveBtn') }}</BaseButton>
          </form>
        </BaseCard>
      </div>

      <!-- Security Tab -->
      <div v-if="activeTab === 'security' && !auth.isGuest">
        <!-- Change Password -->
        <h2 class="text-xl font-bold text-foreground mb-4">
          {{ t('profile.security.changePassword.title') }}
        </h2>

        <BaseAlert
          v-if="passwordMessage"
          :type="passwordError ? 'error' : 'success'"
          class="mb-4"
          >{{ passwordMessage }}</BaseAlert
        >

        <BaseCard padding="lg" class="mb-8">
          <form @submit.prevent="changePassword" class="space-y-4">
            <div class="relative">
              <BaseInput
                v-model="currentPassword"
                :label="t('profile.security.changePassword.currentLabel')"
                :type="showCurrentPassword ? 'text' : 'password'"
              />
              <button
                type="button"
                class="absolute right-3 top-[34px] text-muted hover:text-foreground"
                @click="toggleCurrentPassword"
                :aria-label="showCurrentPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              >
                <component :is="showCurrentPassword ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>
            <div>
              <div class="relative">
                <BaseInput
                  v-model="newPassword"
                  :label="t('profile.security.changePassword.newLabel')"
                  :type="showNewPassword ? 'text' : 'password'"
                />
                <button
                  type="button"
                  class="absolute right-3 top-[34px] text-muted hover:text-foreground"
                  @click="toggleNewPassword"
                  :aria-label="showNewPassword ? t('auth.hidePassword') : t('auth.showPassword')"
                >
                  <component :is="showNewPassword ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
              <p class="text-xs text-muted mt-1">
                {{ t('profile.security.changePassword.newHint') }}
              </p>
            </div>
            <div class="relative">
              <BaseInput
                v-model="confirmPassword"
                :label="t('profile.security.changePassword.confirmLabel')"
                :type="showConfirmPassword ? 'text' : 'password'"
              />
              <button
                type="button"
                class="absolute right-3 top-[34px] text-muted hover:text-foreground"
                @click="toggleConfirmPassword"
                :aria-label="showConfirmPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              >
                <component :is="showConfirmPassword ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>

            <BaseButton
              type="submit"
              :loading="changingPassword"
              :disabled="!currentPassword || !newPassword || !confirmPassword"
            >
              {{ t('profile.security.changePassword.btn') }}
            </BaseButton>
          </form>
        </BaseCard>

        <!-- Invite Codes -->
        <h2 class="text-xl font-bold text-foreground mb-4">
          {{ t('profile.security.inviteCodes.title') }}
        </h2>
        <BaseCard padding="lg">
          <p class="text-sm text-muted mb-4">
            {{ t('profile.security.inviteCodes.description') }}
          </p>
          <div class="flex flex-col gap-3">
            <BaseButton :loading="generatingCode" @click="generateInviteCode">
              {{ t('profile.security.inviteCodes.generateBtn') }}
            </BaseButton>
            <div v-if="generatedCode" class="flex items-center gap-2">
              <BaseInput :model-value="generatedCode" disabled class="flex-1" />
              <BaseButton variant="secondary" size="sm" @click="copyInviteCode">
                <component :is="codeCopied ? Check : Copy" class="w-4 h-4 mr-1" />
                {{
                  codeCopied
                    ? t('profile.security.inviteCodes.copiedBtn')
                    : t('profile.security.inviteCodes.copyBtn')
                }}
              </BaseButton>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Danger Zone Tab -->
      <div v-if="activeTab === 'danger' && !auth.isGuest">
        <BaseAlert type="warning" class="mb-4">{{ t('profile.dangerZone.warning') }}</BaseAlert>

        <h2 class="text-xl font-bold text-danger-600 mb-4">{{ t('profile.dangerZone.title') }}</h2>
        <BaseCard padding="lg">
          <p class="text-sm text-muted mb-4">
            {{ t('profile.dangerZone.deleteDescription') }}
          </p>
          <BaseButton variant="danger" @click="openDeleteConfirm">
            {{ t('profile.dangerZone.deleteBtn') }}
          </BaseButton>
        </BaseCard>
      </div>

      <!-- Delete Account Confirmation Modal -->
      <BaseModal
        v-model="showDeleteConfirm"
        :title="t('profile.dangerZone.deleteConfirm.title')"
        size="sm"
      >
        <p class="text-sm text-muted mb-4">
          {{ t('profile.dangerZone.deleteConfirm.message') }}
        </p>
        <BaseInput
          v-model="deleteConfirmText"
          :label="t('profile.dangerZone.deleteConfirm.typeLabel')"
          :placeholder="t('profile.dangerZone.deleteConfirm.placeholder')"
        />
        <template #footer>
          <BaseButton variant="secondary" @click="closeDeleteConfirm">{{
            t('common.cancel')
          }}</BaseButton>
          <BaseButton
            variant="danger"
            :disabled="deleteConfirmText !== 'DELETE'"
            :loading="deletingAccount"
            @click="handleDeleteAccount"
            >{{ t('profile.dangerZone.deleteConfirm.confirmBtn') }}</BaseButton
          >
        </template>
      </BaseModal>
    </div>
  </div>
</template>
