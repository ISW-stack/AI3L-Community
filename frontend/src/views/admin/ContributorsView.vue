<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Contributor } from '@/types/contributor'
import {
  listContributors,
  createContributor,
  updateContributor,
  deleteContributor,
} from '@/api/contributors'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { Plus, Pencil, Trash2 } from 'lucide-vue-next'

const toast = useToastStore()
const contributors = ref<Contributor[]>([])
const loading = ref(false)

// Form state
const showModal = ref(false)
const editing = ref<Contributor | null>(null)
const formGithub = ref('')
const formDisplayName = ref('')
const formRole = ref('')
const formOrder = ref(0)
const saving = ref(false)

// Delete confirm
const confirmDelete = ref<Contributor | null>(null)
const showDeleteModal = computed({
  get: () => !!confirmDelete.value,
  set: (v: boolean) => {
    if (!v) confirmDelete.value = null
  },
})

async function fetchContributors() {
  loading.value = true
  try {
    contributors.value = await listContributors()
  } catch {
    toast.show('Failed to load contributors.', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  formGithub.value = ''
  formDisplayName.value = ''
  formRole.value = ''
  formOrder.value = contributors.value.length
  showModal.value = true
}

function openEdit(c: Contributor) {
  editing.value = c
  formGithub.value = c.github_username
  formDisplayName.value = c.display_name
  formRole.value = c.role
  formOrder.value = c.display_order
  showModal.value = true
}

async function handleSave() {
  if (!formGithub.value.trim() || !formDisplayName.value.trim() || !formRole.value.trim()) return
  saving.value = true
  try {
    if (editing.value) {
      await updateContributor(editing.value.id, {
        github_username: formGithub.value.trim(),
        display_name: formDisplayName.value.trim(),
        role: formRole.value.trim(),
        display_order: formOrder.value,
      })
      toast.show('Contributor updated.', 'success')
    } else {
      await createContributor({
        github_username: formGithub.value.trim(),
        display_name: formDisplayName.value.trim(),
        role: formRole.value.trim(),
        display_order: formOrder.value,
      })
      toast.show('Contributor created.', 'success')
    }
    showModal.value = false
    await fetchContributors()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || 'Failed to save contributor.'
    toast.show(msg, 'error')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!confirmDelete.value) return
  try {
    await deleteContributor(confirmDelete.value.id)
    toast.show('Contributor deleted.', 'success')
    confirmDelete.value = null
    await fetchContributors()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || 'Failed to delete contributor.'
    toast.show(msg, 'error')
  }
}

onMounted(fetchContributors)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Contributors</h1>
      <BaseButton @click="openCreate" size="sm">
        <Plus :size="16" class="mr-1" />
        New Contributor
      </BaseButton>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <EmptyState
      v-else-if="contributors.length === 0"
      title="No Contributors"
      message="Add your first contributor to the About page."
    />

    <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
      <div
        v-for="c in contributors"
        :key="c.id"
        class="flex items-center justify-between px-5 py-4 hover:bg-surface-alt transition"
      >
        <div class="flex items-center gap-3">
          <img
            :src="c.avatar_url"
            :alt="c.display_name"
            class="w-10 h-10 rounded-full object-cover bg-muted/20"
          />
          <div>
            <p class="text-sm font-medium text-foreground">{{ c.display_name }}</p>
            <p class="text-xs text-muted">{{ c.role }}</p>
            <p class="text-xs text-muted/60">@{{ c.github_username }} &middot; #{{ c.display_order }}</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="openEdit(c)"
            class="p-1.5 rounded text-muted hover:text-brand-600 hover:bg-brand-50 transition"
            title="Edit"
          >
            <Pencil :size="16" />
          </button>
          <button
            @click="confirmDelete = c"
            class="p-1.5 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
            title="Delete"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </div>
    </div>

    <!-- Create / Edit modal -->
    <BaseModal v-model="showModal" :title="editing ? 'Edit Contributor' : 'New Contributor'">
      <form @submit.prevent="handleSave" class="space-y-4">
        <BaseInput
          v-model="formGithub"
          label="GitHub Username"
          placeholder="e.g. octocat"
          required
        />
        <BaseInput
          v-model="formDisplayName"
          label="Display Name"
          placeholder="Display name"
          required
        />
        <BaseInput v-model="formRole" label="Role" placeholder="e.g. Frontend Contributor" required />
        <BaseInput
          v-model.number="formOrder"
          label="Display Order"
          type="number"
          placeholder="0"
        />
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="showModal = false" type="button">
            Cancel
          </BaseButton>
          <BaseButton
            :disabled="!formGithub.trim() || !formDisplayName.trim() || !formRole.trim() || saving"
            :loading="saving"
            type="submit"
          >
            {{ editing ? 'Save' : 'Create' }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <!-- Delete confirm modal -->
    <BaseModal v-model="showDeleteModal" title="Delete Contributor">
      <p class="text-sm text-foreground mb-4">
        Are you sure you want to delete <strong>{{ confirmDelete?.display_name }}</strong
        >?
      </p>
      <div class="flex justify-end gap-2">
        <BaseButton variant="secondary" @click="showDeleteModal = false">Cancel</BaseButton>
        <BaseButton variant="danger" @click="handleDelete">Delete</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
