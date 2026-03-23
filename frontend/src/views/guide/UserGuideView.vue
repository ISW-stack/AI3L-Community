<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { BookOpen, ChevronRight, X } from 'lucide-vue-next'
import GuestGuideContent from '@/components/guide/GuestGuideContent.vue'
import MemberGuideContent from '@/components/guide/MemberGuideContent.vue'
import AdminGuideContent from '@/components/guide/AdminGuideContent.vue'
import SuperAdminGuideContent from '@/components/guide/SuperAdminGuideContent.vue'

const auth = useAuthStore()

interface Tab {
  key: string
  label: string
  minRole: 'GUEST' | 'MEMBER' | 'ADMIN' | 'SUPER_ADMIN'
}

const ROLE_LEVELS: Record<string, number> = {
  GUEST: 0,
  MEMBER: 1,
  ADMIN: 2,
  SUPER_ADMIN: 3,
}

const allTabs: Tab[] = [
  { key: 'guest', label: 'Guest Guide', minRole: 'GUEST' },
  { key: 'member', label: 'Member Guide', minRole: 'MEMBER' },
  { key: 'admin', label: 'Admin Guide', minRole: 'ADMIN' },
  { key: 'super-admin', label: 'Super Admin Guide', minRole: 'SUPER_ADMIN' },
]

const userRoleLevel = computed(() => ROLE_LEVELS[auth.role || 'GUEST'] ?? 0)

const visibleTabs = computed(() =>
  allTabs.filter((tab) => ROLE_LEVELS[tab.minRole] <= userRoleLevel.value),
)

function getDefaultTab(): string {
  return 'guest'
}

const activeTab = ref(getDefaultTab())

interface SidebarItem {
  id: string
  label: string
}

const sidebarItems: Record<string, SidebarItem[]> = {
  guest: [
    { id: 'guest-getting-started', label: 'Getting Started' },
    { id: 'guest-home-dashboard', label: 'Home Dashboard' },
    { id: 'guest-browsing-forum', label: 'Browsing the Forum' },
    { id: 'guest-browsing-qa', label: 'Browsing Q&A' },
    { id: 'guest-sigs', label: 'SIGs' },
    { id: 'guest-forms', label: 'Submitting Forms' },
    { id: 'guest-albums', label: 'Albums' },
    { id: 'guest-notifications', label: 'Notifications' },
    { id: 'guest-profile', label: 'Profile' },
    { id: 'guest-apply-membership', label: 'Applying for Membership' },
    { id: 'guest-limitations', label: 'Guest Limitations' },
  ],
  member: [
    { id: 'member-creating-posts', label: 'Creating Posts' },
    { id: 'member-qa', label: 'Q&A' },
    { id: 'member-comments-reactions', label: 'Comments & Reactions' },
    { id: 'member-sigs', label: 'SIGs' },
    { id: 'member-forms', label: 'Forms' },
    { id: 'member-albums', label: 'Albums' },
    { id: 'member-dm', label: 'Direct Messages' },
    { id: 'member-social', label: 'Social Features' },
    { id: 'member-about', label: 'About Page' },
    { id: 'member-profile', label: 'Profile Management' },
    { id: 'member-file-uploads', label: 'File Uploads' },
  ],
  admin: [
    { id: 'admin-panel-overview', label: 'Admin Panel' },
    { id: 'admin-dashboard', label: 'Dashboard' },
    { id: 'admin-user-management', label: 'User Management' },
    { id: 'admin-applications', label: 'Applications' },
    { id: 'admin-reports', label: 'Reports' },
    { id: 'admin-categories', label: 'Categories' },
    { id: 'admin-invite-codes', label: 'Invite Codes' },
    { id: 'admin-content-moderation', label: 'Content Moderation' },
    { id: 'admin-create-sigs-albums', label: 'Creating SIGs & Albums' },
    { id: 'admin-cross-management', label: 'Cross-SIG & Form Mgmt' },
  ],
  'super-admin': [
    { id: 'sa-additional-pages', label: 'Additional Pages' },
    { id: 'sa-audit-logs', label: 'Audit Logs' },
    { id: 'sa-ip-bans', label: 'IP Bans' },
    { id: 'sa-site-settings', label: 'Site Settings' },
    { id: 'sa-contributors', label: 'Contributors' },
    { id: 'sa-role-management', label: 'Role Management' },
    { id: 'sa-ban-deletion', label: 'Ban & Deletion' },
    { id: 'sa-org-chart', label: 'Org Chart Overrides' },
    { id: 'sa-health', label: 'Health Monitoring' },
    { id: 'sa-capabilities', label: 'Capabilities Summary' },
  ],
}

const currentSidebarItems = computed(() => sidebarItems[activeTab.value] || [])

const activeSectionId = ref('')
const mobileSidebarOpen = ref(false)

