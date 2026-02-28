<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/composables/api'

const router = useRouter()

interface Category {
  id: string
  name: string
}

const title = ref('')
const content = ref('')
const categoryId = ref<string | null>(null)
const keywordsInput = ref('')
const keywords = ref<string[]>([])
const allowComments = ref(true)
const categories = ref<Category[]>([])
const saving = ref(false)
const message = ref('')

async function fetchCategories() {
  try {
    const { data } = await api.get('/categories')
    categories.value = data.categories
  } catch {
    // silent
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
    const body: Record<string, unknown> = {
      title: title.value,
      content: content.value,
      allow_comments: allowComments.value,
    }
    if (categoryId.value) body.category_id = categoryId.value
    if (keywords.value.length) body.keywords = keywords.value

    const { data } = await api.post('/posts', body)
    router.push(`/forum/${data.id}`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.value = err.response?.data?.detail || 'Failed to create post.'
  } finally {
    saving.value = false
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="max-w-3xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Create Post</h1>

    <div v-if="message" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
      {{ message }}
    </div>

    <form @submit.prevent="createPost" class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          v-model="title"
          type="text"
          maxlength="300"
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          placeholder="Post title"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Category</label>
        <select
          v-model="categoryId"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg"
        >
          <option :value="null">None</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Content</label>
        <textarea
          v-model="content"
          rows="12"
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none font-mono text-sm"
          placeholder="Write your post content here. HTML is supported."
        ></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          Keywords ({{ keywords.length }}/15)
        </label>
        <div class="flex gap-2 mb-2 flex-wrap">
          <span
            v-for="(kw, i) in keywords"
            :key="i"
            class="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full"
          >
            {{ kw }}
            <button type="button" @click="removeKeyword(i)" class="text-blue-400 hover:text-blue-600">&times;</button>
          </span>
        </div>
        <div class="flex gap-2">
          <input
            v-model="keywordsInput"
            type="text"
            maxlength="50"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
            placeholder="Add a keyword and press Enter"
            @keydown.enter.prevent="addKeyword"
          />
          <button
            type="button"
            @click="addKeyword"
            class="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200"
          >
            Add
          </button>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <input
          id="allow-comments"
          v-model="allowComments"
          type="checkbox"
          class="rounded border-gray-300"
        />
        <label for="allow-comments" class="text-sm text-gray-700">Allow comments</label>
      </div>

      <div class="flex gap-3 pt-2">
        <button
          type="submit"
          :disabled="saving"
          class="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {{ saving ? 'Publishing...' : 'Publish' }}
        </button>
        <router-link
          to="/forum"
          class="px-6 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition"
        >
          Cancel
        </router-link>
      </div>
    </form>
  </div>
</template>
