<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import { createEvent as apiCreateEvent } from '@/api/events'
import { listSigs } from '@/api/sigs'
import { useDraft } from '@/composables/useDraft'
import type { Sig } from '@/types'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

interface EventDraft {
  title: string
  content: string
  sigId: string | null
  visibility: string[]
  allowComments: boolean
}

const VISIBILITY_OPTIONS = [
  { value: 'GUEST', label: 'events.roleGuest' },
  { value: 'MEMBER', label: 'events.roleMember' },
  { value: 'ADMIN', label: 'events.roleAdmin' },
  { value: 'SUPER_ADMIN', label: 'events.roleSuperAdmin' },
]

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToastStore()

const sigs = ref<Sig[]>([])
const saving = ref(false)
const message = ref('')
const draftRestored = ref(false)
const submitted = ref(false)

const draftKey = computed(() => `ai3l_event_draft_${authStore.user?.id ?? 'anon'}`)

const {
  data: draftData,
  loadDraft,
  clearDraft,
} = useDraft<EventDraft>({
  key: () => draftKey.value,
  defaultValue: {
    title: '',
    content: '',
    sigId: null,
    visibility: ['MEMBER'],
    allowComments: true,
  },
  debounceMs: 1000,
  autoSave: true,
})

const title = computed({
  get: () => draftData.value.title ?? '',
  set: (v: string) => {
    draftData.value.title = v
  },
})

const content = computed({
  get: () => draftData.value.content ?? '',
  set: (v: string) => {
    draftData.value.content = v
  },
})

const sigId = computed({
  get: () => draftData.value.sigId ?? '',
  set: (v: string) => {
    draftData.value.sigId = v || null
  },
})

const allowComments = computed({
  get: () => draftData.value.allowComments ?? true,
  set: (v: boolean) => {
    draftData.value.allowComments = v
  },
})

function toggleVisibility(role: string) {
  const current = draftData.value.visibility ?? []
  const idx = current.indexOf(role)
  if (idx >= 0) {
    if (current.length > 1) {
      current.splice(idx, 1)
    }
  } else {
    current.push(role)
  }
  draftData.value.visibility = [...current]
}

function isVisibilityChecked(role: string): boolean {
  return (draftData.value.visibility ?? []).includes(role)
}

onBeforeRouteLeave(() => {
  if (submitted.value) return true
  if (title.value || content.value) {
    return window.confirm(t('events.unsavedWarning'))
  }
  return true
})

async function handleSubmit() {
  message.value = ''
  if (!title.value.trim()) {
    message.value = t('events.titleRequired')
    return
  }
  if (!content.value.trim()) {
    message.value = t('events.contentRequired')
    return
  }
  const vis = draftData.value.visibility ?? []
  if (vis.length === 0) {
    message.value = t('events.visibilityRequired')
    return
  }

  saving.value = true
  try {
    const event = await apiCreateEvent({
      title: title.value.trim(),
      content: content.value,
      sig_id: sigId.value || undefined,
      visibility: vis,
      allow_comments: allowComments.value,
    })
    submitted.value = true
    clearDraft()
    toast.show(t('events.createSuccess'), 'success')
    router.push(`/events/${event.id}`)
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('events.createError'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const restored = loadDraft()
  if (restored && (draftData.value.title || draftData.value.content)) {
    draftRestored.value = true
  }
  try {
    const data = await listSigs({ page: 1, page_size: 100 })
    sigs.value = data.sigs
  } catch {
    // SIG list not critical
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-6 px-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.events'), to: '/events' },
        { label: t('events.createTitle') },
      ]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('events.createTitle') }}</h1>

    <BaseAlert v-if="draftRestored" type="info" class="mb-4">
      {{ t('events.draftRestored') }}
    </BaseAlert>
    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form class="space-y-5" @submit.prevent="handleSubmit">
      <BaseInput
        v-model="title"
        :label="t('events.fieldTitle')"
        :placeholder="t('events.fieldTitlePlaceholder')"
        required
      />

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">
          {{ t('events.fieldContent') }}
        </label>
        <TiptapEditor v-model="content" />
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-2">
          {{ t('events.fieldVisibility') }}
        </label>
        <div class="flex flex-wrap gap-3">
          <label
            v-for="opt in VISIBILITY_OPTIONS"
            :key="opt.value"
            class="flex items-center gap-2 cursor-pointer"
          >
            <input
              type="checkbox"
              :checked="isVisibilityChecked(opt.value)"
              class="rounded border-border text-brand-600 focus:ring-brand-500"
              @change="toggleVisibility(opt.value)"
            />
            <span class="text-sm text-foreground">{{ t(opt.label) }}</span>
          </label>
        </div>
        <p class="text-xs text-muted mt-1">{{ t('events.visibilityHint') }}</p>
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">
          {{ t('events.fieldSig') }}
        </label>
        <select
          v-model="sigId"
          class="w-full rounded-lg border border-border bg-surface text-foreground text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300"
        >
          <option value="">{{ t('events.noSig') }}</option>
          <option v-for="sig in sigs" :key="sig.id" :value="sig.id">
            {{ sig.name }}
          </option>
        </select>
      </div>

      <label class="flex items-center gap-2 cursor-pointer">
        <input
          v-model="allowComments"
          type="checkbox"
          class="rounded border-border text-brand-600 focus:ring-brand-500"
        />
        <span class="text-sm text-foreground">{{ t('events.allowComments') }}</span>
      </label>

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">
          {{ t('events.publishBtn') }}
        </BaseButton>
        <router-link to="/events">
          <BaseButton variant="secondary" size="lg">{{ t('common.cancel') }}</BaseButton>
        </router-link>
      </div>
    </form>
  </div>
</template>
