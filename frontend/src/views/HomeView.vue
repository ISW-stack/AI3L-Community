<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
import { getErrorMessage } from '@/utils/error'
import { MessageSquare, Users, FileText, BookOpen } from 'lucide-vue-next'

const { t } = useI18n()
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
    toast.show(t('home.applyMembership.success'), 'success')
  } catch (err: unknown) {
    toast.show(getErrorMessage(err, t('home.applyMembership.error')), 'error')
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
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('home.recentPosts.fetchError')), 'error')
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
    <div v-if="auth.isAuthenticated">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left column -->
        <div class="lg:col-span-2 space-y-6">
          <BaseCard padding="lg">
            <h2 class="text-xl font-semibold text-foreground mb-2">
              {{
                auth.isGuest
                  ? t('home.welcome.guest')
                  : t('home.welcome.user', { name: auth.user?.display_name })
              }}
            </h2>
            <p class="text-muted">{{ t('home.tagline') }}</p>
            <div class="mt-4 flex flex-wrap gap-3">
              <router-link to="/forum">
                <BaseButton>{{ t('home.browseForumBtn') }}</BaseButton>
              </router-link>
              <router-link to="/sigs">
                <BaseButton variant="secondary">{{ t('home.mySigsBtn') }}</BaseButton>
              </router-link>
            </div>
          </BaseCard>

          <BaseAlert v-if="auth.isGuest" type="warning">
            {{ t('home.guestAlert') }}
            <router-link to="/register" class="font-medium underline">{{
              t('home.guestSignUp')
            }}</router-link>
            {{ t('home.guestSignUpSuffix') }}
          </BaseAlert>

          <!-- Guest membership application -->
          <BaseCard v-if="auth.isGuest" padding="lg">
            <h3 class="text-lg font-semibold text-foreground mb-2">
              {{ t('home.applyMembership.title') }}
            </h3>
            <div v-if="applicationSent" class="text-sm text-success-600">
              {{ t('home.applyMembership.submitted') }}
            </div>
            <div v-else>
              <p class="text-sm text-muted mb-3">
                {{ t('home.applyMembership.description') }}
              </p>
              <BaseTextarea
                v-model="applicationDesc"
                :placeholder="t('home.applyMembership.placeholder')"
                :rows="3"
                class="mb-3"
              />
              <BaseButton
                :disabled="!applicationDesc.trim() || applyLoading"
                :loading="applyLoading"
                @click="submitApplication"
              >
                {{ t('home.applyMembership.submitBtn') }}
              </BaseButton>
            </div>
          </BaseCard>

          <!-- Recent posts -->
          <BaseCard padding="lg">
            <h3 class="text-lg font-semibold text-foreground mb-3">
              {{ t('home.recentPosts.title') }}
            </h3>
            <SkeletonLoader v-if="loadingPosts" :lines="3" variant="list" />
            <div v-else-if="recentPosts.length === 0" class="text-sm text-muted">
              {{ t('home.recentPosts.empty') }}
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
                  <span>{{ p.comment_count }} {{ t('home.recentPosts.comments') }}</span>
                </div>
              </router-link>
            </div>
          </BaseCard>
        </div>

        <!-- Right column -->
        <div class="space-y-6">
          <!-- Unread notifications summary -->
          <BaseCard
            v-if="notifStore.unreadCount > 0"
            padding="md"
            class="border-l-4 border-brand-500"
          >
            <div class="flex items-center justify-between">
              <p class="text-sm text-foreground">
                {{ t('home.notifications.title') }} <strong>{{ notifStore.unreadCount }}</strong>
                {{ t('home.notifications.count') }}
              </p>
              <router-link to="/notifications">
                <BaseButton size="sm" variant="ghost">{{
                  t('home.notifications.viewBtn')
                }}</BaseButton>
              </router-link>
            </div>
          </BaseCard>

          <!-- Quick Links -->
          <BaseCard padding="md">
            <h3 class="text-sm font-semibold text-foreground mb-3">
              {{ t('home.quickLinks.title') }}
            </h3>
            <ul class="space-y-2">
              <li>
                <router-link to="/forum/create" class="text-sm text-brand-600 hover:underline">
                  {{ t('home.quickLinks.createPost') }}
                </router-link>
              </li>
              <li>
                <router-link to="/sigs" class="text-sm text-brand-600 hover:underline">
                  {{ t('home.quickLinks.browseSigs') }}
                </router-link>
              </li>
              <li v-if="!auth.isGuest">
                <router-link to="/profile" class="text-sm text-brand-600 hover:underline">
                  {{ t('home.quickLinks.editProfile') }}
                </router-link>
              </li>
            </ul>
          </BaseCard>
        </div>
      </div>
    </div>

    <!-- Unauthenticated view -->
    <div v-else>
      <!-- Hero Section -->
      <div
        class="bg-gradient-to-br from-brand-900 to-brand-700 rounded-lg p-8 sm:p-12 text-white text-center mb-8"
      >
        <h1 class="text-3xl sm:text-4xl font-bold mb-3">{{ t('home.unauthenticated.title') }}</h1>
        <p class="text-brand-200 text-lg mb-2">
          {{ t('home.unauthenticated.subtitle') }}
        </p>
        <p class="text-brand-200 mt-2">
          {{ t('home.unauthenticated.tagline') }}
        </p>
        <div class="flex flex-wrap items-center justify-center gap-3 mt-6">
          <router-link to="/register">
            <button
              class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg bg-white text-brand-900 hover:bg-brand-50 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              {{ t('home.unauthenticated.getStartedBtn') }}
            </button>
          </router-link>
          <router-link to="/guest">
            <button
              class="inline-flex items-center justify-center px-6 py-3 text-base font-semibold rounded-lg text-white/90 hover:text-white hover:bg-white/10 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              {{ t('home.unauthenticated.browseGuestBtn') }}
            </button>
          </router-link>
        </div>
      </div>

      <!-- Community stats section -->
      <div class="grid grid-cols-3 gap-4 mb-8">
        <div class="text-center">
          <p class="text-2xl font-bold text-foreground">
            {{ t('home.unauthenticated.stats.community') }}
          </p>
          <p class="text-sm text-muted">{{ t('home.unauthenticated.stats.communitySubtitle') }}</p>
        </div>
        <div class="text-center">
          <p class="text-2xl font-bold text-foreground">
            {{ t('home.unauthenticated.stats.focus') }}
          </p>
          <p class="text-sm text-muted">{{ t('home.unauthenticated.stats.focusSubtitle') }}</p>
        </div>
        <div class="text-center">
          <p class="text-2xl font-bold text-foreground">
            {{ t('home.unauthenticated.stats.network') }}
          </p>
          <p class="text-sm text-muted">{{ t('home.unauthenticated.stats.networkSubtitle') }}</p>
        </div>
      </div>

      <!-- Feature cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <MessageSquare class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">
              {{ t('home.unauthenticated.features.forum.title') }}
            </h3>
            <p class="text-sm text-muted mt-1">
              {{ t('home.unauthenticated.features.forum.description') }}
            </p>
          </BaseCard>
        </router-link>

        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <Users class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">
              {{ t('home.unauthenticated.features.sigs.title') }}
            </h3>
            <p class="text-sm text-muted mt-1">
              {{ t('home.unauthenticated.features.sigs.description') }}
            </p>
          </BaseCard>
        </router-link>

        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <FileText class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">
              {{ t('home.unauthenticated.features.forms.title') }}
            </h3>
            <p class="text-sm text-muted mt-1">
              {{ t('home.unauthenticated.features.forms.description') }}
            </p>
          </BaseCard>
        </router-link>

        <router-link to="/register" class="block">
          <BaseCard hoverable padding="lg" class="text-center h-full">
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-50 text-brand-600 mb-3"
            >
              <BookOpen class="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 class="font-semibold text-foreground">
              {{ t('home.unauthenticated.features.richContent.title') }}
            </h3>
            <p class="text-sm text-muted mt-1">
              {{ t('home.unauthenticated.features.richContent.description') }}
            </p>
          </BaseCard>
        </router-link>
      </div>
    </div>
  </div>
</template>
