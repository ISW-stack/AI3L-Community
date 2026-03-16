<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { FriendRecommendation, RecommendationReason } from '@/types/recommendation'
import { getRecommendations, dismissRecommendation } from '@/api/recommendations'
import { sendFriendRequest } from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import { ChevronDown, ChevronUp, UserPlus, X, Users } from 'lucide-vue-next'

const auth = useAuthStore()
const toast = useToastStore()

const recommendations = ref<FriendRecommendation[]>([])
const loading = ref(false)
const collapsed = ref(false)
const sendingRequests = ref<Set<string>>(new Set())

function formatReason(reason: RecommendationReason): string {
  switch (reason.type) {
    case 'common_sig':
      return `${reason.count} shared SIG${(reason.count ?? 0) > 1 ? 's' : ''}`
    case 'mutual_friends':
      return `${reason.count} mutual friend${(reason.count ?? 0) > 1 ? 's' : ''}`
    case 'similar_keywords':
      return 'Similar interests'
    case 'same_affiliation':
      return `Same affiliation: ${reason.affiliation}`
    case 'activity_recency':
      return 'Recently active'
    default:
      return ''
  }
}

function topReason(reasons: RecommendationReason[]): string {
  if (!reasons.length) return ''
  return formatReason(reasons[0])
}

async function fetchRecommendations() {
  if (!auth.isAuthenticated || auth.isGuest) return
  loading.value = true
  try {
    const { data } = await getRecommendations()
    recommendations.value = data.recommendations.slice(0, 10)
  } catch (e: unknown) {
    console.error('Failed to fetch recommendations:', getErrorMessage(e))
  } finally {
    loading.value = false
  }
}

async function handleAddFriend(userId: string) {
  sendingRequests.value.add(userId)
  try {
    await sendFriendRequest(userId)
    // Remove from recommendations after successful request
    recommendations.value = recommendations.value.filter((r) => r.user_id !== userId)
    toast.show('Friend request sent', 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to send friend request'), 'error')
  } finally {
    sendingRequests.value.delete(userId)
  }
}

async function handleDismiss(userId: string) {
  // Optimistic removal
  const removed = recommendations.value.find((r) => r.user_id === userId)
  recommendations.value = recommendations.value.filter((r) => r.user_id !== userId)
  try {
    await dismissRecommendation(userId)
  } catch (e: unknown) {
    // Rollback on error
    if (removed) {
      recommendations.value.push(removed)
    }
    toast.show(getErrorMessage(e, 'Failed to dismiss recommendation'), 'error')
  }
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

onMounted(fetchRecommendations)
</script>

<template>
  <BaseCard
    v-if="auth.isAuthenticated && !auth.isGuest"
    padding="md"
    data-testid="friend-recommendations"
  >
    <!-- Header -->
    <button class="w-full flex items-center justify-between mb-2" @click="toggleCollapsed">
      <div class="flex items-center gap-2">
        <Users class="w-4 h-4 text-brand-600" />
        <h3 class="text-sm font-semibold text-foreground">People You May Know</h3>
      </div>
      <component :is="collapsed ? ChevronDown : ChevronUp" class="w-4 h-4 text-muted" />
    </button>

    <!-- Content -->
    <div v-if="!collapsed">
      <!-- Loading -->
      <div v-if="loading" class="space-y-3">
        <div v-for="i in 3" :key="i" class="flex items-center gap-3 animate-pulse">
          <div class="w-8 h-8 bg-gray-200 rounded-full shrink-0"></div>
          <div class="flex-1 space-y-1">
            <div class="h-3 bg-gray-200 rounded w-3/4"></div>
            <div class="h-2.5 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <p
        v-else-if="recommendations.length === 0"
        class="text-sm text-muted py-2"
        data-testid="no-recommendations"
      >
        No recommendations right now. Check back later!
      </p>

      <!-- Recommendations list -->
      <ul v-else class="space-y-3">
        <li
          v-for="rec in recommendations"
          :key="rec.id"
          class="flex items-start gap-3"
          data-testid="recommendation-item"
        >
          <router-link :to="`/users/${rec.user_id}`" class="shrink-0">
            <BaseAvatar :src="rec.avatar_url" :name="rec.display_name" size="sm" />
          </router-link>

          <div class="flex-1 min-w-0">
            <router-link
              :to="`/users/${rec.user_id}`"
              class="text-sm font-medium text-foreground hover:text-brand-600 hover:underline block truncate"
            >
              {{ rec.display_name }}
            </router-link>
            <p v-if="rec.affiliation" class="text-xs text-muted truncate">
              {{ rec.affiliation }}
            </p>
            <p v-if="rec.reasons.length" class="text-xs text-brand-600 mt-0.5">
              {{ topReason(rec.reasons) }}
            </p>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button
              class="p-1 rounded text-brand-600 hover:bg-brand-50 transition"
              title="Add Friend"
              :disabled="sendingRequests.has(rec.user_id)"
              @click="handleAddFriend(rec.user_id)"
            >
              <UserPlus class="w-4 h-4" />
            </button>
            <button
              class="p-1 rounded text-muted hover:bg-surface-alt hover:text-foreground transition"
              title="Dismiss"
              @click="handleDismiss(rec.user_id)"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
        </li>
      </ul>
    </div>
  </BaseCard>
</template>
