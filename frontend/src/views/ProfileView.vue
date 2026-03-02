<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  updateProfile,
  uploadAvatar as apiUploadAvatar,
  changePassword as apiChangePassword,
  deleteAccount as apiDeleteAccount,
} from '@/api/users'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const auth = useAuthStore()
const router = useRouter()

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
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-6">Profile</h1>

    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

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

        <BaseInput v-model="displayName" label="Display Name" maxlength="100" />
        <BaseTextarea v-model="bio" label="Bio" :rows="3" maxlength="500" />
        <BaseInput v-model="affiliation" label="Affiliation" maxlength="200" />
        <BaseInput v-model="orcid" label="ORCID" maxlength="50" placeholder="0000-0000-0000-0000" />

        <BaseButton type="submit" :loading="saving">Save</BaseButton>
      </form>
    </BaseCard>

    <!-- Change Password -->
    <div v-if="!auth.isGuest" class="pt-8 border-t border-border">
      <h2 class="text-xl font-bold text-foreground mb-4">Change Password</h2>

      <BaseAlert v-if="passwordMessage" :type="passwordError ? 'error' : 'success'" class="mb-4">{{
        passwordMessage
      }}</BaseAlert>

      <BaseCard padding="lg">
        <form @submit.prevent="changePassword" class="space-y-4">
          <BaseInput v-model="currentPassword" label="Current Password" type="password" />
          <div>
            <BaseInput v-model="newPassword" label="New Password" type="password" />
            <p class="text-xs text-muted mt-1">
              At least 8 characters, with uppercase, lowercase, and a digit.
            </p>
          </div>
          <BaseInput v-model="confirmPassword" label="Confirm New Password" type="password" />

          <BaseButton
            type="submit"
            :loading="changingPassword"
            :disabled="!currentPassword || !newPassword || !confirmPassword"
          >
            Change Password
          </BaseButton>
        </form>
      </BaseCard>
    </div>

    <!-- Danger Zone -->
    <div v-if="!auth.isGuest" class="pt-8 border-t border-border">
      <h2 class="text-xl font-bold text-danger-600 mb-4">Danger Zone</h2>
      <BaseCard padding="lg">
        <p class="text-sm text-muted mb-4">
          Permanently delete your account and anonymize all personal data. This action cannot be
          undone.
        </p>
        <BaseButton variant="danger" @click="showDeleteConfirm = true">
          Delete My Account
        </BaseButton>
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
        <BaseButton variant="secondary" @click="showDeleteConfirm = false">Cancel</BaseButton>
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
