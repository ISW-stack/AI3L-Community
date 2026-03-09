<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useToastStore } from '@/stores/toast'
import type { Category, Sig } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { createPost as apiCreatePost } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { listMySigs } from '@/api/sigs'
import TiptapEditor from '@/components/TiptapEditor.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const querySigId = (route.query.sig_id as string) || null
const fromSig = computed(() => !!querySigId)

const title = ref('')
const content = ref('')
const categoryId = ref<string | null>(null)
const sigId = ref<string | null>(querySigId)
const keywordsInput = ref('')
const keywords = ref<string[]>([])
const allowComments = ref(true)
const categories = ref<Category[]>([])
const mySigs = ref<Sig[]>([])
const saving = ref(false)
const message = ref('')
const draftRestored = ref(false)

const DRAFT_KEY = 'ai3l_post_draft'

function saveDraft() {
  const draft = {
    title: title.value,
    content: content.value,
    categoryId: categoryId.value,
    keywords: keywords.value,
    allowComments: allowComments.value,
  }
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
}

function loadDraft() {
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return
  try {
    const draft = JSON.parse(raw)
    if (draft.title || draft.content) {
      title.value = draft.title || ''
      content.value = draft.content || ''
      categoryId.value = draft.categoryId ?? null
      keywords.value = draft.keywords || []
      allowComments.value = draft.allowComments ?? true
      draftRestored.value = true
    }
  } catch {
    localStorage.removeItem(DRAFT_KEY)
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
}

function discardDraft() {
  clearDraft()
  title.value = ''
  content.value = ''
  keywords.value = []
  categoryId.value = null
  allowComments.value = true
  draftRestored.value = false
}

let draftTimer: ReturnType<typeof setTimeout> | null = null
function debouncedSaveDraft() {
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(saveDraft, 1000)
}

watch([title, content, categoryId, keywords, allowComments], debouncedSaveDraft, { deep: true })

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
    keywords.value.push(kw)
    keywordsInput.value = ''
  }
}

function removeKeyword(index: number) {
  keywords.value.splice(index, 1)
}

async function createPost() {
  if (!title.value.trim() || !content.value.trim()) {
    message.value = t('post.create.errorRequired')
    return
  }
  saving.value = true
  message.value = ''
  try {
    const payload: any = {
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
  loadDraft()
  fetchCategories()
  fetchMySigs()
})

onUnmounted(() => {
  if (draftTimer) clearTimeout(draftTimer)
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-6">
    <div class="mb-4">
      <router-link
        :to="fromSig ? `/sigs/${sigId}` : '/forum'"
        class="text-sm text-brand-600 hover:underline flex items-center gap-1"
      >
        <span>&larr;</span> {{ t('post.create.back') }}
      </router-link>
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
        <router-link :to="fromSig ? `/sigs/${sigId}` : '/forum'"
          ><BaseButton type="button" variant="secondary" size="lg">{{
            t('common.cancel')
          }}</BaseButton></router-link
        >
      </div>
    </form>
  </div>
</template>
