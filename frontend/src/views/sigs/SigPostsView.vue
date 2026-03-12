<script setup lang="ts">
import { ref, onMounted, computed, inject, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSigPosts } from '@/api/sigs'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import type { Post, Sig } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'

const { t } = useI18n()
const toast = useToastStore()
const route = useRoute()
const sigId = computed(() => route.params.id as string)
const sig = inject<Ref<Sig | null>>('sig', ref(null))
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
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('sigs.posts.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(fetchPosts)
</script>

<template>
  <div class="space-y-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        { label: sig?.name || '...', to: `/sigs/${sigId}` },
        { label: t('breadcrumb.posts') },
      ]"
    />
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

          <router-link
            :to="{
              path: `/forum/${p.id}`,
              query: { fromSigId: sigId, fromSigName: sig?.name || '' },
            }"
            class="group"
          >
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
