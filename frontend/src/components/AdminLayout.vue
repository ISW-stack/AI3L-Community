<script setup lang="ts">
import { ref } from 'vue'
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
} from 'lucide-vue-next'

const auth = useAuthStore()
const sidebarOpen = ref(false)

interface NavItem {
  label: string
  to: string
  icon: typeof LayoutDashboard
  superAdminOnly?: boolean
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/admin', icon: LayoutDashboard },
  { label: 'Users', to: '/admin/users', icon: Users },
  { label: 'Applications', to: '/admin/applications', icon: FileCheck },
  { label: 'Reports', to: '/admin/reports', icon: Flag },
  { label: 'Categories', to: '/admin/categories', icon: FolderOpen },
  { label: 'Invite Codes', to: '/admin/invite-codes', icon: KeyRound },
  { label: 'Contributors', to: '/admin/contributors', icon: Users2, superAdminOnly: true },
  { label: 'Audit Logs', to: '/admin/audit-logs', icon: Shield, superAdminOnly: true },
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
      class="hidden lg:flex fixed top-20 left-8 w-64 h-[calc(100vh-theme(spacing.24))] flex-col bg-surface border border-border rounded-xl shadow-sm z-30"
    >
      <div class="px-6 py-8">
        <h2 class="text-xs font-bold text-muted uppercase tracking-widest">Administration</h2>
      </div>

      <nav class="flex-1 px-3 pb-4 space-y-1 overflow-y-auto">
        <template v-for="item in navItems" :key="item.to">
          <router-link
            v-if="!item.superAdminOnly || auth.isSuperAdmin"
            :to="item.to"
            class="sidebar-link flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg transition text-muted hover:text-foreground hover:bg-surface-alt"
          >
            <component :is="item.icon" class="w-5 h-5 shrink-0" />
            {{ item.label }}
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
        class="fixed inset-y-0 left-0 w-64 bg-surface border-r border-border flex flex-col z-50 lg:hidden"
      >
        <div class="flex items-center justify-between px-4 py-6 border-b border-border">
          <h2 class="text-sm font-semibold uppercase tracking-wider">Administration</h2>

          <button
            @click="closeSidebar"
            class="p-1 text-muted hover:text-foreground transition"
            aria-label="Close sidebar"
          >
            <X class="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <template v-for="item in navItems" :key="item.to">
            <router-link
              v-if="!item.superAdminOnly || auth.isSuperAdmin"
              :to="item.to"
              class="sidebar-link flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg text-muted hover:text-foreground hover:bg-surface-alt"
              @click="closeSidebar"
            >
              <component :is="item.icon" class="w-5 h-5 shrink-0" />
              {{ item.label }}
            </router-link>
          </template>
        </nav>
      </aside>
    </Transition>

    <!-- Main Content -->
    <div class="flex-1 lg:pl-[22rem] pr-8 py-4 [scrollbar-gutter:stable] min-w-0">
      <!-- Mobile header -->
      <div class="lg:hidden sticky top-0 z-20 bg-surface border-b border-border px-4 py-3">
        <button
          @click="toggleSidebar"
          class="flex items-center gap-2 text-sm text-muted hover:text-foreground transition"
          aria-label="Toggle admin sidebar"
        >
          <Menu class="w-5 h-5" aria-hidden="true" />
          <span>Menu</span>
        </button>
      </div>

      <!-- Page -->
      <main class="py-4">
        <div class="w-full">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
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
