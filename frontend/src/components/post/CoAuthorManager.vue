<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { CoAuthor } from '@/types/coauthor'
import {
  listCoAuthors,
  inviteCoAuthor,
  addExternalCoAuthor,
  removeCoAuthor,
  searchUsers,
} from '@/api/coauthors'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import { UserPlus, X, Users } from 'lucide-vue-next'

const MAX_CO_AUTHORS = 10

const props = defineProps<{
  postId: string
}>()

const toast = useToastStore()

const coAuthors = ref<CoAuthor[]>([])
const loading = ref(false)
const error = ref('')

// Internal user search
const searchQuery = ref('')
const searchResults = ref<Array<{ id: string; display_name: string; avatar_url: string | null }>>([])
const searchLoading = ref(false)
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// External co-author form
const showExternalForm = ref(false)
const externalName = ref('')
const externalAffiliation = ref('')
const externalOrcid = ref('')
const addingExternal = ref(false)

const canAddMore = computed(() => coAuthors.value.length < MAX_CO_AUTHORS)

async function fetchCoAuthors() {
  loading.value = true
  try {
    const res = await listCoAuthors(props.postId)
    coAuthors.value = res.data.co_authors
  } catch (e: unknown) {
    error.value = getErrorMessage(e, 'Failed to load co-authors.')
  } finally {
    loading.value = false
  }
}

function onSearchInput() {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  searchLoading.value = true
  searchDebounceTimer = setTimeout(async () => {
    try {
      const res = await searchUsers(searchQuery.value.trim())
      searchResults.value = res.data as Array<{
        id: string
        display_name: string
        avatar_url: string | null
      }>
    } catch {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }, 300)
}

async function handleInvite(userId: string, displayName: string) {
  if (!canAddMore.value) {
    toast.show('Maximum of 10 co-authors reached.', 'warning')
    return
  }
  try {
    await inviteCoAuthor(props.postId, { user_id: userId, display_name: displayName })
    toast.show(`Invited ${displayName} as co-author.`, 'success')
    searchQuery.value = ''
    searchResults.value = []
    await fetchCoAuthors()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to invite co-author.'), 'error')
  }
}

async function handleAddExternal() {
  if (!externalName.value.trim()) return
  if (!canAddMore.value) {
    toast.show('Maximum of 10 co-authors reached.', 'warning')
    return
  }
  addingExternal.value = true
  try {
    const payload: { display_name: string; affiliation?: string; orcid?: string } = {
      display_name: externalName.value.trim(),
    }
    if (externalAffiliation.value.trim()) payload.affiliation = externalAffiliation.value.trim()
    if (externalOrcid.value.trim()) payload.orcid = externalOrcid.value.trim()
    await addExternalCoAuthor(props.postId, payload)
    toast.show('External co-author added.', 'success')
    externalName.value = ''
    externalAffiliation.value = ''
    externalOrcid.value = ''
    showExternalForm.value = false
    await fetchCoAuthors()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to add external co-author.'), 'error')
  } finally {
    addingExternal.value = false
  }
}

async function handleRemove(coAuthorId: string) {
  try {
    await removeCoAuthor(props.postId, coAuthorId)
    toast.show('Co-author removed.', 'success')
    await fetchCoAuthors()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to remove co-author.'), 'error')
  }
}

function toggleExternalForm() {
  showExternalForm.value = !showExternalForm.value
}

function statusVariant(status: string): 'default' | 'neutral' {
  if (status === 'ACCEPTED') return 'default'
  return 'neutral'
}

onMounted(fetchCoAuthors)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <Users class="w-4 h-4 text-muted" />
      <h3 class="text-sm font-semibold text-foreground">
        Co-Authors ({{ coAuthors.length }}/{{ MAX_CO_AUTHORS }})
      </h3>
    </div>

    <BaseAlert v-if="error" type="error">{{ error }}</BaseAlert>

    <!-- Current co-authors list -->
    <div v-if="coAuthors.length > 0" class="space-y-2">
      <div
        v-for="ca in coAuthors"
        :key="ca.id"
        class="flex items-center gap-2 py-1.5 px-2 rounded-lg bg-surface-alt"
      >
        <BaseAvatar :src="ca.avatar_url" :name="ca.display_name" size="sm" />
        <div class="flex-1 min-w-0">
          <span class="text-sm font-medium text-foreground truncate block">{{ ca.display_name }}</span>
          <span v-if="ca.affiliation" class="text-xs text-muted truncate block">{{ ca.affiliation }}</span>
        </div>
        <BaseBadge :variant="statusVariant(ca.status)" class="!text-[10px] !px-1.5 !py-0">
          {{ ca.status === 'ACCEPTED' ? 'Accepted' : ca.status === 'PENDING' ? 'Pending' : 'Rejected' }}
        </BaseBadge>
        <button
          type="button"
          class="p-1 text-muted hover:text-danger-600 transition"
          aria-label="Remove co-author"
          @click="handleRemove(ca.id)"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-sm text-muted">Loading co-authors...</div>

    <!-- Invite internal user -->
    <div v-if="canAddMore" class="space-y-2">
      <label class="block text-xs font-medium text-muted">Search and invite a user</label>
      <div class="relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search by name..."
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
          @input="onSearchInput"
        />
      </div>
      <div
        v-if="searchResults.length > 0"
        class="border border-border rounded-lg divide-y divide-border max-h-40 overflow-y-auto"
      >
        <button
          v-for="user in searchResults"
          :key="user.id"
          type="button"
          class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-alt transition text-sm"
          @click="handleInvite(user.id, user.display_name)"
        >
          <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="sm" />
          <span class="text-foreground">{{ user.display_name }}</span>
          <UserPlus class="w-3.5 h-3.5 text-brand-600 ml-auto" />
        </button>
      </div>
      <div v-if="searchLoading" class="text-xs text-muted">Searching...</div>
    </div>

    <!-- External co-author toggle -->
    <div v-if="canAddMore">
      <button
        type="button"
        class="text-sm text-brand-600 hover:text-brand-700 hover:underline"
        @click="toggleExternalForm"
      >
        {{ showExternalForm ? 'Cancel' : '+ Add external co-author' }}
      </button>

      <div v-if="showExternalForm" class="mt-2 space-y-2 p-3 border border-border rounded-lg">
        <BaseInput
          v-model="externalName"
          label="Name"
          placeholder="Full name"
          required
        />
        <BaseInput
          v-model="externalAffiliation"
          label="Affiliation"
          placeholder="University or organization"
        />
        <BaseInput
          v-model="externalOrcid"
          label="ORCID"
          placeholder="0000-0000-0000-0000"
        />
        <BaseButton
          size="sm"
          :loading="addingExternal"
          :disabled="!externalName.trim()"
          @click="handleAddExternal"
        >
          Add External Co-Author
        </BaseButton>
      </div>
    </div>
  </div>
</template>
