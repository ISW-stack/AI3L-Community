<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/composables/api'
import DOMPurify from 'dompurify'

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

const route = useRoute()
const sigId = computed(() => route.params.id as string)

const sig = ref<Sig | null>(null)
const members = ref<SigMember[]>([])
const membersTotal = ref(0)
const posts = ref<Post[]>([])
const postsTotal = ref(0)
const loading = ref(true)
const activeTab = ref<'posts' | 'members'>('posts')

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

function switchTab(tab: 'posts' | 'members') {
  activeTab.value = tab
  if (tab === 'posts') fetchPosts()
  else fetchMembers()
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
    </template>
  </div>
</template>
