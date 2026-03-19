<script setup lang="ts">
import { ref } from 'vue'
import { Eye, EyeOff, Copy, Check } from 'lucide-vue-next'
import { useLocale } from '@/composables/useLocale'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'

const { t } = useLocale()

defineProps<{
  passwordMessage: string
  passwordError: boolean
  changingPassword: boolean
  generatedCode: string
  generatingCode: boolean
  codeCopied: boolean
}>()

const currentPassword = defineModel<string>('currentPassword', { required: true })
const newPassword = defineModel<string>('newPassword', { required: true })
const confirmPassword = defineModel<string>('confirmPassword', { required: true })

const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

const emit = defineEmits<{
  'change-password': []
  'generate-invite-code': []
  'copy-invite-code': []
}>()

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
  <div>
    <!-- Change Password -->
    <h2 class="text-xl font-bold text-foreground mb-4">
    {{ t('profile.security.changePassword.title') }}
  </h2>

  <BaseAlert v-if="passwordMessage" :type="passwordError ? 'error' : 'success'" class="mb-4">{{
    passwordMessage
  }}</BaseAlert>

  <BaseCard padding="lg" class="mb-8">
    <form @submit.prevent="emit('change-password')" class="space-y-4">
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
      <BaseButton :loading="generatingCode" @click="emit('generate-invite-code')">
        {{ t('profile.security.inviteCodes.generateBtn') }}
      </BaseButton>
      <div v-if="generatedCode" class="flex items-center gap-2">
        <BaseInput :model-value="generatedCode" disabled class="flex-1" />
        <BaseButton variant="secondary" size="sm" @click="emit('copy-invite-code')">
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
</template>
