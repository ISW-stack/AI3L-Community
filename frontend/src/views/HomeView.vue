<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { listPosts, getTrendingPosts, getPublicStats } from '@/api/posts'
import { listMySigs, listSigs } from '@/api/sigs'
import { applyForMembership, getMyApplication } from '@/api/users'
import type { MyApplication } from '@/api/users'
import type { Post, Sig } from '@/types'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { useFetchPaginated } from '@/composables/useFetchPaginated'
import { getErrorMessage } from '@/utils/error'
import { MessageSquare, Users, FileText, BookOpen, TrendingUp } from 'lucide-vue-next'
import FriendRecommendations from '@/components/social/FriendRecommendations.vue'

const { t } = useI18n()
const auth = useAuthStore()
const notifStore = useNotificationStore()
const toast = useToastStore()

const {
  items: recentPosts,
  loading: loadingPosts,
  fetchPage: fetchRecentPosts,
} = useFetchPaginated<Post>(async () => {
  const data = await listPosts({ page: 1, page_size: 5, sort: 'newest' })
  return { items: data.posts, total: data.total ?? 0 }
}, 5)

const trendingPosts = ref<Post[]>([])
const mySigs = ref<Sig[]>([])
const featuredSigs = ref<Sig[]>([])
const publicStats = ref<{ member_count: number; post_count: number; sig_count: number } | null>(
  null,
)
const loadingTrending = ref(false)
const loadingMySigs = ref(false)
const loadingStats = ref(false)
const loadingFeaturedSigs = ref(false)

// ── Membership application ──────────────────────────────────
const showApplyModal = ref(false)
const applyForm = ref({ username: '', password: '', display_name: '', description: '' })
const applyErrors = ref<Record<string, string>>({})
const applySubmitting = ref(false)
const myApplication = ref<MyApplication | null>(null)

function validateApplyForm(): boolean {
  const errs: Record<string, string> = {}
  const uname = applyForm.value.username
  if (uname.length < 3) {
    errs.username = t('home.applyMembership.validation.usernameMin')
  } else if (uname.length > 50) {
    errs.username = t('home.applyMembership.validation.usernameMax')
  } else if (!/^[a-zA-Z0-9_.@-]+$/.test(uname)) {
    errs.username = t('home.applyMembership.validation.usernameFormat')
  }
  const pw = applyForm.value.password
  if (pw.length < 8) {
    errs.password = t('home.applyMembership.validation.passwordMin')
  } else if (
    !/[A-Z]/.test(pw) ||
    !/[a-z]/.test(pw) ||
    !/\d/.test(pw) ||
    !/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?\/~]/.test(pw)
  ) {
    errs.password = t('home.applyMembership.validation.passwordPolicy')
  }
  if (applyForm.value.display_name.trim().length === 0)
    errs.display_name = t('home.applyMembership.validation.displayNameRequired')
  if (applyForm.value.description.trim().length === 0)
    errs.description = t('home.applyMembership.validation.descriptionRequired')
  applyErrors.value = errs
  return Object.keys(errs).length === 0
}

async function handleApplySubmit() {
  if (!validateApplyForm()) return
  applySubmitting.value = true
  applyErrors.value = {}
  try {
    await applyForMembership({
      username: applyForm.value.username,
      password: applyForm.value.password,
      display_name: applyForm.value.display_name,
      description: applyForm.value.description,
    })
    toast.show(t('home.applyMembership.success'), 'success')
    showApplyModal.value = false
    applyForm.value = { username: '', password: '', display_name: '', description: '' }
    // Refresh application status
    await fetchMyApplication()
  } catch (e: unknown) {
    const msg = getErrorMessage(e, t('home.applyMembership.error'))
    toast.show(msg, 'error')
  } finally {
    applySubmitting.value = false
  }
}

async function fetchMyApplication() {
  try {
    const data = await getMyApplication()
    myApplication.value = data.application
  } catch (e: unknown) {
    // If the axios interceptor already cleared the session (e.g. 401),
    // bail silently — the user is being redirected to login.
    if (!auth.isAuthenticated) return
    // 404 expected for guests who haven't applied yet
    const { isAxiosError } = await import('axios')
    if (isAxiosError(e) && e.response?.status === 404) return
    // Surface unexpected errors
    toast.show(
      getErrorMessage(
        e,
        t('home.applyMembership.fetchError', 'Failed to check application status.'),
      ),
      'error',
    )
  }
}

