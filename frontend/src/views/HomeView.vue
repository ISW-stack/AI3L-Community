<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { listPosts } from '@/api/posts'
import { applyForMembership } from '@/api/users'
import type { Post } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { KeyRound, PenTool, GraduationCap } from 'lucide-vue-next'

const auth = useAuthStore()
const notifStore = useNotificationStore()
const toast = useToastStore()

const recentPosts = ref<Post[]>([])
const loadingPosts = ref(false)

// Guest membership application
const applicationDesc = ref('')
const applyLoading = ref(false)
const applicationSent = ref(false)

async function submitApplication() {
  if (!applicationDesc.value.trim()) return
  applyLoading.value = true
  try {
    await applyForMembership(applicationDesc.value.trim())
    applicationSent.value = true
    toast.show('Application submitted successfully!', 'success')
  } catch (err: any) {
    const msg = err?.response?.data?.detail || 'Failed to submit application.'
    toast.show(msg, 'error')
  } finally {
    applyLoading.value = false
  }
}

async function fetchRecentPosts() {
  if (!auth.isAuthenticated) return
  loadingPosts.value = true
  try {
    const data = await listPosts({ page: 1, page_size: 5, sort: 'newest' })
    recentPosts.value = data.posts
  } catch {
    /* silent */
  } finally {
    loadingPosts.value = false
  }
}

onMounted(() => {
  if (auth.isAuthenticated) {
    fetchRecentPosts()
    notifStore.fetchUnreadCount()
  }
})
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <!-- Authenticated view -->
    <div v-if="auth.isAuthenticated" class="space-y-6">
      <BaseCard padding="lg">
        <h2 class="text-xl font-semibold text-foreground mb-2">
          {{ auth.isGuest ? 'Welcome, Guest' : `Welcome back, ${auth.user?.display_name}` }}
        </h2>
        <p class="text-muted">Explore discussions and share your research.</p>
        <div class="mt-4 flex flex-wrap gap-3">
          <router-link to="/forum">
            <BaseButton>Browse Forum</BaseButton>
          </router-link>
          <router-link to="/sigs">
            <BaseButton variant="secondary">My SIGs</BaseButton>
          </router-link>
        </div>
      </BaseCard>

      <BaseAlert v-if="auth.isGuest" type="warning">
        You are browsing as a guest. Your session lasts 45 minutes.
        <router-link to="/register" class="font-medium underline">Sign up</router-link>
        for full access.
      </BaseAlert>

      <!-- Guest membership application -->
      <BaseCard v-if="auth.isGuest" padding="lg">
        <h3 class="text-lg font-semibold text-foreground mb-2">Apply for Membership</h3>
        <div v-if="applicationSent" class="text-sm text-success-600">
          Your application has been submitted. An admin will review it shortly.
        </div>
        <div v-else>
          <p class="text-sm text-muted mb-3">
            Tell us a bit about yourself and why you'd like to join the community.
          </p>
          <BaseTextarea
            v-model="applicationDesc"
            placeholder="Describe your background and research interests..."
            :rows="3"
            class="mb-3"
          />
          <BaseButton
            :disabled="!applicationDesc.trim() || applyLoading"
            :loading="applyLoading"
            @click="submitApplication"
          >
            Submit Application
          </BaseButton>
        </div>
      </BaseCard>

      <!-- Unread notifications summary -->
      <BaseCard v-if="notifStore.unreadCount > 0" padding="md" class="border-l-4 border-brand-500">
        <div class="flex items-center justify-between">
          <p class="text-sm text-foreground">
            You have <strong>{{ notifStore.unreadCount }}</strong> unread notification(s).
          </p>
          <router-link to="/notifications">
            <BaseButton size="sm" variant="ghost">View</BaseButton>
          </router-link>
        </div>
      </BaseCard>

      <!-- Recent posts -->
      <BaseCard padding="lg">
        <h3 class="text-lg font-semibold text-foreground mb-3">Recent Posts</h3>
        <SkeletonLoader v-if="loadingPosts" :lines="3" variant="list" />
        <div v-else-if="recentPosts.length === 0" class="text-sm text-muted">
          No posts yet. Be the first to start a discussion!
        </div>
        <div v-else class="divide-y divide-border">
          <router-link
            v-for="p in recentPosts"
            :key="p.id"
            :to="`/forum/${p.id}`"
            class="block py-3 hover:bg-surface-alt -mx-4 px-4 rounded transition"
          >
            <p class="text-sm font-medium text-foreground">{{ p.title }}</p>
            <div class="flex items-center gap-3 text-xs text-muted mt-1">
              <span>{{ p.author.display_name }}</span>
              <span>{{ new Date(p.created_at).toLocaleDateString() }}</span>
              <span>{{ p.comment_count }} comments</span>
            </div>
          </router-link>
        </div>
      </BaseCard>
    </div>

    <!-- Unauthenticated view -->
    <div v-else>
      <!-- Hero Section -->
      <div
        class="bg-gradient-to-br from-brand-900 to-brand-700 rounded-lg p-8 sm:p-12 text-white text-center mb-8"
      >
        <h1 class="text-3xl sm:text-4xl font-bold mb-3">AI3L Community</h1>
        <p class="text-brand-200 text-lg mb-6">
          AI in Language Learning and Literacy &mdash; Academic Exchange Platform
        </p>
        <div class="flex flex-wrap items-center justify-center gap-3">
          <router-link to="/register">
            <button
              class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg bg-white text-brand-900 hover:bg-brand-50 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Get Started
            </button>
          </router-link>
          <router-link to="/guest">
            <button
              class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg text-white/90 hover:text-white hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Browse as Guest
            </button>
          </router-link>
        </div>
      </div>

      <!-- Feature cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <router-link to="/login" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <KeyRound class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Log In</h3>
            <p class="text-sm text-muted mt-1">Sign in with your credentials</p>
          </BaseCard>
        </router-link>

        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <PenTool class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Sign Up</h3>
            <p class="text-sm text-muted mt-1">Create a new account</p>
          </BaseCard>
        </router-link>

        <router-link to="/guest" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <GraduationCap class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">Guest Access</h3>
            <p class="text-sm text-muted mt-1">Browse without signing up</p>
          </BaseCard>
        </router-link>
      </div>
    </div>
  </div>
</template>
