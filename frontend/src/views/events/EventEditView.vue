<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import { getEvent, updateEvent as apiUpdateEvent } from '@/api/events'
import { listSigs } from '@/api/sigs'
import type { Event, Sig } from '@/types'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const VISIBILITY_OPTIONS = [
  { value: 'GUEST', label: 'events.roleGuest' },
  { value: 'MEMBER', label: 'events.roleMember' },
  { value: 'ADMIN', label: 'events.roleAdmin' },
]

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const eventId = computed(() => route.params.id as string)
const event = ref<Event | null>(null)
const sigs = ref<Sig[]>([])
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const submitted = ref(false)

const title = ref('')
const content = ref('')
const sigId = ref('')
const visibility = ref<string[]>([])
const allowComments = ref(true)
const version = ref(1)

function toggleVisibility(role: string) {
  const idx = visibility.value.indexOf(role)
  if (idx >= 0) {
    if (visibility.value.length > 1) {
      visibility.value.splice(idx, 1)
    }
  } else {
    visibility.value.push(role)
  }
}

function isVisibilityChecked(role: string): boolean {
  return visibility.value.includes(role)
}

onBeforeRouteLeave(() => {
  if (submitted.value) return true
  if (event.value && (title.value !== event.value.title || content.value !== event.value.content)) {
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
  if (visibility.value.length === 0) {
    message.value = t('events.visibilityRequired')
    return
  }

  saving.value = true
  try {
    await apiUpdateEvent(eventId.value, {
      title: title.value.trim(),
      content: content.value,
      sig_id: sigId.value || null,
      visibility: visibility.value,
      allow_comments: allowComments.value,
      version: version.value,
    })
    submitted.value = true
    toast.show(t('events.updateSuccess'), 'success')
    router.push(`/events/${eventId.value}`)
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('events.updateError'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const [ev, sigData] = await Promise.all([
      getEvent(eventId.value),
      listSigs({ page: 1, page_size: 100 }),
    ])
    event.value = ev
    sigs.value = sigData.sigs

    // Check permission
    if (ev.author.id !== auth.user?.id && !auth.isSuperAdmin) {
      toast.show(t('events.noEditPermission'), 'error')
      router.push(`/events/${eventId.value}`)
      return
    }

    title.value = ev.title
    content.value = ev.content
    sigId.value = ev.sig_id || ''
    visibility.value = [...ev.visibility]
    allowComments.value = ev.allow_comments
    version.value = ev.version
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('events.fetchError')), 'error')
    router.push('/events')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-6 px-4">
    <SkeletonLoader v-if="loading" :lines="6" variant="card" />

    <template v-else-if="event">
      <BaseBreadcrumb
        :items="[
          { label: t('breadcrumb.home'), to: '/' },
          { label: t('breadcrumb.events'), to: '/events' },
          { label: event.title, to: `/events/${eventId}` },
          { label: t('events.editTitle') },
        ]"
      />
      <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('events.editTitle') }}</h1>

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
            {{ t('events.saveBtn') }}
          </BaseButton>
          <router-link :to="`/events/${eventId}`">
            <BaseButton variant="secondary" size="lg">{{ t('common.cancel') }}</BaseButton>
          </router-link>
        </div>
      </form>
    </template>
  </div>
</template>
