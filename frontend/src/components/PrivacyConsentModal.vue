<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { acceptConsent as apiAcceptConsent } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import BaseButton from '@/components/base/BaseButton.vue'

const { t } = useI18n()
const emit = defineEmits<{ accepted: [] }>()
const router = useRouter()
const auth = useAuthStore()
const submitting = ref(false)
const error = ref('')
const modalRef = ref<HTMLElement | null>(null)

async function handleAcceptConsent() {
  submitting.value = true
  error.value = ''
  try {
    await apiAcceptConsent()
    emit('accepted')
  } catch {
    error.value = t('privacy.error')
  } finally {
    submitting.value = false
  }
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

function trapFocus(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    return
  }
  if (e.key === 'Tab' && modalRef.value) {
    const focusable = modalRef.value.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    )
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', trapFocus)
  nextTick(() => {
    if (modalRef.value) {
      const firstBtn = modalRef.value.querySelector<HTMLElement>('button')
      firstBtn?.focus()
    }
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', trapFocus)
})
</script>

<template>
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100] p-4"
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="consent-title"
    aria-describedby="consent-desc"
  >
    <div ref="modalRef" class="bg-surface rounded-lg shadow-xl p-6 w-full max-w-lg">
      <h2 id="consent-title" class="text-lg font-bold text-foreground mb-4">
        {{ t('privacy.title') }}
      </h2>
      <p id="consent-desc" class="text-sm text-foreground/80 leading-relaxed mb-4">
        {{ t('privacy.description') }}
      </p>
      <p class="text-sm text-muted mb-6">
        {{ t('privacy.requirement') }}
      </p>
      <div v-if="error" class="text-sm text-danger-600 mb-4">{{ error }}</div>
      <BaseButton size="full" :loading="submitting" @click="handleAcceptConsent">
        {{ t('privacy.acceptButton') }}
      </BaseButton>
      <div class="text-center mt-3">
        <button
          @click="handleLogout"
          class="text-sm text-muted hover:text-foreground underline transition"
        >
          {{ t('privacy.rejectButton') }}
        </button>
      </div>
    </div>
  </div>
</template>