// ── Data fetching ───────────────────────────────────────────

async function fetchTrendingPosts() {
  loadingTrending.value = true
  try {
    trendingPosts.value = await getTrendingPosts()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('home.trending.fetchError')), 'error')
  } finally {
    loadingTrending.value = false
  }
}

async function fetchMySigs() {
  loadingMySigs.value = true
  try {
    mySigs.value = await listMySigs()
  } catch (e: unknown) {
    if (import.meta.env.DEV) console.error('Failed to fetch SIGs:', getErrorMessage(e))
  } finally {
    loadingMySigs.value = false
  }
}

async function fetchPublicStats() {
  loadingStats.value = true
  try {
    publicStats.value = await getPublicStats()
  } catch (e: unknown) {
    if (import.meta.env.DEV) console.error('Failed to fetch public stats:', getErrorMessage(e))
  } finally {
    loadingStats.value = false
  }
}

async function fetchFeaturedSigs() {
  loadingFeaturedSigs.value = true
  try {
    const data = await listSigs()
    // Show up to 3 SIGs as featured
    featuredSigs.value = data.sigs.slice(0, 3)
  } catch (e: unknown) {
    if (import.meta.env.DEV) console.error('Failed to fetch featured SIGs:', getErrorMessage(e))
  } finally {
    loadingFeaturedSigs.value = false
  }
}

