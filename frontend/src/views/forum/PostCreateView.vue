<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { Category, Sig } from '@/types'
import { createPost as apiCreatePost } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { listMySigs } from '@/api/sigs'
import TiptapEditor from '@/components/TiptapEditor.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'

const router = useRouter()

const title = ref('')
const content = ref('')
const categoryId = ref<string | null>(null)
const sigId = ref<string | null>(null)
const keywordsInput = ref('')
const keywords = ref<string[]>([])
const allowComments = ref(true)
const categories = ref<Category[]>([])
const mySigs = ref<Sig[]>([])
const saving = ref(false)
const message = ref('')

async function fetchCategories() {
  try {
    categories.value = await listCategories()
  } catch {
    /* silent */
  }
}

async function fetchMySigs() {
  try {
    mySigs.value = await listMySigs()
  } catch {
    /* silent */
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
    message.value = 'Title and content are required.'
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
    router.push(`/forum/${data.id}`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.value = err.response?.data?.detail || 'Failed to create post.'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchCategories()
  fetchMySigs()
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-6">Create Post</h1>

    <BaseAlert v-if="message" type="error" class="mb-4">{{ message }}</BaseAlert>

    <form @submit.prevent="createPost" class="space-y-4">
      <BaseInput v-model="title" label="Title" placeholder="Post title" required />

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">Category</label>
        <select
          v-model="categoryId"
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
        >
          <option :value="null">None</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
      </div>

      <div v-if="mySigs.length > 0">
        <label class="block text-sm font-medium text-foreground mb-1">SIG (optional)</label>
        <select
          v-model="sigId"
          class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-foreground"
        >
          <option :value="null">None</option>
          <option v-for="s in mySigs" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1">Content</label>
        <TiptapEditor v-model="content" />
      </div>

      <div>
        <label class="block text-sm font-medium text-foreground mb-1"
          >Keywords ({{ keywords.length }}/15)</label
        >
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
            placeholder="Add a keyword and press Enter"
            @keydown.enter.prevent="addKeyword"
          />
          <BaseButton type="button" variant="secondary" @click="addKeyword">Add</BaseButton>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <input
          id="allow-comments"
          v-model="allowComments"
          type="checkbox"
          class="rounded border-border"
        />
        <label for="allow-comments" class="text-sm text-foreground">Allow comments</label>
      </div>

      <div class="flex gap-3 pt-2">
        <BaseButton type="submit" size="lg" :loading="saving">Publish</BaseButton>
        <router-link to="/forum"
          ><BaseButton type="button" variant="secondary" size="lg">Cancel</BaseButton></router-link
        >
      </div>
    </form>
  </div>
</template>
