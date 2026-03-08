<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDropdownKeyNav } from '@/composables/useDropdownKeyNav'
import { useLocale } from '@/composables/useLocale'
import type { SupportedLocale } from '@/locales'
import NotificationBell from '@/components/NotificationBell.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { Menu, X, ChevronDown, GraduationCap } from 'lucide-vue-next'

const auth = useAuthStore()
const router = useRouter()
const { t, currentLocale, localeOptions, setLocale } = useLocale()
const mobileMenuOpen = ref(false)
const userDropdownOpen = ref(false)
const adminDropdownOpen = ref(false)

const { handleDropdownKeydown: handleAdminKeydown } = useDropdownKeyNav({
  isOpen: adminDropdownOpen,
  onOpen: () => (adminDropdownOpen.value = true),
  onClose: () => (adminDropdownOpen.value = false),
  wrapperClass: 'admin-dropdown-wrapper',
})

const { handleDropdownKeydown: handleUserKeydown } = useDropdownKeyNav({
  isOpen: userDropdownOpen,
  onOpen: () => (userDropdownOpen.value = true),
  onClose: () => (userDropdownOpen.value = false),
  wrapperClass: 'user-dropdown-wrapper',
})

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
  const target = e.target as HTMLElement
  if (!target.closest('.user-dropdown-wrapper')) {
    userDropdownOpen.value = false
  }
  if (!target.closest('.admin-dropdown-wrapper')) {
    adminDropdownOpen.value = false
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
    :aria-label="t('nav.ariaLabel')"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2" @click="mobileMenuOpen = false">
          <GraduationCap class="w-6 h-6 text-brand-600" aria-hidden="true" />
          <span class="text-lg font-bold text-brand-700">AI3L</span>
        </router-link>

        <!-- Desktop nav links -->
        <div class="hidden lg:flex lg:items-center lg:gap-4">
          <router-link
            to="/forum"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.forum') }}</router-link
          >
          <router-link
            to="/sigs"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.sigs') }}</router-link
          >
          <router-link
            to="/about"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.about') }}</router-link
          >

          <template v-if="auth.isAuthenticated">
            <!-- Admin dropdown -->
            <div
              v-if="auth.isAdmin"
              class="relative admin-dropdown-wrapper"
              @keydown="handleAdminKeydown"
            >
              <button
                @click="adminDropdownOpen = !adminDropdownOpen"
                class="flex items-center gap-1 text-sm text-muted hover:text-foreground transition"
                :aria-expanded="adminDropdownOpen"
              >
                {{ t('nav.admin') }}
                <ChevronDown
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': adminDropdownOpen }"
                  aria-hidden="true"
                />
              </button>

              <Transition name="dropdown">
                <div
                  v-if="adminDropdownOpen"
                  class="absolute left-0 mt-2 w-48 bg-surface border border-border rounded-lg shadow-lg py-1"
                >
                  <router-link
                    to="/admin"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.dashboard') }}
                  </router-link>
                  <router-link
                    to="/admin/users"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.users') }}
                  </router-link>
                  <router-link
                    to="/admin/applications"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.applications') }}
                  </router-link>
                  <router-link
                    to="/admin/reports"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.reports') }}
                  </router-link>
                  <router-link
                    to="/admin/categories"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.categories') }}
                  </router-link>
                  <router-link
                    to="/admin/invite-codes"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.inviteCodes') }}
                  </router-link>
                  <router-link
                    v-if="auth.isSuperAdmin"
                    to="/admin/audit-logs"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition border-t border-border"
                    @click="adminDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.auditLogs') }}
                  </router-link>
                </div>
              </Transition>
            </div>

            <select
              :value="currentLocale"
              class="text-sm bg-transparent border border-border rounded px-2 py-1 text-foreground"
              @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
            >
              <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>

            <NotificationBell />

            <!-- User dropdown -->
            <div class="relative user-dropdown-wrapper" @keydown="handleUserKeydown">
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
                  tabindex="-1"
                >
                  {{ t('nav.profile') }}
                </router-link>
                <button
                  @click="handleLogout"
                  class="block w-full text-left px-4 py-2 text-sm text-danger-600 hover:bg-surface-alt transition"
                  tabindex="-1"
                >
                  {{ t('nav.logOut') }}
                </button>
              </div>
            </div>
          </template>

          <template v-else>
            <select
              :value="currentLocale"
              class="text-sm bg-transparent border border-border rounded px-2 py-1 text-foreground"
              @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
            >
              <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>

            <router-link to="/login" class="text-sm text-muted hover:text-foreground transition"
              >{{ t('nav.logIn') }}</router-link
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
            :aria-label="t('nav.toggleMenu')"
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
            {{ t('nav.forum') }}
          </router-link>
          <router-link
            to="/sigs"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.sigs') }}
          </router-link>

          <router-link
            to="/about"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.about') }}
          </router-link>

          <template v-if="auth.isAuthenticated">
            <template v-if="auth.isAdmin">
              <div class="pt-2 pb-1 px-3 text-xs font-medium text-muted uppercase tracking-wider">
                {{ t('nav.sectionAdmin') }}
              </div>
              <router-link
                to="/admin"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.dashboard') }}</router-link
              >
              <router-link
                to="/admin/users"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.users') }}</router-link
              >
              <router-link
                to="/admin/applications"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.applications') }}</router-link
              >
              <router-link
                to="/admin/reports"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.reports') }}</router-link
              >
              <router-link
                to="/admin/categories"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.categories') }}</router-link
              >
              <router-link
                to="/admin/invite-codes"
                class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
                >{{ t('nav.inviteCodes') }}</router-link
              >
            </template>
            <router-link
              v-if="auth.isSuperAdmin"
              to="/admin/audit-logs"
              class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
              @click="mobileMenuOpen = false"
              >{{ t('nav.auditLogs') }}</router-link
            >

            <div class="pt-2 pb-1 px-3 text-xs font-medium text-muted uppercase tracking-wider">
              {{ t('nav.sectionAccount') }}
            </div>
            <div class="flex items-center gap-2 px-3 py-2">
              <span class="text-sm text-foreground">{{
                auth.user?.display_name || auth.role
              }}</span>
              <BaseBadge :variant="roleBadgeVariant[auth.role || ''] || 'neutral'">
                {{ roleLabels[auth.role || ''] || auth.role }}
              </BaseBadge>
            </div>
            <div class="px-3 py-2">
              <select
                :value="currentLocale"
                class="text-sm bg-transparent border border-border rounded px-2 py-1 text-foreground w-full"
                @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
              >
                <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <router-link
              v-if="!auth.isGuest"
              to="/profile"
              class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
              @click="mobileMenuOpen = false"
            >
              {{ t('nav.profile') }}
            </router-link>
            <button
              @click="handleLogout"
              class="block w-full text-left px-3 py-2 text-sm text-danger-600 hover:bg-surface-alt rounded-lg transition"
            >
              {{ t('nav.logOut') }}
            </button>
          </template>

          <template v-else>
            <div class="pt-3 space-y-2">
              <div class="px-3 py-2">
                <select
                  :value="currentLocale"
                  class="text-sm bg-transparent border border-border rounded px-2 py-1 text-foreground w-full"
                  @change="setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
                >
                  <option v-for="opt in localeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <router-link
                to="/login"
                class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
              >
                {{ t('nav.logIn') }}
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

/* Dropdown animation */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
