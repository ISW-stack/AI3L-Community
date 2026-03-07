<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Category } from '@/types'
import { listCategories, createCategory, updateCategory, deleteCategory } from '@/api/categories'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { Plus, Pencil, Trash2 } from 'lucide-vue-next'

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
    toast.show('Failed to load categories.', 'error')
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
      toast.show('Category updated.', 'success')
    } else {
      await createCategory({
        name: formName.value.trim(),
        description: formDescription.value.trim() || undefined,
      })
      toast.show('Category created.', 'success')
    }
    showModal.value = false
    await fetchCategories()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, 'Failed to save category.'), 'error')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!confirmDelete.value) return
  try {
    await deleteCategory(confirmDelete.value.id)
    toast.show('Category deleted.', 'success')
    confirmDelete.value = null
    await fetchCategories()
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, 'Failed to delete category.'), 'error')
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Categories</h1>
      <BaseButton @click="openCreate">
        <Plus :size="18" class="mr-1.5" />
        New Category
      </BaseButton>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <EmptyState
      v-else-if="categories.length === 0"
      title="No Categories"
      message="Create your first category to organize forum posts."
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
            class="p-1.5 rounded text-muted hover:text-brand-600 hover:bg-brand-50 transition"
            title="Edit"
          >
            <Pencil :size="16" />
          </button>
          <button
            @click="confirmDelete = cat"
            class="p-1.5 rounded text-muted hover:text-danger-600 hover:bg-danger-50 transition"
            title="Delete"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </div>
    </div>

    <!-- Create / Edit modal -->
    <BaseModal v-model="showModal" :title="editing ? 'Edit Category' : 'New Category'">
      <form @submit.prevent="handleSave" class="space-y-4">
        <BaseInput v-model="formName" label="Name" placeholder="Category name" required />
        <BaseInput
          v-model="formDescription"
          label="Description"
          placeholder="Optional description"
        />
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="showModal = false" type="button"
            >Cancel</BaseButton
          >
          <BaseButton :disabled="!formName.trim() || saving" :loading="saving" type="submit">
            {{ editing ? 'Save' : 'Create' }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <!-- Delete confirm modal -->
    <BaseModal v-model="showDeleteModal" title="Delete Category">
      <p class="text-sm text-foreground mb-4">
        Are you sure you want to delete <strong>{{ confirmDelete?.name }}</strong
        >? Posts using this category will become uncategorized.
      </p>
      <div class="flex justify-end gap-2">
        <BaseButton variant="secondary" @click="showDeleteModal = false">Cancel</BaseButton>
        <BaseButton variant="danger" @click="handleDelete">Delete</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
