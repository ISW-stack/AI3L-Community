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
  <div class="flex min-h-[calc(100vh-theme(spacing.16))]">
    <!-- Desktop sidebar -->
    <aside class="hidden lg:flex lg:flex-col lg:w-56 lg:shrink-0 bg-surface border-r border-border">
      <div class="px-4 py-4">
        <h2 class="text-sm font-semibold text-foreground uppercase tracking-wider">
          Administration
        </h2>
      </div>
      <nav class="flex-1 px-2 pb-4 space-y-1">
        <template v-for="item in navItems" :key="item.to">
          <router-link
            v-if="!item.superAdminOnly || auth.isSuperAdmin"
            :to="item.to"
            class="sidebar-link flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition text-muted hover:text-foreground hover:bg-surface-alt"
            @click="closeSidebar"
          >
            <component :is="item.icon" class="w-5 h-5 shrink-0" aria-hidden="true" />
            {{ item.label }}
          </router-link>
        </template>
      </nav>
    </aside>

    <!-- Mobile sidebar overlay -->
    <Transition name="sidebar-overlay">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-40 bg-foreground/30 lg:hidden"
        @click="closeSidebar"
      />
    </Transition>

    <!-- Mobile sidebar panel -->
    <Transition name="sidebar-panel">
      <aside
        v-if="sidebarOpen"
        class="fixed inset-y-0 left-0 z-50 flex flex-col w-56 bg-surface border-r border-border lg:hidden"
      >
        <div class="flex items-center justify-between px-4 py-4">
          <h2 class="text-sm font-semibold text-foreground uppercase tracking-wider">
            Administration
          </h2>
          <button
            @click="closeSidebar"
            class="p-1 text-muted hover:text-foreground transition"
            aria-label="Close sidebar"
          >
            <X class="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
        <nav class="flex-1 px-2 pb-4 space-y-1">
          <template v-for="item in navItems" :key="item.to">
            <router-link
              v-if="!item.superAdminOnly || auth.isSuperAdmin"
              :to="item.to"
              class="sidebar-link flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition text-muted hover:text-foreground hover:bg-surface-alt"
              @click="closeSidebar"
            >
              <component :is="item.icon" class="w-5 h-5 shrink-0" aria-hidden="true" />
              {{ item.label }}
            </router-link>
          </template>
        </nav>
      </aside>
    </Transition>

    <!-- Main content -->
    <div class="flex-1 min-w-0">
      <!-- Mobile toggle button -->
      <div class="lg:hidden px-4 py-2 border-b border-border">
        <button
          @click="toggleSidebar"
          class="flex items-center gap-2 text-sm text-muted hover:text-foreground transition"
          aria-label="Toggle admin sidebar"
        >
          <Menu class="w-5 h-5" aria-hidden="true" />
          <span>Menu</span>
        </button>
      </div>
      <router-view />
    </div>
  </div>
</template>

<style scoped>
/* Active sidebar link */
.sidebar-link.router-link-active {
  background-color: var(--color-brand-50);
  color: var(--color-brand-700);
  font-weight: 500;
}

/* Overlay transition */
.sidebar-overlay-enter-active,
.sidebar-overlay-leave-active {
  transition: opacity 0.2s ease;
}
.sidebar-overlay-enter-from,
.sidebar-overlay-leave-to {
  opacity: 0;
}

/* Panel slide transition */
.sidebar-panel-enter-active,
.sidebar-panel-leave-active {
  transition: transform 0.2s ease;
}
.sidebar-panel-enter-from,
.sidebar-panel-leave-to {
  transform: translateX(-100%);
}
</style>
