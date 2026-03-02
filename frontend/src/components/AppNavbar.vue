<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationBell from '@/components/NotificationBell.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { Menu, X, ChevronDown } from 'lucide-vue-next'

const auth = useAuthStore()
const router = useRouter()
const mobileMenuOpen = ref(false)
const userDropdownOpen = ref(false)

const roleLabels: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  MEMBER: 'Member',
  GUEST: 'Guest',
}

const roleBadgeVariant: Record<string, 'danger' | 'orange' | 'brand' | 'neutral'> = {
  SUPER_ADMIN: 'danger',
  ADMIN: 'orange',
  MEMBER: 'brand',
  GUEST: 'neutral',
}

async function handleLogout() {
  userDropdownOpen.value = false
  mobileMenuOpen.value = false
  await auth.logout()
  router.push('/login')
}

function handleClickOutside(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest('.user-dropdown-wrapper')
  if (!el) {
    userDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <nav
    class="sticky top-0 z-50 backdrop-blur-md bg-surface/80 border-b border-border"
    aria-label="Main navigation"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-14 items-center">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2" @click="mobileMenuOpen = false">
          <span class="text-lg font-bold text-brand-700">AI3L Community</span>
        </router-link>

        <!-- Desktop nav links -->
        <div class="hidden lg:flex lg:items-center lg:gap-4">
          <router-link
            to="/forum"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >Forum</router-link
          >
          <router-link
            to="/sigs"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >SIGs</router-link
          >

          <template v-if="auth.isAuthenticated">
            <template v-if="auth.isAdmin">
              <router-link
                to="/admin"
                class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
                >Dashboard</router-link
              >
              <router-link
                to="/admin/users"
                class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
                >Users</router-link
              >
              <router-link
                to="/admin/applications"
                class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
                >Applications</router-link
              >
              <router-link
                to="/admin/reports"
                class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
                >Reports</router-link
              >
              <router-link
                to="/admin/invite-codes"
                class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
                >Invite Codes</router-link
              >
            </template>
            <router-link
              v-if="auth.isSuperAdmin"
              to="/admin/audit-logs"
              class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
              >Audit Logs</router-link
            >

            <NotificationBell />

            <!-- User dropdown -->
            <div class="relative user-dropdown-wrapper">
              <button
                @click="userDropdownOpen = !userDropdownOpen"
                class="flex items-center gap-2 text-sm text-foreground hover:text-foreground/80 transition"
                :aria-expanded="userDropdownOpen"
              >
                <span>{{ auth.user?.display_name || auth.role }}</span>
                <BaseBadge :variant="roleBadgeVariant[auth.role || ''] || 'neutral'">
                  {{ roleLabels[auth.role || ''] || auth.role }}
                </BaseBadge>
                <ChevronDown class="w-4 h-4 text-muted" aria-hidden="true" />
              </button>

              <div
                v-if="userDropdownOpen"
                class="absolute right-0 mt-2 w-48 bg-surface border border-border rounded-lg shadow-lg py-1"
              >
                <router-link
                  v-if="!auth.isGuest"
                  to="/profile"
                  class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                  @click="userDropdownOpen = false"
                >
                  Profile
                </router-link>
                <button
                  @click="handleLogout"
                  class="block w-full text-left px-4 py-2 text-sm text-danger-600 hover:bg-surface-alt transition"
                >
                  Log Out
                </button>
              </div>
            </div>
          </template>

          <template v-else>
            <router-link to="/login" class="text-sm text-muted hover:text-foreground transition"
              >Log In</router-link
            >
            <router-link
              to="/register"
              class="text-sm bg-brand-600 text-white px-4 py-1.5 rounded-lg hover:bg-brand-700 transition"
            >
              Sign Up
            </router-link>
          </template>
        </div>

        <!-- Mobile right side: notification bell + hamburger -->
        <div class="flex items-center gap-3 lg:hidden">
          <NotificationBell v-if="auth.isAuthenticated" />
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="p-1 text-muted hover:text-foreground transition"
            :aria-expanded="mobileMenuOpen"
            aria-label="Toggle menu"
          >
            <Menu v-if="!mobileMenuOpen" class="w-6 h-6" aria-hidden="true" />
            <X v-else class="w-6 h-6" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile menu panel -->
    <Transition name="mobile-menu">
      <div
        v-if="mobileMenuOpen"
        class="lg:hidden border-t border-border bg-surface/95 backdrop-blur-md"
      >
        <div class="px-4 py-3 space-y-1">
          <router-link
            to="/forum"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            Forum
          </router-link>
          <router-link
            to="/sigs"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            SIGs
          </router-link>

          <template v-if="auth.isAuthenticated">
            <template v-if="auth.isAdmin">
              <div class="pt-2 pb-1 px-3 text-xs font-medium text-muted uppercase tracking-wider">
                Admin
              </div>
              <router-link
                to="/admin"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >Dashboard</router-link
              >
              <router-link
                to="/admin/users"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >Users</router-link
              >
              <router-link
                to="/admin/applications"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >Applications</router-link
              >
              <router-link
                to="/admin/reports"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >Reports</router-link
              >
              <router-link
                to="/admin/invite-codes"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >Invite Codes</router-link
              >
            </template>
            <router-link
              v-if="auth.isSuperAdmin"
              to="/admin/audit-logs"
              class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
              @click="mobileMenuOpen = false"
              >Audit Logs</router-link
            >

            <div class="pt-2 pb-1 px-3 text-xs font-medium text-muted uppercase tracking-wider">
              Account
            </div>
            <div class="flex items-center gap-2 px-3 py-2">
              <span class="text-sm text-foreground">{{
                auth.user?.display_name || auth.role
              }}</span>
              <BaseBadge :variant="roleBadgeVariant[auth.role || ''] || 'neutral'">
                {{ roleLabels[auth.role || ''] || auth.role }}
              </BaseBadge>
            </div>
            <router-link
              v-if="!auth.isGuest"
              to="/profile"
              class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
              @click="mobileMenuOpen = false"
            >
              Profile
            </router-link>
            <button
              @click="handleLogout"
              class="block w-full text-left px-3 py-2 text-sm text-danger-600 hover:bg-surface-alt rounded-lg transition"
            >
              Log Out
            </button>
          </template>

          <template v-else>
            <div class="pt-3 space-y-2">
              <router-link
                to="/login"
                class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
              >
                Log In
              </router-link>
              <router-link
                to="/register"
                class="block text-center text-sm bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 transition"
                @click="mobileMenuOpen = false"
              >
                Sign Up
              </router-link>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </nav>
</template>

<style scoped>
/* Desktop active link */
.nav-link-desktop.router-link-active {
  color: var(--color-brand-600);
  font-weight: 600;
}

/* Mobile active link */
.nav-link-mobile.router-link-active {
  background-color: var(--color-brand-50);
  color: var(--color-brand-700);
  font-weight: 500;
}

.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
  max-height: 0;
}
.mobile-menu-enter-to,
.mobile-menu-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
