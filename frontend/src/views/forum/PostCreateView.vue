<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { Category, Sig } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { createPost as apiCreatePost } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { listMySigs } from '@/api/sigs'
import { useDraft } from '@/composables/useDraft'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'

interface PostDraft {
  title: string
  content: string
  categoryId: string | null
  keywords: string[]
  allowComments: boolean
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToastStore()

const querySigId = (route.query.sig_id as string) || null
const fromSig = computed(() => !!querySigId)

const sigId = ref<string | null>(querySigId)
const keywordsInput = ref('')
const categories = ref<Category[]>([])
const mySigs = ref<Sig[]>([])
const saving = ref(false)
const message = ref('')
const draftRestored = ref(false)

const draftKey = computed(
  () => `ai3l_post_draft_${querySigId || 'general'}_${authStore.user?.id ?? 'anon'}`,
)

const {
  data: draftData,
  loadDraft,
  clearDraft,
} = useDraft<PostDraft>({
  key: draftKey.value,
  defaultValue: {
    title: '',
    content: '',
    categoryId: null,
    keywords: [],
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

const categoryId = computed({
  get: () => draftData.value.categoryId ?? null,
  set: (v: string | null) => {
    draftData.value.categoryId = v
  },
})

const keywords = computed({
  get: () => draftData.value.keywords ?? [],
  set: (v: string[]) => {
    draftData.value.keywords = v
  },
})

const allowComments = computed({
  get: () => draftData.value.allowComments ?? true,
  set: (v: boolean) => {
    draftData.value.allowComments = v
  },
})

function discardDraft() {
  clearDraft()
  draftRestored.value = false
}

async function fetchCategories() {
  try {
    categories.value = await listCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('post.create.fetchCategoriesError')), 'error')
  }
}

async function fetchMySigs() {
  try {
    mySigs.value = await listMySigs()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('post.create.fetchSigsError')), 'error')
  }
}

function addKeyword() {
  const kw = keywordsInput.value.trim()
  if (kw && keywords.value.length < 15 && !keywords.value.includes(kw)) {
    draftData.value.keywords = [...draftData.value.keywords, kw]
    keywordsInput.value = ''
  }
}

function removeKeyword(index: number) {
  const updated = [...draftData.value.keywords]
  updated.splice(index, 1)
  draftData.value.keywords = updated
}

function isContentEmpty(html: string): boolean {
  if (!html || html === '<p></p>') return true
  if (/<(img|iframe|video|audio|embed|object|source|table)\b/i.test(html)) return false
  return !html.replace(/<[^>]*>/g, '').trim()
}

async function createPost() {
  const titleEmpty = !title.value.trim()
  const contentEmpty = isContentEmpty(content.value)
  if (titleEmpty && contentEmpty) {
    message.value = t('post.create.errorRequired')
    return
  }
  if (titleEmpty) {
    message.value = t('post.create.errorTitleRequired')
    return
  }
  if (contentEmpty) {
    message.value = t('post.create.errorContentRequired')
    return
  }
  saving.value = true
  message.value = ''
  try {
    const payload: {
      title: string
      content: string
      allow_comments: boolean
      category_id?: string
      sig_id?: string
      keywords?: string[]
    } = {
      title: title.value,
      content: content.value,
      allow_comments: allowComments.value,
    }
    if (categoryId.value) payload.category_id = categoryId.value
    if (sigId.value) payload.sig_id = sigId.value
    if (keywords.value.length) payload.keywords = keywords.value
    const data = await apiCreatePost(payload)
    clearDraft()
    router.push(`/forum/${data.id}`)
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('post.create.errorFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  const loaded = loadDraft()
  if (loaded && (draftData.value.title || draftData.value.content)) {
    draftRestored.value = true
  }
  fetchCategories()
  fetchMySigs()
})

function goBack() {
  // If Vue Router has a previous route in history, go back to it
  const hasHistory = window.history.state?.back != null
  if (hasHistory) {
    router.back()
  } else {
    // Fallback when opened directly (no browser history)
    router.push(sigId.value ? `/sigs/${sigId.value}` : '/')
  }
}

onBeforeRouteLeave(() => {
  if (title.value?.trim() || content.value?.trim()) {
    return window.confirm('You have unsaved changes. Are you sure you want to leave?')
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-6">
    <div class="mb-4">
      <button
        type="button"
        class="text-sm text-brand-600 hover:underline flex items-center gap-1"
        @click="goBack"
      >
        <span>&larr;</span> {{ t('post.create.back') }}
      </button>
    </div>

    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('post.create.title') }}</h1>

    <BaseAlert v-if="draftRestored" type="info" class="mb-4">
      {{ t('post.create.draftRestored') }}
      <button @click="discardDraft" class="ml-2 underline text-brand-600">
        {{ t('post.create.discardDraft') }}
      </button>
    </BaseAlert>

    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form @submit.prevent="createPost" class="space-y-4">
      <BaseInput
        v-model="title"
        :label="t('post.create.titleLabel')"
        :placeholder="t('post.create.titlePlaceholder')"
        required
      />

      <div v-if="!fromSig">
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('post.create.categoryLabel')
        }}</label>
        <select
          v-model="categoryId"
          name="category"
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
        >
          <option :value="null">{{ t('common.none') }}</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
      </div>

      <div v-if="!fromSig && mySigs.length > 0">
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('post.create.sigLabel')
        }}</label>
        <select
          v-model="sigId"
          name="sig"
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
        >
          <option :value="null">{{ t('common.none') }}</option>
          <option v-for="s in mySigs" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <div v-if="fromSig" class="text-sm text-muted">
        {{ t('post.create.sigPostingTo') }}
        <span class="font-medium text-foreground">{{
          mySigs.find((s) => s.id === sigId)?.name || t('common.loading')
        }}</span>
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('post.create.contentLabel')
        }}</label>
        <TiptapEditor v-model="content" />
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('post.create.keywordsLabel', { current: keywords.length, max: 15 })
        }}</label>
        <div class="flex gap-2 mb-2 flex-wrap">
          <BaseBadge v-for="(kw, i) in keywords" :key="i" class="gap-1">
            {{ kw }}
            <button
              type="button"
              @click="removeKeyword(i)"
              class="text-brand-400 hover:text-brand-600"
            >
              &times;
            </button>
          </BaseBadge>
        </div>
        <div class="flex gap-2">
          <input
            v-model="keywordsInput"
            type="text"
            name="keywords"
            maxlength="50"
            class="flex-1 px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
            :placeholder="t('post.create.keywordsPlaceholder')"
            @keydown.enter.prevent="addKeyword"
          />
          <BaseButton type="button" variant="secondary" @click="addKeyword">{{
            t('post.create.keywordsAdd')
          }}</BaseButton>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <input
          id="allow-comments"
          v-model="allowComments"
          type="checkbox"
          class="rounded border-border"
        />
        <label for="allow-comments" class="text-sm text-foreground">{{
          t('post.create.allowComments')
        }}</label>
      </div>

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">{{
          t('post.create.publish')
        }}</BaseButton>
        <router-link :to="sigId ? `/sigs/${sigId}` : '/forum'"
          ><BaseButton type="button" variant="secondary" size="lg">{{
            t('common.cancel')
          }}</BaseButton></router-link
        >
      </div>
    </form>
  </div>
</template>
