<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePostList } from '@/composables/usePostList'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import ForumLeftSidebar from '@/components/forum/ForumLeftSidebar.vue'
import SearchPanel from '@/components/shared/SearchPanel.vue'
import CategoryFilter from '@/components/shared/CategoryFilter.vue'
import SortControls from '@/components/shared/SortControls.vue'
import TrendingSidebar from '@/components/shared/TrendingSidebar.vue'

const { t } = useI18n()

const {
  posts,
  categories,
  trendingPosts,
  loading,
  isLoadingMore,
  hasMore,
  isSearching,
  isSearchLoading,
  showAdvanced,
  categoryFilter,
  searchKeyword,
  searchDateFrom,
  searchDateTo,
  searchLogic,
  sortBy,
  dateRangeInvalid,
  activeCategoryName,
  sentinelRef,
  selectCategory,
  selectSort,
  onSearchInput,
  immediateSearch,
  clearSearch,
  toggleAdvanced,
  loadMore,
  init,
  cleanup,
} = usePostList({
  postType: 'post',
  defaultSort: 'newest',
  i18nErrorKeys: {
    fetchPosts: 'forum.fetchPostsError',
    fetchCategories: 'forum.fetchCategoriesError',
    fetchTrending: 'forum.fetchTrendingError',
    searchError: 'forum.searchError',
  },
})

const sortOptions = [
  { value: 'newest', label: t('forum.sort.newest') },
  { value: 'oldest', label: t('forum.sort.oldest') },
  { value: 'most_comments', label: t('forum.sort.mostDiscussed') },
]

const showLogoLightbox = ref(false)

function openLogoLightbox() {
  showLogoLightbox.value = true
  document.body.style.overflow = 'hidden'
}

function closeLogoLightbox() {
  showLogoLightbox.value = false
  document.body.style.overflow = ''
}

function handleLightboxKey(e: KeyboardEvent) {
  if (showLogoLightbox.value && e.key === 'Escape') {
    closeLogoLightbox()
  }
}

onMounted(() => {
  init()
  document.addEventListener('keydown', handleLightboxKey)
})
onUnmounted(() => {
  cleanup()
  document.removeEventListener('keydown', handleLightboxKey)
  document.body.style.overflow = ''
})

defineExpose({ loadMore })
</script>

