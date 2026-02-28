<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/composables/api'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/auth'

interface Sig {
  id: string
  name: string
  description: string | null
  created_by: string
  creator_display_name: string | null
  member_count: number
  created_at: string
}

interface SigMember {
  id: string
  sig_id: string
  user_id: string
  role: string
  display_name: string
  username: string
  created_at: string
}

interface PostAuthor {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
}

interface Post {
  id: string
  title: string
  content: string
  author: PostAuthor
  category_id: string | null
  category_name: string | null
  keywords: string[] | null
  allow_comments: boolean
  version: number
  comment_count: number
  created_at: string
  updated_at: string
}

interface SigForm {
  id: string
  sig_id: string
  title: string
  description: string | null
  deadline: string | null
  max_respondents: number | null
  response_count: number
  is_active: boolean
  created_by_name: string
  created_at: string
  user_is_sig_admin: boolean
}

const route = useRoute()
const auth = useAuthStore()
const sigId = computed(() => route.params.id as string)

const sig = ref<Sig | null>(null)
const members = ref<SigMember[]>([])
const membersTotal = ref(0)
const posts = ref<Post[]>([])
const postsTotal = ref(0)
const forms = ref<SigForm[]>([])
const formsTotal = ref(0)
const loading = ref(true)
const activeTab = ref<'posts' | 'members' | 'forms'>('posts')

const canCreateForm = computed(() => {
  if (auth.isAdmin) return true
  if (forms.value.length > 0 && forms.value[0].user_is_sig_admin) return true
  return false
})

async function fetchSig() {
  loading.value = true
  try {
    const { data } = await api.get(`/sigs/${sigId.value}`)
    sig.value = data
  } catch {
    sig.value = null
  } finally {
    loading.value = false
  }
}

async function fetchPosts() {
  try {
    const { data } = await api.get(`/sigs/${sigId.value}/posts`)
    posts.value = data.posts
    postsTotal.value = data.total
  } catch {
    // silent
  }
}

async function fetchMembers() {
  try {
    const { data } = await api.get(`/sigs/${sigId.value}/members`)
    members.value = data.members
    membersTotal.value = data.total
  } catch {
    // silent
  }
}

async function fetchForms() {
  try {
    const { data } = await api.get(`/sigs/${sigId.value}/forms`)
    forms.value = data.forms
    formsTotal.value = data.total
  } catch {
    // silent
  }
}

function switchTab(tab: 'posts' | 'members' | 'forms') {
  activeTab.value = tab
  if (tab === 'posts') fetchPosts()
  else if (tab === 'members') fetchMembers()
  else fetchForms()
}

