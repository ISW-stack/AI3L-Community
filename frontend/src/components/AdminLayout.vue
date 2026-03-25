<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard,
  Users,
  FileCheck,
  Flag,
  FolderOpen,
  KeyRound,
  Shield,
  Users2,
  Menu,
  X,
  Ban,
  Settings,
  HardDriveDownload,
} from 'lucide-vue-next'

const { t } = useI18n()
const auth = useAuthStore()
const sidebarOpen = ref(false)

interface NavItem {
  labelKey: string
  to: string
  icon: typeof LayoutDashboard
  superAdminOnly?: boolean
}

const navItems: NavItem[] = [
  { labelKey: 'nav.dashboard', to: '/admin', icon: LayoutDashboard },
  { labelKey: 'nav.users', to: '/admin/users', icon: Users },
  { labelKey: 'nav.applications', to: '/admin/applications', icon: FileCheck },
  { labelKey: 'nav.reports', to: '/admin/reports', icon: Flag },
  { labelKey: 'nav.categories', to: '/admin/categories', icon: FolderOpen },
  { labelKey: 'nav.inviteCodes', to: '/admin/invite-codes', icon: KeyRound },
  { labelKey: 'nav.contributors', to: '/admin/contributors', icon: Users2, superAdminOnly: true },
  { labelKey: 'nav.auditLogs', to: '/admin/audit-logs', icon: Shield, superAdminOnly: true },
  { labelKey: 'nav.ipBans', to: '/admin/ip-bans', icon: Ban, superAdminOnly: true },
  {
    labelKey: 'nav.siteSettings',
    to: '/admin/site-settings',
    icon: Settings,
    superAdminOnly: true,
  },
  {
    labelKey: 'nav.dataExport',
    to: '/admin/data-export',
    icon: HardDriveDownload,
    superAdminOnly: true,
  },
]

function closeSidebar() {
  sidebarOpen.value = false
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}
</script>

<template>
  <div class="min-h-screen bg-surface-alt/30">
    <!-- Desktop Sidebar -->
    <aside
      class="hidden lg:flex fixed top-20 left-layout w-64 h-[calc(100vh-theme(spacing.24))] flex-col bg-surface border border-border rounded-xl shadow-sm z-30"
    >
      <div class="px-6 py-8">
        <h2 class="text-xs font-bold text-muted uppercase tracking-widest">
          {{ t('admin.layout.title') }}
        </h2>
      </div>

      <nav class="flex-1 px-3 pb-4 space-y-1 overflow-y-auto">
        <template v-for="item in navItems" :key="item.to">
          <router-link
            v-if="!item.superAdminOnly || auth.isSuperAdmin"
            :to="item.to"
            class="sidebar-link flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition text-muted hover:text-foreground hover:bg-surface-alt"
          >
            <component :is="item.icon" class="w-5 h-5 shrink-0" />
            {{ t(item.labelKey) }}
          </router-link>
        </template>
      </nav>
    </aside>

    <!-- Mobile overlay -->
    <Transition name="sidebar-overlay">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 bg-black/30 z-40 lg:hidden"
        @click="closeSidebar"
      />
    </Transition>

    <!-- Mobile sidebar -->
    <Transition name="sidebar-panel">
      <aside
        v-if="sidebarOpen"
        class="mobile-sidebar fixed inset-y-0 left-0 w-[80vw] max-w-[300px] bg-surface border-r border-border flex flex-col z-50 lg:hidden overflow-y-auto"
      >
        <div class="flex items-center justify-between px-4 py-6 border-b border-border">
          <h2 class="text-sm font-semibold uppercase tracking-wider">
            {{ t('admin.layout.title') }}
          </h2>

          <button
            @click="closeSidebar"
            class="p-1 text-muted hover:text-foreground transition"
            :aria-label="t('admin.layout.closeSidebar')"
          >
            <X class="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <template v-for="item in navItems" :key="item.to">
            <router-link
              v-if="!item.superAdminOnly || auth.isSuperAdmin"
              :to="item.to"
              class="sidebar-link flex items-center gap-3 px-3 py-3 text-sm rounded-lg text-muted hover:text-foreground hover:bg-surface-alt active:bg-surface-alt touch-manipulation"
              @click="closeSidebar"
            >
              <component :is="item.icon" class="w-5 h-5 shrink-0" />
              {{ t(item.labelKey) }}
            </router-link>
          </template>
        </nav>
      </aside>
    </Transition>

    <!-- Main Content -->
    <div
      class="flex-1 lg:pl-[calc(var(--spacing-layout)+18rem)] lg:pr-layout py-4 [scrollbar-gutter:stable] min-w-0"
    >
      <!-- Mobile header -->
      <div class="lg:hidden sticky top-0 z-20 bg-surface border-b border-border px-4 py-3">
        <button
          @click="toggleSidebar"
          class="flex items-center gap-2 text-sm text-muted hover:text-foreground active:text-foreground transition p-1 -ml-1 rounded-md touch-manipulation"
          :aria-label="t('admin.layout.toggleSidebar')"
        >
          <Menu class="w-5 h-5" aria-hidden="true" />
          <span>{{ t('admin.layout.menu') }}</span>
        </button>
      </div>

      <!-- Page -->
      <main class="px-4 lg:px-0 py-4">
        <div class="w-full">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Safe area inset for mobile sidebar (notch / dynamic island devices) */
.mobile-sidebar {
  padding-top: env(safe-area-inset-top, 0px);
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.sidebar-link.router-link-active {
  background-color: var(--color-brand-50);
  color: var(--color-brand-700);
  font-weight: 500;
}

.sidebar-overlay-enter-active,
.sidebar-overlay-leave-active {
  transition: opacity 0.2s ease;
}

.sidebar-overlay-enter-from,
.sidebar-overlay-leave-to {
  opacity: 0;
}

.sidebar-panel-enter-active,
.sidebar-panel-leave-active {
  transition: transform 0.2s ease;
}

.sidebar-panel-enter-from,
.sidebar-panel-leave-to {
  transform: translateX(-100%);
}
</style>
