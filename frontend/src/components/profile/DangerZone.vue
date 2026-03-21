<script setup lang="ts">
import { ref, watch } from 'vue'
import { useLocale } from '@/composables/useLocale'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const { t } = useLocale()

defineProps<{
  deletingAccount: boolean
}>()

const emit = defineEmits<{
  'delete-account': []
}>()

const showDeleteConfirm = ref(false)
const deleteConfirmText = ref('')

function openDeleteConfirm() {
  showDeleteConfirm.value = true
}

function closeDeleteConfirm() {
  showDeleteConfirm.value = false
}

// Clear delete confirmation text when modal is closed
watch(showDeleteConfirm, (open) => {
  if (!open) {
    deleteConfirmText.value = ''
  }
})

function handleConfirmDelete() {
  emit('delete-account')
}

defineExpose({
  showDeleteConfirm,
  deleteConfirmText,
  closeDeleteConfirm,
})
</script>

<template>
  <div>
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
          @click="handleConfirmDelete"
          >{{ t('profile.dangerZone.deleteConfirm.confirmBtn') }}</BaseButton
        >
      </template>
    </BaseModal>
  </div>
</template>