onMounted(() => {
  fetchSig()
  fetchPosts()
})
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <div class="mb-6">
      <router-link to="/sigs" class="text-sm text-blue-600 hover:underline">&larr; All SIGs</router-link>
    </div>

    <div v-if="loading" class="text-center text-gray-400 py-12">Loading...</div>

    <div v-else-if="!sig" class="text-center py-12">
      <p class="text-gray-500 mb-4">SIG not found.</p>
      <router-link to="/sigs" class="text-blue-600 hover:underline">Back to SIGs</router-link>
    </div>

    <template v-else>
      <div class="bg-white rounded-xl shadow p-6 mb-6">
        <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ sig.name }}</h1>
        <p v-if="sig.description" class="text-sm text-gray-600 mb-3" v-html="DOMPurify.sanitize(sig.description)"></p>
        <div class="flex items-center gap-4 text-xs text-gray-400">
          <span>Created by {{ sig.creator_display_name || 'Unknown' }}</span>
          <span>{{ sig.member_count }} member(s)</span>
          <span>{{ new Date(sig.created_at).toLocaleDateString() }}</span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-4">
        <button
          @click="switchTab('posts')"
          class="px-4 py-2 text-sm rounded-lg transition"
          :class="activeTab === 'posts' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        >
          Posts ({{ postsTotal }})
        </button>
        <button
          @click="switchTab('members')"
          class="px-4 py-2 text-sm rounded-lg transition"
          :class="activeTab === 'members' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        >
          Members ({{ membersTotal }})
        </button>
        <button
          @click="switchTab('forms')"
          class="px-4 py-2 text-sm rounded-lg transition"
          :class="activeTab === 'forms' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        >
          Forms ({{ formsTotal }})
        </button>
      </div>

      <!-- Posts tab -->
      <div v-if="activeTab === 'posts'">
        <div v-if="posts.length === 0" class="text-center text-gray-400 py-8 text-sm">
          No posts in this SIG yet.
        </div>
        <div v-else class="space-y-3">
          <router-link
            v-for="p in posts"
            :key="p.id"
            :to="`/forum/${p.id}`"
            class="block bg-white rounded-xl shadow p-4 hover:shadow-md transition"
          >
            <h3 class="font-semibold text-gray-900 mb-1">{{ p.title }}</h3>
            <div class="flex items-center gap-3 text-xs text-gray-400">
              <span>{{ p.author.display_name }}</span>
              <span>{{ new Date(p.created_at).toLocaleString() }}</span>
              <span>{{ p.comment_count }} comments</span>
            </div>
          </router-link>
        </div>
      </div>

      <!-- Members tab -->
      <div v-if="activeTab === 'members'">
        <div v-if="members.length === 0" class="text-center text-gray-400 py-8 text-sm">
          No members yet.
        </div>
        <div v-else class="bg-white rounded-xl shadow overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 border-b">
              <tr>
                <th class="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                <th class="text-left px-4 py-3 font-medium text-gray-600">Username</th>
                <th class="text-left px-4 py-3 font-medium text-gray-600">Role</th>
                <th class="text-left px-4 py-3 font-medium text-gray-600">Joined</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in members" :key="m.id" class="border-b last:border-0 hover:bg-gray-50">
                <td class="px-4 py-3 text-gray-900">{{ m.display_name }}</td>
                <td class="px-4 py-3 text-gray-500">{{ m.username }}</td>
                <td class="px-4 py-3">
                  <span
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="{
                      'bg-orange-100 text-orange-700': m.role === 'ADMIN',
                      'bg-purple-100 text-purple-700': m.role === 'SUB_ADMIN',
                      'bg-blue-100 text-blue-700': m.role === 'MEMBER',
                    }"
                  >
                    {{ m.role }}
                  </span>
                </td>
                <td class="px-4 py-3 text-gray-400 text-xs">
                  {{ new Date(m.created_at).toLocaleDateString() }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Forms tab -->
      <div v-if="activeTab === 'forms'">
        <div v-if="canCreateForm" class="mb-4">
          <router-link :to="`/sigs/${sigId}/forms/new`"
            class="inline-block text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition">
            + Create Form
          </router-link>
        </div>
        <div v-if="forms.length === 0" class="text-center text-gray-400 py-8 text-sm">
          No forms in this SIG yet.
        </div>
        <div v-else class="grid gap-4 sm:grid-cols-2">
          <router-link
            v-for="f in forms"
            :key="f.id"
            :to="`/forms/${f.id}`"
            class="block bg-white rounded-xl shadow p-4 hover:shadow-md transition"
          >
            <div class="flex items-start justify-between mb-2">
              <h3 class="font-semibold text-gray-900">{{ f.title }}</h3>
              <span
                class="text-xs px-2 py-0.5 rounded-full shrink-0 ml-2"
                :class="f.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
              >
                {{ f.is_active ? 'Active' : 'Closed' }}
              </span>
            </div>
            <p v-if="f.description" class="text-xs text-gray-500 mb-2 line-clamp-2">{{ f.description }}</p>
            <div class="flex items-center gap-3 text-xs text-gray-400">
              <span>{{ f.response_count }} response(s)</span>
              <span v-if="f.deadline">Deadline: {{ new Date(f.deadline).toLocaleDateString() }}</span>
              <span>By {{ f.created_by_name }}</span>
            </div>
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>
