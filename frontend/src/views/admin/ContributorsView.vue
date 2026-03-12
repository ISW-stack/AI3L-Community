<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Contributor } from '@/types/contributor'
import {
  listContributors,
  createContributor,
  updateContributor,
  deleteContributor,
} from '@/api/contributors'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import { Plus, Pencil, Trash2 } from 'lucide-vue-next'

const { t } = useI18n()
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
    toast.show(t('admin.contributors.message.loadFailed'), 'error')
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
      toast.show(t('admin.contributors.message.updated'), 'success')
    } else {
      await createContributor({
        github_username: formGithub.value.trim(),
        display_name: formDisplayName.value.trim(),
        role: formRole.value.trim(),
        display_order: formOrder.value,
      })
      toast.show(t('admin.contributors.message.created'), 'success')
    }
    showModal.value = false
    await fetchContributors()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.contributors.message.saveFailed')), 'error')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!confirmDelete.value) return
  try {
    await deleteContributor(confirmDelete.value.id)
    toast.show(t('admin.contributors.message.deleted'), 'success')
    confirmDelete.value = null
    await fetchContributors()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.contributors.message.deleteFailed')), 'error')
  }
}

onMounted(fetchContributors)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.contributors') },
      ]"
    />
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.contributors.title') }}</h1>
      <BaseButton @click="openCreate">
        <Plus :size="18" class="mr-1.5" />
        {{ t('admin.contributors.newBtn') }}
      </BaseButton>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <EmptyState
      v-else-if="contributors.length === 0"
      :title="t('admin.contributors.emptyTitle')"
      :message="t('admin.contributors.emptyMessage')"
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
            <p class="text-xs text-muted/60">
              @{{ c.github_username }} &middot; #{{ c.display_order }}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="openEdit(c)"
            class="p-1.5 rounded text-muted hover:text-brand-600 hover:bg-brand-50 transition"
            :title="t('common.edit')"
          >
            <Pencil :size="16" />
          </button>
          <button
            @click="confirmDelete = c"
            class="p-1.5 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
            :title="t('common.delete')"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </div>
    </div>

    <!-- Create / Edit modal -->
    <BaseModal
      v-model="showModal"
      :title="
        editing
          ? t('admin.contributors.modal.editTitle')
          : t('admin.contributors.modal.createTitle')
      "
    >
      <form @submit.prevent="handleSave" class="space-y-4">
        <BaseInput
          v-model="formGithub"
          :label="t('admin.contributors.modal.githubLabel')"
          :placeholder="t('admin.contributors.modal.githubPlaceholder')"
          required
        />
        <BaseInput
          v-model="formDisplayName"
          :label="t('admin.contributors.modal.displayNameLabel')"
          :placeholder="t('admin.contributors.modal.displayNamePlaceholder')"
          required
        />
        <BaseInput
          v-model="formRole"
          :label="t('admin.contributors.modal.roleLabel')"
          :placeholder="t('admin.contributors.modal.rolePlaceholder')"
          required
        />
        <BaseInput
          v-model.number="formOrder"
          :label="t('admin.contributors.modal.orderLabel')"
          type="number"
          :placeholder="t('admin.contributors.modal.orderPlaceholder')"
        />
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="showModal = false" type="button">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            :disabled="!formGithub.trim() || !formDisplayName.trim() || !formRole.trim() || saving"
            :loading="saving"
            type="submit"
          >
            {{ editing ? t('common.save') : t('common.create') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <!-- Delete confirm modal -->
    <BaseModal v-model="showDeleteModal" :title="t('admin.contributors.deleteConfirm.title')">
      <p class="text-sm text-foreground mb-4">
        {{ t('admin.contributors.deleteConfirm.message', { name: confirmDelete?.display_name }) }}
      </p>
      <div class="flex justify-end gap-2">
        <BaseButton variant="secondary" @click="showDeleteModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="handleDelete">{{ t('common.delete') }}</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