function scrollToSection(id: string) {
  activeSectionId.value = id
  mobileSidebarOpen.value = false
  const el = document.getElementById(id)
  if (el) {
    const offset = 80
    const top = el.getBoundingClientRect().top + window.scrollY - offset
    window.scrollTo({ top, behavior: 'smooth' })
  }
}

function switchTab(key: string) {
  activeTab.value = key
  activeSectionId.value = ''
  nextTick(() => {
    window.scrollTo({ top: 0 })
  })
}

let observer: IntersectionObserver | null = null
let unmounted = false

function setupScrollspy() {
  if (unmounted) return
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && entry.target.id !== activeSectionId.value) {
          activeSectionId.value = entry.target.id
          break
        }
      }
    },
    { rootMargin: '-80px 0px -60% 0px', threshold: 0 },
  )
  const items = currentSidebarItems.value
  for (const item of items) {
    const el = document.getElementById(item.id)
    if (el) observer.observe(el)
  }
}

watch(activeTab, () => {
  nextTick(() => setupScrollspy())
})

watch(mobileSidebarOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

onMounted(() => {
  nextTick(() => setupScrollspy())
})

onUnmounted(() => {
  unmounted = true
  if (observer) {
    observer.disconnect()
    observer = null
  }
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center gap-3 mb-2">
        <BookOpen class="w-7 h-7 text-brand-600" aria-hidden="true" />
        <h1 class="text-3xl font-bold text-foreground">User Guide</h1>
      </div>
      <p class="text-sm text-muted max-w-2xl">
        Learn how to use the AI3L Community platform. Select a guide tab below based on your role.
        Higher roles include all features from lower roles.
      </p>
    </div>

    <!-- Tab bar -->
    <div class="flex flex-wrap gap-1 border-b border-border mb-6" role="tablist">
      <button
        v-for="tab in visibleTabs"
        :key="tab.key"
        role="tab"
        :aria-selected="activeTab === tab.key"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          activeTab === tab.key
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Layout: sidebar + content -->
    <div class="flex gap-8">
      <!-- Desktop sidebar -->
      <nav
        class="hidden lg:block w-56 shrink-0 sticky top-20 self-start max-h-[calc(100vh-6rem)] overflow-y-auto"
      >
        <ul class="space-y-0.5">
          <li v-for="item in currentSidebarItems" :key="item.id">
            <button
              @click="scrollToSection(item.id)"
              class="flex items-center gap-1.5 w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors"
              :class="
                activeSectionId === item.id
                  ? 'bg-brand-50 text-brand-700 font-medium'
                  : 'text-muted hover:text-foreground hover:bg-surface-alt'
              "
            >
              <ChevronRight
                class="w-3 h-3 shrink-0 transition-transform"
                :class="{ 'text-brand-500': activeSectionId === item.id }"
                aria-hidden="true"
              />
              <span class="truncate">{{ item.label }}</span>
            </button>
          </li>
        </ul>
      </nav>

      <!-- Mobile sidebar toggle -->
      <div class="lg:hidden fixed bottom-4 right-4 z-40">
        <button
          @click="mobileSidebarOpen = !mobileSidebarOpen"
          class="bg-brand-600 text-white p-3 rounded-full shadow-lg hover:bg-brand-700 transition"
          aria-label="Toggle table of contents"
        >
          <BookOpen class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>

      <!-- Mobile sidebar drawer -->
      <Transition name="slide">
        <div v-if="mobileSidebarOpen" class="lg:hidden fixed inset-0 z-50 flex">
          <div class="absolute inset-0 bg-black/30" @click="mobileSidebarOpen = false" />
          <div
            class="relative ml-auto w-64 max-w-[80vw] bg-surface h-full shadow-xl overflow-y-auto p-4"
          >
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-foreground">Table of Contents</h3>
              <button
                @click="mobileSidebarOpen = false"
                class="p-1 text-muted hover:text-foreground transition"
                aria-label="Close"
              >
                <X class="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
            <ul class="space-y-0.5">
              <li v-for="item in currentSidebarItems" :key="item.id">
                <button
                  @click="scrollToSection(item.id)"
                  class="flex items-center gap-1.5 w-full text-left px-3 py-2 text-sm rounded-md transition-colors"
                  :class="
                    activeSectionId === item.id
                      ? 'bg-brand-50 text-brand-700 font-medium'
                      : 'text-muted hover:text-foreground hover:bg-surface-alt'
                  "
                >
                  <ChevronRight class="w-3 h-3 shrink-0" aria-hidden="true" />
                  <span>{{ item.label }}</span>
                </button>
              </li>
            </ul>
          </div>
        </div>
      </Transition>

      <!-- Main content -->
      <main class="flex-1 min-w-0">
        <GuestGuideContent v-if="activeTab === 'guest'" />
        <MemberGuideContent v-else-if="activeTab === 'member'" />
        <AdminGuideContent v-else-if="activeTab === 'admin'" />
        <SuperAdminGuideContent v-else-if="activeTab === 'super-admin'" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