onMounted(() => {
  fetchPublicStats()
  if (auth.isAuthenticated) {
    fetchRecentPosts()
    fetchTrendingPosts()
    notifStore.fetchUnreadCount()
    if (!auth.isGuest) {
      fetchMySigs()
    } else {
      fetchMyApplication()
    }
    fetchFeaturedSigs()
  }
})
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <!-- Authenticated view -->
    <div v-if="auth.isAuthenticated">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main column -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Welcome card -->
          <BaseCard padding="lg">
            <h2 class="text-xl font-semibold text-foreground mb-2">
              {{
                auth.isGuest
                  ? t('home.welcome.guest')
                  : t('home.welcome.user', { name: auth.user?.display_name })
              }}
            </h2>
            <p class="text-muted">{{ t('home.tagline') }}</p>
            <div class="mt-4 flex flex-col sm:flex-row gap-3">
              <router-link to="/forum">
                <BaseButton>{{ t('home.browseForumBtn') }}</BaseButton>
              </router-link>
              <router-link to="/sigs">
                <BaseButton variant="secondary">{{ t('home.mySigsBtn') }}</BaseButton>
              </router-link>
            </div>
          </BaseCard>

          <!-- Guest alert + membership application -->
          <template v-if="auth.isGuest">
            <BaseAlert type="warning">
              {{ t('home.guestAlert') }}
              <router-link to="/register" class="font-medium underline">{{
                t('home.guestSignUp')
              }}</router-link>
              {{ t('home.guestSignUpSuffix') }}
            </BaseAlert>

            <!-- Application status or apply button -->
            <BaseCard v-if="myApplication" padding="md">
              <div class="flex items-center gap-3">
                <span
                  :class="[
                    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                    myApplication.status === 'PENDING'
                      ? 'bg-yellow-100 text-yellow-800'
                      : myApplication.status === 'APPROVED'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800',
                  ]"
                >
                  {{ t(`home.applyMembership.status.${myApplication.status}`) }}
                </span>
                <p class="text-sm text-muted">
                  {{ t('home.applyMembership.submitted') }}
                </p>
              </div>
            </BaseCard>

            <BaseCard v-else padding="md">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm font-medium text-foreground">
                    {{ t('home.applyMembership.title') }}
                  </p>
                  <p class="text-xs text-muted mt-0.5">
                    {{ t('home.applyMembership.description') }}
                  </p>
                </div>
                <BaseButton size="sm" @click="showApplyModal = true">
                  {{ t('home.applyMembership.applyBtn') }}
                </BaseButton>
              </div>
            </BaseCard>
          </template>

          <!-- Trending Posts -->
          <div v-if="!auth.isGuest">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <TrendingUp class="w-5 h-5 text-brand-600" />
                <h3 class="text-lg font-semibold text-foreground">
                  {{ t('home.trending.title') }}
                </h3>
              </div>
              <router-link
                v-if="trendingPosts.length > 0"
                to="/forum?sort=trending"
                class="text-sm text-brand-600 hover:underline"
              >
                {{ t('home.trending.viewAll') }}
              </router-link>
            </div>
            <SkeletonLoader v-if="loadingTrending" :lines="3" variant="list" />
            <div v-else-if="trendingPosts.length === 0" class="text-sm text-muted">
              {{ t('home.trending.empty') }}
            </div>
            <div v-else class="space-y-4">
              <PostCard
                v-for="p in trendingPosts.slice(0, 3)"
                :key="p.id"
                :post="p"
                :max-preview-lines="3"
              />
            </div>
          </div>

          <!-- Recent posts -->
          <div>
            <h3 class="text-lg font-semibold text-foreground mb-3">
              {{ t('home.recentPosts.title') }}
            </h3>
            <SkeletonLoader v-if="loadingPosts" :lines="3" variant="list" />
            <div v-else-if="recentPosts.length === 0" class="text-sm text-muted">
              {{ t('home.recentPosts.empty') }}
            </div>
            <div v-else class="space-y-4">
              <PostCard v-for="p in recentPosts" :key="p.id" :post="p" :max-preview-lines="3" />
            </div>
          </div>
        </div>

        <!-- Right sidebar -->
        <div class="space-y-6 sticky top-20 self-start">
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

          <!-- Friend Recommendations -->
          <FriendRecommendations />

          <!-- Community Stats -->
          <BaseCard v-if="publicStats" padding="md">
            <h3 class="text-sm font-semibold text-foreground mb-3">
              {{ t('home.stats.title') }}
            </h3>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div>
                <p class="text-xl font-bold text-brand-600">{{ publicStats.member_count }}</p>
                <p class="text-xs text-muted">{{ t('home.stats.members') }}</p>
              </div>
              <div>
                <p class="text-xl font-bold text-brand-600">{{ publicStats.post_count }}</p>
                <p class="text-xs text-muted">{{ t('home.stats.posts') }}</p>
              </div>
              <div>
                <p class="text-xl font-bold text-brand-600">{{ publicStats.sig_count }}</p>
                <p class="text-xs text-muted">{{ t('home.stats.sigs') }}</p>
              </div>
            </div>
          </BaseCard>

          <!-- Your SIGs -->
          <BaseCard v-if="!auth.isGuest && mySigs.length > 0" padding="md">
            <h3 class="text-sm font-semibold text-foreground mb-3">
              {{ t('home.yourSigs.title') }}
            </h3>
            <ul class="space-y-2">
              <li v-for="sig in mySigs.slice(0, 5)" :key="sig.id">
                <router-link
                  :to="`/sigs/${sig.id}`"
                  class="flex items-center justify-between text-sm hover:bg-surface-alt -mx-2 px-2 py-1.5 rounded transition"
                >
                  <span class="text-foreground font-medium truncate">{{ sig.name }}</span>
                  <span class="text-xs text-muted shrink-0 ml-2">
                    {{ sig.member_count }} {{ t('home.yourSigs.members') }}
                  </span>
                </router-link>
              </li>
            </ul>
            <router-link
              v-if="mySigs.length > 5"
              to="/sigs"
              class="block text-xs text-brand-600 hover:underline mt-2"
            >
              {{ t('home.yourSigs.viewAll') }}
            </router-link>
          </BaseCard>

          <!-- Featured SIGs -->
          <BaseCard v-if="featuredSigs.length > 0" padding="md">
            <h3 class="text-sm font-semibold text-foreground mb-3">
              {{ t('home.featuredSigs.title') }}
            </h3>
            <ul class="space-y-2">
              <li v-for="sig in featuredSigs" :key="sig.id">
                <router-link
                  :to="`/sigs/${sig.id}`"
                  class="block hover:bg-surface-alt -mx-2 px-2 py-1.5 rounded transition"
                >
                  <p class="text-sm font-medium text-foreground">{{ sig.name }}</p>
                  <p v-if="sig.description" class="text-xs text-muted line-clamp-2">
                    {{ sig.description }}
                  </p>
                </router-link>
              </li>
            </ul>
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
      <div class="relative overflow-hidden rounded-lg mb-8">
        <!-- Background gradient -->
        <div
          class="absolute inset-0 bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700"
        ></div>
        <!-- Radial overlay for depth -->
        <div
          class="absolute inset-0 opacity-30"
          style="
            background:
              radial-gradient(ellipse at 20% 50%, rgba(255, 255, 255, 0.15) 0%, transparent 60%),
              radial-gradient(ellipse at 80% 20%, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
          "
        ></div>
        <!-- Dot pattern overlay -->
        <div class="hero-pattern absolute inset-0"></div>
        <!-- Decorative floating shapes -->
        <div class="absolute -top-12 -left-12 w-48 h-48 rounded-full bg-white/5 blur-2xl"></div>
        <div class="absolute -bottom-16 -right-16 w-64 h-64 rounded-full bg-white/5 blur-3xl"></div>
        <div class="absolute top-1/4 right-[15%] w-24 h-24 rounded-full bg-white/5 blur-xl"></div>
        <!-- Content -->
        <div class="relative p-8 sm:p-12 text-white text-center">
          <img src="/images/logo.png" alt="AI3L" class="w-48 sm:w-64 mx-auto mb-6 drop-shadow-lg" />
          <h1 class="text-3xl sm:text-4xl font-bold mb-3">
            {{ t('home.unauthenticated.title') }}
          </h1>
          <p class="text-brand-200 text-lg mb-2">
            {{ t('home.unauthenticated.subtitle') }}
          </p>
          <p class="text-brand-200 mt-2">
            {{ t('home.unauthenticated.tagline') }}
          </p>
          <div class="flex flex-wrap items-center justify-center gap-3 mt-6">
            <router-link to="/register">
              <button
                class="inline-flex items-center justify-center min-h-[44px] px-6 py-2.5 rounded-lg font-semibold text-brand-700 bg-white hover:bg-brand-50 transition-colors duration-200 shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-800 touch-manipulation"
              >
                {{ t('home.unauthenticated.getStartedBtn') }}
              </button>
            </router-link>
            <router-link to="/guest">
              <button
                class="inline-flex items-center justify-center min-h-[44px] px-6 py-2.5 rounded-lg font-semibold text-white border-2 border-white/40 bg-white/10 hover:bg-white/20 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-800 touch-manipulation"
              >
                {{ t('home.unauthenticated.browseGuestBtn') }}
              </button>
            </router-link>
          </div>
        </div>
      </div>

      <!-- Community stats section — real numbers from API -->
      <div class="grid grid-cols-3 gap-2 sm:gap-5 mb-8">
        <div class="bg-surface rounded-xl p-3 sm:p-5 shadow-sm text-center">
          <div
            class="hidden sm:inline-flex items-center justify-center w-10 h-10 rounded-full bg-brand-50 text-brand-600 mb-2"
          >
            <Users class="w-5 h-5" aria-hidden="true" />
          </div>
          <div
            v-if="loadingStats"
            class="h-8 sm:h-9 w-12 sm:w-16 bg-gray-200 rounded animate-pulse mx-auto mb-1"
          ></div>
          <p v-else class="text-2xl sm:text-3xl font-extrabold text-foreground">
            {{ publicStats ? publicStats.member_count : '—' }}
          </p>
          <p class="text-xs sm:text-sm text-muted mt-1">{{ t('home.stats.members') }}</p>
        </div>
        <div class="bg-surface rounded-xl p-3 sm:p-5 shadow-sm text-center">
          <div
            class="hidden sm:inline-flex items-center justify-center w-10 h-10 rounded-full bg-brand-50 text-brand-600 mb-2"
          >
            <FileText class="w-5 h-5" aria-hidden="true" />
          </div>
          <div
            v-if="loadingStats"
            class="h-8 sm:h-9 w-12 sm:w-16 bg-gray-200 rounded animate-pulse mx-auto mb-1"
          ></div>
          <p v-else class="text-2xl sm:text-3xl font-extrabold text-foreground">
            {{ publicStats ? publicStats.post_count : '—' }}
          </p>
          <p class="text-xs sm:text-sm text-muted mt-1">{{ t('home.stats.posts') }}</p>
        </div>
        <div class="bg-surface rounded-xl p-3 sm:p-5 shadow-sm text-center">
          <div
            class="hidden sm:inline-flex items-center justify-center w-10 h-10 rounded-full bg-brand-50 text-brand-600 mb-2"
          >
            <BookOpen class="w-5 h-5" aria-hidden="true" />
          </div>
          <div
            v-if="loadingStats"
            class="h-8 sm:h-9 w-12 sm:w-16 bg-gray-200 rounded animate-pulse mx-auto mb-1"
          ></div>
          <p v-else class="text-2xl sm:text-3xl font-extrabold text-foreground">
            {{ publicStats ? publicStats.sig_count : '—' }}
          </p>
          <p class="text-xs sm:text-sm text-muted mt-1">{{ t('home.stats.sigs') }}</p>
        </div>
      </div>

      <!-- Feature cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <router-link to="/register" class="block">
          <BaseCard
            hoverable
            padding="lg"
            class="text-center h-full border-t-2 border-brand-500 hover:-translate-y-1 transition-all duration-200"
          >
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
          <BaseCard
            hoverable
            padding="lg"
            class="text-center h-full border-t-2 border-emerald-500 hover:-translate-y-1 transition-all duration-200"
          >
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-emerald-50 text-emerald-600 mb-3"
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
          <BaseCard
            hoverable
            padding="lg"
            class="text-center h-full border-t-2 border-amber-500 hover:-translate-y-1 transition-all duration-200"
          >
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-amber-50 text-amber-600 mb-3"
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
          <BaseCard
            hoverable
            padding="lg"
            class="text-center h-full border-t-2 border-purple-500 hover:-translate-y-1 transition-all duration-200"
          >
            <div
              class="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-purple-50 text-purple-600 mb-3"
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

    <!-- Membership application modal -->
    <BaseModal v-model="showApplyModal" :title="t('home.applyMembership.title')" size="md">
      <form class="space-y-4" @submit.prevent="handleApplySubmit">
        <p class="text-sm text-muted">{{ t('home.applyMembership.description') }}</p>

        <BaseInput
          id="apply-username"
          v-model="applyForm.username"
          :label="t('auth.username')"
          :placeholder="t('home.applyMembership.usernamePlaceholder')"
          :error="applyErrors.username"
          :maxlength="50"
          autocomplete="username"
        />
        <p class="text-xs text-muted -mt-3">
          {{ t('home.applyMembership.usernameHint') }}
        </p>

        <BaseInput
          id="apply-password"
          v-model="applyForm.password"
          type="password"
          :label="t('auth.password')"
          :placeholder="t('home.applyMembership.passwordPlaceholder')"
          :error="applyErrors.password"
          :maxlength="128"
          autocomplete="new-password"
        />
        <p class="text-xs text-muted -mt-3">
          {{ t('home.applyMembership.passwordHint') }}
        </p>

        <BaseInput
          id="apply-display-name"
          v-model="applyForm.display_name"
          :label="t('auth.displayName')"
          :error="applyErrors.display_name"
          :maxlength="100"
        />

        <BaseTextarea
          id="apply-description"
          v-model="applyForm.description"
          :label="t('home.applyMembership.reasonLabel')"
          :placeholder="t('home.applyMembership.placeholder')"
          :error="applyErrors.description"
          :maxlength="500"
          :rows="4"
        />
        <p class="text-xs text-muted text-right -mt-3">{{ applyForm.description.length }}/500</p>
        <button type="submit" class="hidden" />
      </form>

      <template #footer>
        <BaseButton variant="secondary" :disabled="applySubmitting" @click="showApplyModal = false">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton :disabled="applySubmitting" @click="handleApplySubmit">
          {{ applySubmitting ? t('common.submitting') : t('home.applyMembership.submitBtn') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.hero-pattern {
  background-image: radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px);
  background-size: 20px 20px;
}
</style>
