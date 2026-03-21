<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import type { Category } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { createPost as apiCreatePost } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { useDraft } from '@/composables/useDraft'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'

interface QuestionDraft {
  title: string
  content: string
  categoryId: string | null
  keywords: string[]
}

const { t } = useLocale()
const router = useRouter()
const toast = useToastStore()
const auth = useAuthStore()

const keywordsInput = ref('')
const categories = ref<Category[]>([])
const saving = ref(false)
const message = ref('')
const draftRestored = ref(false)

const {
  data: draftData,
  loadDraft,
  clearDraft,
} = useDraft<QuestionDraft>({
  key: `ai3l_question_draft_${auth.user?.id ?? 'anon'}`,
  defaultValue: {
    title: '',
    content: '',
    categoryId: null,
    keywords: [],
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

function discardDraft() {
  clearDraft()
  draftRestored.value = false
}

async function fetchCategories() {
  try {
    categories.value = await listCategories()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.loadCategoriesError')), 'error')
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

async function submitQuestion() {
  const titleEmpty = !title.value.trim()
  const contentEmpty = isContentEmpty(content.value)
  if (titleEmpty && contentEmpty) {
    message.value = t('qa.titleAndContentRequired')
    return
  }
  if (titleEmpty) {
    message.value = t('qa.titleRequired')
    return
  }
  if (contentEmpty) {
    message.value = t('qa.contentRequired')
    return
  }
  saving.value = true
  message.value = ''
  try {
    const payload: {
      title: string
      content: string
      type: 'question'
      category_id?: string
      keywords?: string[]
      allow_comments: boolean
    } = {
      title: title.value,
      content: content.value,
      type: 'question',
      allow_comments: true,
    }
    if (categoryId.value) payload.category_id = categoryId.value
    if (keywords.value.length) payload.keywords = keywords.value
    const data = await apiCreatePost(payload)
    clearDraft()
    router.push(`/qa/${data.id}`)
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('qa.createError'))
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
})
</script>

<template>
  <div class="max-w-3xl mx-auto py-6 px-4">
    <div class="mb-4">
      <router-link to="/qa" class="text-sm text-brand-600 hover:underline flex items-center gap-1">
        <span>&larr;</span> {{ t('qa.backToList') }}
      </router-link>
    </div>

    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('qa.askQuestion') }}</h1>

    <BaseAlert v-if="draftRestored" type="info" class="mb-4">
      {{ t('qa.draftRestored') }}
      <button class="ml-2 underline text-brand-600" @click="discardDraft">
        {{ t('qa.discardDraft') }}
      </button>
    </BaseAlert>

    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form class="space-y-4" @submit.prevent="submitQuestion">
      <BaseInput
        v-model="title"
        :label="t('qa.questionTitle')"
        :placeholder="t('qa.questionTitlePlaceholder')"
        required
      />

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{
          t('qa.categoryOptional')
        }}</label>
        <select
          v-model="categoryId"
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
        >
          <option :value="null">{{ t('qa.categoryNone') }}</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">{{ t('qa.details') }}</label>
        <TiptapEditor v-model="content" />
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">
          {{ t('qa.keywords') }} ({{ keywords.length }}/15)
        </label>
        <div class="flex gap-2 mb-2 flex-wrap">
          <BaseBadge v-for="(kw, i) in keywords" :key="i" class="gap-1">
            {{ kw }}
            <button
              type="button"
              class="text-brand-400 hover:text-brand-600"
              @click="removeKeyword(i)"
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
            :placeholder="t('qa.addKeyword')"
            @keydown.enter.prevent="addKeyword"
          />
          <BaseButton type="button" variant="secondary" @click="addKeyword">
            {{ t('qa.addKeywordBtn') }}
          </BaseButton>
        </div>
      </div>

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">
          {{ t('qa.postQuestion') }}
        </BaseButton>
        <router-link to="/qa">
          <BaseButton type="button" variant="secondary" size="lg">
            {{ t('common.cancel') }}
          </BaseButton>
        </router-link>
      </div>
    </form>
  </div>
</template>
