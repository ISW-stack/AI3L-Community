<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Category } from '@/types'
import { listCategories, createCategory, updateCategory, deleteCategory } from '@/api/categories'
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
const categories = ref<Category[]>([])
const loading = ref(false)

// Form state
const showModal = ref(false)
const editing = ref<Category | null>(null)
const formName = ref('')
const formDescription = ref('')
const saving = ref(false)

// Delete confirm
const confirmDelete = ref<Category | null>(null)
const showDeleteModal = computed({
  get: () => !!confirmDelete.value,
  set: (v: boolean) => {
    if (!v) confirmDelete.value = null
  },
})

async function fetchCategories() {
  loading.value = true
  try {
    categories.value = await listCategories()
  } catch {
    toast.show(t('admin.categories.message.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  formName.value = ''
  formDescription.value = ''
  showModal.value = true
}

function openEdit(cat: Category) {
  editing.value = cat
  formName.value = cat.name
  formDescription.value = cat.description || ''
  showModal.value = true
}

async function handleSave() {
  if (!formName.value.trim()) return
  saving.value = true
  try {
    if (editing.value) {
      await updateCategory(editing.value.id, {
        name: formName.value.trim(),
        description: formDescription.value.trim() || undefined,
      })
      toast.show(t('admin.categories.message.updated'), 'success')
    } else {
      await createCategory({
        name: formName.value.trim(),
        description: formDescription.value.trim() || undefined,
      })
      toast.show(t('admin.categories.message.created'), 'success')
    }
    showModal.value = false
    await fetchCategories()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.categories.message.saveFailed')), 'error')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!confirmDelete.value) return
  try {
    await deleteCategory(confirmDelete.value.id)
    toast.show(t('admin.categories.message.deleted'), 'success')
    confirmDelete.value = null
    await fetchCategories()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('admin.categories.message.deleteFailed')), 'error')
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.categories') },
      ]"
    />
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.categories.title') }}</h1>
      <BaseButton @click="openCreate">
        <Plus :size="18" class="mr-1.5" />
        {{ t('admin.categories.newBtn') }}
      </BaseButton>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <EmptyState
      v-else-if="categories.length === 0"
      :title="t('admin.categories.emptyTitle')"
      :message="t('admin.categories.emptyMessage')"
    />

    <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
      <div
        v-for="cat in categories"
        :key="cat.id"
        class="flex items-center justify-between px-5 py-4 hover:bg-surface-alt transition"
      >
        <div>
          <p class="text-sm font-medium text-foreground">{{ cat.name }}</p>
          <p v-if="cat.description" class="text-xs text-muted mt-0.5">{{ cat.description }}</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="openEdit(cat)"
            class="p-2.5 sm:p-1.5 rounded text-muted hover:text-brand-600 hover:bg-brand-50 transition"
            :title="t('common.edit')"
          >
            <Pencil :size="16" />
          </button>
          <button
            @click="confirmDelete = cat"
            class="p-2.5 sm:p-1.5 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
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
        editing ? t('admin.categories.modal.editTitle') : t('admin.categories.modal.createTitle')
      "
    >
      <form @submit.prevent="handleSave" class="space-y-4">
        <BaseInput
          v-model="formName"
          :label="t('admin.categories.modal.nameLabel')"
          :placeholder="t('admin.categories.modal.namePlaceholder')"
          required
        />
        <BaseInput
          v-model="formDescription"
          :label="t('admin.categories.modal.descLabel')"
          :placeholder="t('admin.categories.modal.descPlaceholder')"
        />
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="showModal = false" type="button">{{
            t('common.cancel')
          }}</BaseButton>
          <BaseButton :disabled="!formName.trim() || saving" :loading="saving" type="submit">
            {{ editing ? t('common.save') : t('common.create') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <!-- Delete confirm modal -->
    <BaseModal v-model="showDeleteModal" :title="t('admin.categories.deleteConfirm.title')">
      <p class="text-sm text-foreground mb-4">
        {{ t('admin.categories.deleteConfirm.message', { name: confirmDelete?.name }) }}
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
