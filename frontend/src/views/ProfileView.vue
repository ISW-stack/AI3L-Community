<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'

const auth = useAuthStore()

const displayName = ref('')
const bio = ref('')
const affiliation = ref('')
const orcid = ref('')
const saving = ref(false)
const message = ref('')

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
    const { data } = await api.put('/users/me', {
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

  const formData = new FormData()
  formData.append('file', file)

  try {
    const { data } = await api.put('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    auth.user = data
    message.value = 'Avatar updated successfully.'
  } catch (e: any) {
    message.value = e.response?.data?.detail || 'Failed to upload avatar.'
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Profile</h1>

    <div v-if="message" class="bg-blue-50 border border-blue-200 text-blue-700 rounded-lg p-3 mb-4 text-sm">
      {{ message }}
    </div>

    <!-- Avatar -->
    <div class="flex items-center gap-4 mb-6">
      <div class="w-20 h-20 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden">
        <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" />
        <span v-else class="text-2xl text-gray-400">{{ (auth.user?.display_name || '?')[0] }}</span>
      </div>
      <label class="text-sm text-blue-600 hover:underline cursor-pointer">
        Change Avatar
        <input type="file" accept="image/png,image/jpeg" class="hidden" @change="uploadAvatar" />
      </label>
    </div>

    <form @submit.prevent="saveProfile" class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
        <input :value="auth.user?.username" disabled class="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-gray-500" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
        <input v-model="displayName" type="text" maxlength="100" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Bio</label>
        <textarea v-model="bio" maxlength="500" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Affiliation</label>
        <input v-model="affiliation" type="text" maxlength="200" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">ORCID</label>
        <input v-model="orcid" type="text" maxlength="50" placeholder="0000-0000-0000-0000" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none" />
      </div>

      <button
        type="submit"
        :disabled="saving"
        class="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
      >
        {{ saving ? 'Saving...' : 'Save' }}
      </button>
    </form>
  </div>
</template>
