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
      return 'Super Admin'
    case 'ADMIN':
      return 'Admin'
    case 'MEMBER':
      return 'Member'
    case 'GUEST':
      return 'Guest'
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
    toast.show('Invite code generated successfully.', 'success')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    toast.show(
      typeof detail === 'object' && detail?.message
        ? detail.message
        : detail || 'Failed to generate invite code.',
      'error',
    )
  } finally {
    generatingCode.value = false
  }
}

async function copyInviteCode() {
  try {
    await navigator.clipboard.writeText(generatedCode.value)
    codeCopied.value = true
    toast.show('Invite code copied to clipboard.', 'success')
    setTimeout(() => {
      codeCopied.value = false
    }, 2000)
  } catch {
    toast.show('Failed to copy invite code.', 'error')
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
    message.value = 'Profile updated successfully.'
  } catch (e: any) {
    message.value = e.response?.data?.detail || 'Failed to update profile.'
  } finally {
    saving.value = false
  }
}

async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const data = await apiUploadAvatar(file)
    auth.user = data
    message.value = 'Avatar updated successfully.'
  } catch (e: any) {
    message.value = e.response?.data?.detail || 'Failed to upload avatar.'
  }
}

async function changePassword() {
  passwordMessage.value = ''
  passwordError.value = false

  if (newPassword.value !== confirmPassword.value) {
    passwordMessage.value = 'New passwords do not match.'
    passwordError.value = true
    return
  }

  changingPassword.value = true
  try {
    await apiChangePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    passwordMessage.value = 'Password changed successfully. Redirecting to login...'
    passwordError.value = false
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    setTimeout(async () => {
      await auth.logout()
      router.push({ name: 'login' })
    }, 1500)
  } catch (e: any) {
    passwordMessage.value = e.response?.data?.detail || 'Failed to change password.'
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
    const err = e as { response?: { data?: { detail?: string } } }
    message.value = err.response?.data?.detail || 'Failed to delete account.'
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
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-6">Profile</h1>

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
        General
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
        Security
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
        Danger Zone
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
          <span v-else class="text-2xl text-muted">{{ (auth.user?.display_name || '?')[0] }}</span>
        </div>
        <label class="text-sm text-brand-600 hover:underline cursor-pointer">
          Change Avatar
          <input type="file" accept="image/png,image/jpeg" class="hidden" @change="uploadAvatar" />
        </label>
      </div>

      <!-- Member Info -->
      <BaseCard padding="lg" class="mb-6">
        <h2 class="text-sm font-medium text-muted mb-3">Member Info</h2>
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
            <label class="block text-sm font-medium text-foreground mb-1">Username</label>
            <input
              :value="auth.user?.username"
              disabled
              class="w-full px-3 py-2 bg-surface-alt border border-border rounded-lg text-muted"
            />
          </div>

          <BaseInput v-model="displayName" label="Display Name" :maxlength="100" />
          <BaseTextarea v-model="bio" label="Bio" :rows="3" :maxlength="500" />
          <BaseInput v-model="affiliation" label="Affiliation" :maxlength="200" />
          <BaseInput
            v-model="orcid"
            label="ORCID"
            :maxlength="50"
            placeholder="0000-0000-0000-0000"
          />

          <BaseButton type="submit" :loading="saving">Save</BaseButton>
        </form>
      </BaseCard>
    </div>

    <!-- Security Tab -->
    <div v-if="activeTab === 'security' && !auth.isGuest">
      <!-- Change Password -->
      <h2 class="text-xl font-bold text-foreground mb-4">Change Password</h2>

      <BaseAlert v-if="passwordMessage" :type="passwordError ? 'error' : 'success'" class="mb-4">{{
        passwordMessage
      }}</BaseAlert>

      <BaseCard padding="lg" class="mb-8">
        <form @submit.prevent="changePassword" class="space-y-4">
          <div class="relative">
            <BaseInput
              v-model="currentPassword"
              label="Current Password"
              :type="showCurrentPassword ? 'text' : 'password'"
            />
            <button
              type="button"
              class="absolute right-3 top-[34px] text-muted hover:text-foreground"
              @click="toggleCurrentPassword"
              :aria-label="showCurrentPassword ? 'Hide password' : 'Show password'"
            >
              <component :is="showCurrentPassword ? EyeOff : Eye" class="w-4 h-4" />
            </button>
          </div>
          <div>
            <div class="relative">
              <BaseInput
                v-model="newPassword"
                label="New Password"
                :type="showNewPassword ? 'text' : 'password'"
              />
              <button
                type="button"
                class="absolute right-3 top-[34px] text-muted hover:text-foreground"
                @click="toggleNewPassword"
                :aria-label="showNewPassword ? 'Hide password' : 'Show password'"
              >
                <component :is="showNewPassword ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>
            <p class="text-xs text-muted mt-1">
              At least 8 characters, with uppercase, lowercase, and a digit.
            </p>
          </div>
          <div class="relative">
            <BaseInput
              v-model="confirmPassword"
              label="Confirm New Password"
              :type="showConfirmPassword ? 'text' : 'password'"
            />
            <button
              type="button"
              class="absolute right-3 top-[34px] text-muted hover:text-foreground"
              @click="toggleConfirmPassword"
              :aria-label="showConfirmPassword ? 'Hide password' : 'Show password'"
            >
              <component :is="showConfirmPassword ? EyeOff : Eye" class="w-4 h-4" />
            </button>
          </div>

          <BaseButton
            type="submit"
            :loading="changingPassword"
            :disabled="!currentPassword || !newPassword || !confirmPassword"
          >
            Change Password
          </BaseButton>
        </form>
      </BaseCard>

      <!-- Invite Codes -->
      <h2 class="text-xl font-bold text-foreground mb-4">Invite Codes</h2>
      <BaseCard padding="lg">
        <p class="text-sm text-muted mb-4">
          Generate an invite code to share with others so they can create an account.
        </p>
        <div class="flex flex-col gap-3">
          <BaseButton :loading="generatingCode" @click="generateInviteCode">
            Generate Invite Code
          </BaseButton>
          <div v-if="generatedCode" class="flex items-center gap-2">
            <BaseInput :model-value="generatedCode" disabled class="flex-1" />
            <BaseButton variant="secondary" size="sm" @click="copyInviteCode">
              <component :is="codeCopied ? Check : Copy" class="w-4 h-4 mr-1" />
              {{ codeCopied ? 'Copied!' : 'Copy' }}
            </BaseButton>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- Danger Zone Tab -->
    <div v-if="activeTab === 'danger' && !auth.isGuest">
      <BaseAlert type="warning" class="mb-4"
        >Actions in this section are irreversible. Please proceed with caution.</BaseAlert
      >

      <h2 class="text-xl font-bold text-danger-600 mb-4">Danger Zone</h2>
      <BaseCard padding="lg">
        <p class="text-sm text-muted mb-4">
          Permanently delete your account and anonymize all personal data. This action cannot be
          undone.
        </p>
        <BaseButton variant="danger" @click="openDeleteConfirm"> Delete My Account </BaseButton>
      </BaseCard>
    </div>

    <!-- Delete Account Confirmation Modal -->
    <BaseModal v-model="showDeleteConfirm" title="Delete Account?" size="sm">
      <p class="text-sm text-muted mb-4">
        This will permanently anonymize your profile, remove all personal information, and log you
        out. Your posts will remain but be attributed to a deleted user.
      </p>
      <BaseInput v-model="deleteConfirmText" label="Type DELETE to confirm" placeholder="DELETE" />
      <template #footer>
        <BaseButton variant="secondary" @click="closeDeleteConfirm">Cancel</BaseButton>
        <BaseButton
          variant="danger"
          :disabled="deleteConfirmText !== 'DELETE'"
          :loading="deletingAccount"
          @click="handleDeleteAccount"
          >Delete Account</BaseButton
        >
      </template>
    </BaseModal>
  </div>
</template>
