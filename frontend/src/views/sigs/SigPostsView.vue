<script setup lang="ts">
import { ref, onMounted, computed, inject, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSigPosts } from '@/api/sigs'
import type { Post } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'

const { t } = useI18n()
const route = useRoute()
const sigId = computed(() => route.params.id as string)
const userSigRole = inject<Ref<string | null>>('userSigRole', ref(null))

const posts = ref<Post[]>([])
const total = ref(0)
const loading = ref(true)

const isMember = computed(() => userSigRole?.value != null)

async function fetchPosts() {
  loading.value = true
  try {
    const data = await getSigPosts(sigId.value)
    posts.value = data.posts
    total.value = data.total
  } catch (e) {
    console.error('Failed to fetch posts:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchPosts)
</script>

<template>
  <div class="space-y-4">
    <!-- Header/Actions -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-foreground">
        {{ t('sigs.posts.title') }} ({{ total }})
      </h2>
    </div>

    <!-- Content -->
    <div v-if="loading" class="space-y-3">
      <SkeletonLoader v-for="i in 3" :key="i" variant="card" :lines="2" />
    </div>

    <EmptyState
      v-else-if="posts.length === 0"
      :title="t('sigs.posts.emptyTitle')"
      :message="t('sigs.posts.emptyMessage')"
    />

    <div v-else class="space-y-3">
      <div v-for="p in posts" :key="p.id">
        <BaseCard hoverable padding="md">
          <div class="flex items-center gap-2 mb-3">
            <router-link :to="`/users/${p.author.id}`">
              <BaseAvatar :src="p.author.avatar_url" :name="p.author.display_name" size="sm" />
            </router-link>
            <div class="min-w-0">
              <router-link
                :to="`/users/${p.author.id}`"
                class="text-sm font-medium text-foreground hover:text-brand-600 block truncate"
              >
                {{ p.author.display_name }}
              </router-link>
              <div class="text-[10px] text-muted">
                {{ new Date(p.created_at).toLocaleString() }}
              </div>
            </div>
          </div>

          <router-link :to="`/forum/${p.id}`" class="group">
            <h3 class="font-bold text-foreground mb-1 group-hover:text-brand-600 transition-colors">
              {{ p.title }}
            </h3>
          </router-link>

          <div class="flex items-center gap-4 mt-3 text-xs text-muted">
            <span class="flex items-center gap-1">
              {{ p.comment_count }} {{ t('sigs.posts.comments') }}
            </span>
          </div>
        </BaseCard>
      </div>
    </div>

    <FloatingCreateButton v-if="isMember" :to="`/forum/create?sig_id=${sigId}`" />
  </div>
</template>