<template>
  <div class="w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
    <div class="max-w-[1340px] mx-auto">
      <BaseBreadcrumb
        :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.forum') }]"
      />

      <!-- Forum Banner -->
      <div
        class="bg-gradient-to-r from-brand-900 to-brand-700 rounded-lg px-6 py-5 mb-6 flex items-center gap-5"
      >
        <button
          type="button"
          class="shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-white rounded"
          aria-label="Enlarge AI3L logo"
          @click="openLogoLightbox"
        >
          <img
            src="/images/logo.png"
            alt="AI3L"
            class="h-16 sm:h-20 w-auto drop-shadow-lg cursor-zoom-in hover:opacity-90 transition-opacity"
          />
        </button>
        <div>
          <h1 class="text-xl sm:text-2xl font-bold text-white">{{ t('forum.title') }}</h1>
          <p class="text-brand-200 text-sm mt-1">{{ t('home.tagline') }}</p>
        </div>
      </div>

      <!-- Mobile Category Pills -->
      <div class="lg:hidden mb-4">
        <CategoryFilter
          :categories="categories"
          :active-category="categoryFilter"
          mode="pills"
          :all-label="t('common.all')"
          @select="selectCategory"
        />
      </div>

      <!-- 3-column layout -->
      <div class="flex gap-6 justify-center">
        <!-- Left Sidebar (xl+) -->
        <aside class="hidden xl:block w-[240px] 2xl:w-[280px] shrink-0">
          <div class="sticky top-20">
            <ForumLeftSidebar />
          </div>
        </aside>

        <!-- Main Feed Column -->
        <div class="w-full lg:flex-1 xl:w-[640px] xl:flex-none 2xl:w-[680px] min-w-0">
          <SearchPanel
            :keyword="searchKeyword"
            :date-from="searchDateFrom"
            :date-to="searchDateTo"
            :logic="searchLogic"
            :show-advanced="showAdvanced"
            :is-search-loading="isSearchLoading"
            :is-searching="isSearching"
            :date-range-invalid="dateRangeInvalid"
            :placeholder="t('forum.searchPlaceholder')"
            @update:keyword="searchKeyword = $event"
            @update:date-from="searchDateFrom = $event"
            @update:date-to="searchDateTo = $event"
            @update:logic="searchLogic = $event"
            @search-input="onSearchInput"
            @immediate-search="immediateSearch"
            @toggle-advanced="toggleAdvanced"
            @clear-search="clearSearch"
          />

          <SortControls
            :current-sort="sortBy"
            :options="sortOptions"
            :active-category-name="activeCategoryName"
            @select="selectSort"
          />

          <SkeletonLoader v-if="loading" :lines="3" variant="card" />
          <EmptyState
            v-else-if="posts.length === 0"
            :message="t('forum.emptyMessage')"
            :title="t('forum.emptyTitle')"
            :action-label="t('forum.createPostAction')"
            action-to="/forum/create"
          />

          <!-- Post Feed -->
          <div class="space-y-2 md:space-y-4">
            <div v-for="post in posts" :key="post.id">
              <PostCard :post="post" />
            </div>
          </div>

          <!-- Infinite Scroll Sentinel -->
          <div ref="sentinelRef" class="h-4"></div>

          <!-- Loading More Spinner -->
          <div v-if="isLoadingMore" class="flex justify-center py-6">
            <svg
              class="animate-spin h-6 w-6 text-brand-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              role="status"
              :aria-label="t('forum.loadingMore')"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              ></path>
            </svg>
          </div>

          <!-- No More Posts -->
          <p v-if="!hasMore && posts.length > 0" class="mt-4 text-sm text-muted text-center py-4">
            {{ t('forum.noMorePosts') }}
          </p>
        </div>

        <!-- Right Sidebar (lg+) -->
        <aside class="hidden lg:block w-[240px] 2xl:w-[280px] shrink-0">
          <div class="sticky top-20 space-y-6">
            <!-- About -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-2">
                {{ t('forum.sidebar.aboutTitle') }}
              </h3>
              <p class="text-sm text-muted">
                {{ t('forum.sidebar.aboutDescription') }}
              </p>
            </BaseCard>

            <!-- Categories -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-3">
                {{ t('forum.sidebar.categoriesTitle') }}
              </h3>
              <CategoryFilter
                :categories="categories"
                :active-category="categoryFilter"
                mode="list"
                :all-label="t('forum.sidebar.allPosts')"
                @select="selectCategory"
              />
            </BaseCard>

            <!-- Trending Posts -->
            <TrendingSidebar
              :posts="trendingPosts"
              :title="t('forum.sidebar.trendingTitle')"
              link-prefix="/forum"
            />
          </div>
        </aside>
      </div>

      <FloatingCreateButton to="/forum/create" />
    </div>
  </div>

  <!-- Logo Lightbox -->
  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="showLogoLightbox"
        class="fixed inset-0 z-50 bg-black/85 flex items-center justify-center"
        role="dialog"
        aria-modal="true"
        aria-label="AI3L logo enlarged view"
        @click="closeLogoLightbox"
      >
        <button
          type="button"
          class="absolute top-6 right-4 sm:top-4 text-white/80 hover:text-white p-3 rounded-full bg-black/30 hover:bg-black/50 transition"
          aria-label="Close"
          @click.stop="closeLogoLightbox"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-6 h-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <img
          src="/images/logo.png"
          alt="AI3L"
          class="max-w-[90vw] max-h-[85vh] object-contain drop-shadow-2xl"
          @click.stop
        />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.lightbox-enter-active,
.lightbox-leave-active {
  transition: opacity 0.2s ease;
}
.lightbox-enter-from,
.lightbox-leave-to {
  opacity: 0;
}
</style>
