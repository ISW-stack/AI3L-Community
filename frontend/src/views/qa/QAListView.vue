<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { usePostList } from '@/composables/usePostList'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'
import QACard from '@/components/qa/QACard.vue'
import SearchPanel from '@/components/shared/SearchPanel.vue'
import CategoryFilter from '@/components/shared/CategoryFilter.vue'
import SortControls from '@/components/shared/SortControls.vue'
import TrendingSidebar from '@/components/shared/TrendingSidebar.vue'

const { t } = useI18n()
const auth = useAuthStore()

const {
  posts: questions,
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
  init,
  cleanup,
} = usePostList({
  postType: 'question',
  defaultSort: 'newest',
  i18nErrorKeys: {
    fetchPosts: 'qa.fetchError',
    fetchCategories: 'qa.loadCategoriesError',
    fetchTrending: 'qa.fetchTrendingError',
    searchError: 'qa.searchError',
  },
})

const sortOptions = [
  { value: 'newest', label: t('qa.sort.newest') },
  { value: 'oldest', label: t('qa.sort.oldest') },
  { value: 'most_answers', label: t('qa.sort.mostAnswers') },
  { value: 'unanswered', label: t('qa.sort.unanswered') },
]

onMounted(init)
onUnmounted(cleanup)
</script>

<template>
  <div class="w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
    <div class="max-w-[1340px] mx-auto">
      <BaseBreadcrumb
        :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.qa') }]"
      />
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold text-foreground">{{ t('qa.title') }}</h1>
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

      <!-- 2-column layout -->
      <div class="flex gap-6 justify-center">
        <!-- Main Feed Column -->
        <div class="w-full lg:flex-1 min-w-0">
          <SearchPanel
            :keyword="searchKeyword"
            :date-from="searchDateFrom"
            :date-to="searchDateTo"
            :logic="searchLogic"
            :show-advanced="showAdvanced"
            :is-search-loading="isSearchLoading"
            :is-searching="isSearching"
            :date-range-invalid="dateRangeInvalid"
            :placeholder="t('qa.searchPlaceholder')"
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
            v-else-if="questions.length === 0"
            :title="t('qa.noQuestions')"
            :message="t('qa.emptyMessage')"
            :action-label="auth.isAuthenticated && !auth.isGuest ? t('qa.askQuestion') : undefined"
            action-to="/qa/ask"
          />

          <!-- Question Feed -->
          <div v-else class="space-y-3">
            <QACard v-for="q in questions" :key="q.id" :question="q" />
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
              :aria-label="t('qa.loadingMore')"
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

          <!-- No More Questions -->
          <p
            v-if="!hasMore && questions.length > 0"
            class="mt-4 text-sm text-muted text-center py-4"
          >
            {{ t('qa.noMoreQuestions') }}
          </p>
        </div>

        <!-- Right Sidebar (lg+) -->
        <aside class="hidden lg:block w-[240px] 2xl:w-[280px] shrink-0">
          <div class="sticky top-20 space-y-6">
            <!-- About -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-2">
                {{ t('qa.sidebar.aboutTitle') }}
              </h3>
              <p class="text-sm text-muted">
                {{ t('qa.sidebar.aboutDescription') }}
              </p>
            </BaseCard>

            <!-- Categories -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-3">
                {{ t('qa.sidebar.categoriesTitle') }}
              </h3>
              <CategoryFilter
                :categories="categories"
                :active-category="categoryFilter"
                mode="list"
                :all-label="t('qa.sidebar.allQuestions')"
                @select="selectCategory"
              />
            </BaseCard>

            <!-- Trending Questions -->
            <TrendingSidebar
              :posts="trendingPosts"
              :title="t('qa.sidebar.trendingTitle')"
              link-prefix="/qa"
            >
              <template #item="{ post }">
                <router-link
                  :to="`/qa/${post.id}`"
                  class="block hover:bg-surface-alt rounded-lg px-2 py-1.5 -mx-2 transition"
                >
                  <p class="text-sm text-foreground font-medium line-clamp-2">{{ post.title }}</p>
                  <div class="flex items-center gap-3 mt-1 text-xs text-muted">
                    <span>{{ t('qa.sidebar.answerCount', { count: post.answer_count }) }}</span>
                    <span v-if="post.best_answer_id" class="text-success-700 font-medium">{{
                      t('qa.answered')
                    }}</span>
                  </div>
                </router-link>
              </template>
            </TrendingSidebar>
          </div>
        </aside>
      </div>

      <FloatingCreateButton v-if="auth.isAuthenticated && !auth.isGuest" to="/qa/ask" />
    </div>
  </div>
</template>
