<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDropdownKeyNav } from '@/composables/useDropdownKeyNav'
import { useLocale } from '@/composables/useLocale'
import NotificationBell from '@/components/NotificationBell.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import { Menu, X, ChevronDown, MessageSquare, BookOpen } from 'lucide-vue-next'
import { useDMStore } from '@/stores/dm'

const auth = useAuthStore()
const dmStore = useDMStore()
const router = useRouter()
const { t } = useLocale()
const mobileMenuOpen = ref(false)
const userDropdownOpen = ref(false)
const adminDropdownOpen = ref(false)
const aboutDropdownOpen = ref(false)
const mobileAdminOpen = ref(false)
const mobileAboutOpen = ref(false)

watch(mobileMenuOpen, (open) => {
  if (!open) {
    mobileAdminOpen.value = false
    mobileAboutOpen.value = false
  }
})

const { handleDropdownKeydown: handleAdminKeydown } = useDropdownKeyNav({
  isOpen: adminDropdownOpen,
  onOpen: () => (adminDropdownOpen.value = true),
  onClose: () => (adminDropdownOpen.value = false),
  wrapperClass: 'admin-dropdown-wrapper',
})

const { handleDropdownKeydown: handleAboutKeydown } = useDropdownKeyNav({
  isOpen: aboutDropdownOpen,
  onOpen: () => (aboutDropdownOpen.value = true),
  onClose: () => (aboutDropdownOpen.value = false),
  wrapperClass: 'about-dropdown-wrapper',
})

const { handleDropdownKeydown: handleUserKeydown } = useDropdownKeyNav({
  isOpen: userDropdownOpen,
  onOpen: () => (userDropdownOpen.value = true),
  onClose: () => (userDropdownOpen.value = false),
  wrapperClass: 'user-dropdown-wrapper',
})

const userInitials = computed(() => {
  const trimmed = (auth.user?.display_name || '').trim()
  if (!trimmed) return '?'
  const parts = trimmed.split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return trimmed.slice(0, 2).toUpperCase()
})

const roleLabels = computed<Record<string, string>>(() => ({
  SUPER_ADMIN: t('common.role.superAdmin'),
  ADMIN: t('common.role.admin'),
  MEMBER: t('common.role.member'),
  GUEST: t('common.role.guest'),
}))

const roleBadgeVariant: Record<string, 'danger' | 'orange' | 'brand' | 'neutral'> = {
  SUPER_ADMIN: 'danger',
  ADMIN: 'orange',
  MEMBER: 'brand',
  GUEST: 'neutral',
}

async function handleLogout() {
  userDropdownOpen.value = false
  mobileMenuOpen.value = false
  mobileAdminOpen.value = false
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
  if (!target.closest('.about-dropdown-wrapper')) {
    aboutDropdownOpen.value = false
  }
}

function handleEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    userDropdownOpen.value = false
    adminDropdownOpen.value = false
    aboutDropdownOpen.value = false
    mobileMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleEscapeKey)
  if (auth.isAuthenticated && !auth.isGuest) {
    dmStore.fetchUnreadCount()
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleEscapeKey)
})
</script>

<template>
  <nav
    class="sticky top-0 z-50 backdrop-blur-md bg-surface/80 border-b border-border"
    style="padding-top: env(safe-area-inset-top, 0px)"
    :aria-label="t('nav.ariaLabel')"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2" @click="mobileMenuOpen = false">
          <img src="/images/logo.png" alt="AI3L" class="h-12 w-auto" />
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
            to="/qa"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.qa') }}</router-link
          >
          <router-link
            to="/sigs"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.sigs') }}</router-link
          >
          <router-link
            to="/albums"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.albums') }}</router-link
          >
          <router-link
            to="/forms"
            class="nav-link-desktop text-sm text-muted hover:text-foreground transition"
            >{{ t('nav.forms') }}</router-link
          >

          <template v-if="auth.isAuthenticated && !auth.isGuest">
            <!-- About dropdown -->
            <div class="relative about-dropdown-wrapper" @keydown="handleAboutKeydown">
              <button
                @click="aboutDropdownOpen = !aboutDropdownOpen"
                class="flex items-center gap-1 text-sm text-muted hover:text-foreground transition"
                :aria-expanded="aboutDropdownOpen"
              >
                {{ t('nav.about') }}
                <ChevronDown
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': aboutDropdownOpen }"
                  aria-hidden="true"
                />
              </button>

              <Transition name="dropdown">
                <div
                  v-if="aboutDropdownOpen"
                  class="absolute right-0 sm:left-0 sm:right-auto mt-2 w-48 max-w-[calc(100vw-2rem)] bg-surface border border-border rounded-lg shadow-lg py-1"
                >
                  <router-link
                    to="/about"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="aboutDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.introduction') }}
                  </router-link>
                  <router-link
                    to="/about/org-chart"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="aboutDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.orgChart') }}
                  </router-link>
                  <router-link
                    to="/about/members"
                    class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="aboutDropdownOpen = false"
                    tabindex="-1"
                  >
                    {{ t('nav.members') }}
                  </router-link>
                </div>
              </Transition>
            </div>
          </template>

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
                  class="absolute right-0 sm:left-0 sm:right-auto mt-2 w-48 max-w-[calc(100vw-2rem)] bg-surface border border-border rounded-lg shadow-lg py-1"
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

            <!-- DM Badge -->
            <router-link
              v-if="!auth.isGuest"
              to="/messages"
              class="relative p-2 text-muted hover:text-foreground transition"
              aria-label="Messages"
            >
              <MessageSquare class="w-5 h-5" aria-hidden="true" />
              <span
                v-if="dmStore.unreadCount > 0"
                class="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[11px] font-bold text-white bg-danger-500 rounded-full"
              >
                {{ dmStore.unreadCount > 99 ? '99+' : dmStore.unreadCount }}
              </span>
            </router-link>

            <NotificationBell />

            <!-- User dropdown -->
            <div class="relative user-dropdown-wrapper" @keydown="handleUserKeydown">
              <button
                @click="userDropdownOpen = !userDropdownOpen"
                class="flex items-center gap-2 transition"
                :aria-expanded="userDropdownOpen"
                :aria-label="t('nav.sectionAccount')"
                :title="auth.user?.display_name || ''"
              >
                <span
                  v-if="auth.user?.avatar_url"
                  class="w-8 h-8 rounded-full overflow-hidden ring-2 ring-transparent hover:ring-brand-200 transition"
                >
                  <img
                    :src="auth.user.avatar_url"
                    :alt="auth.user.display_name"
                    class="w-full h-full object-cover"
                  />
                </span>
                <span
                  v-else
                  class="flex items-center justify-center w-8 h-8 rounded-full bg-brand-100 text-brand-700 text-xs font-semibold ring-2 ring-transparent hover:ring-brand-200 transition"
                >
                  {{ userInitials }}
                </span>
                <ChevronDown
                  class="w-3.5 h-3.5 text-muted transition-transform"
                  :class="{ 'rotate-180': userDropdownOpen }"
                  aria-hidden="true"
                />
              </button>

              <Transition name="dropdown">
                <div
                  v-if="userDropdownOpen"
                  class="absolute right-0 mt-2 w-56 max-w-[calc(100vw-1rem)] bg-surface border border-border rounded-lg shadow-lg py-1"
                >
                  <!-- User info header -->
                  <div class="px-4 py-2 border-b border-border">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-foreground truncate">{{
                        auth.user?.display_name || '—'
                      }}</span>
                      <BaseBadge
                        :variant="roleBadgeVariant[auth.role || ''] || 'neutral'"
                        size="sm"
                      >
                        {{ roleLabels[auth.role || ''] || auth.role }}
                      </BaseBadge>
                    </div>
                  </div>

                  <template v-if="!auth.isGuest">
                    <router-link
                      to="/profile"
                      class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                      @click="userDropdownOpen = false"
                      tabindex="-1"
                    >
                      {{ t('nav.profile') }}
                    </router-link>
                    <router-link
                      to="/friends"
                      class="block px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                      @click="userDropdownOpen = false"
                      tabindex="-1"
                    >
                      {{ t('nav.friends') }}
                    </router-link>
                  </template>

                  <router-link
                    to="/guide"
                    class="flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-surface-alt transition"
                    @click="userDropdownOpen = false"
                    tabindex="-1"
                  >
                    <BookOpen class="w-3.5 h-3.5" aria-hidden="true" />
                    {{ t('nav.userGuide') }}
                  </router-link>

                  <div class="border-t border-border my-1" />

                  <div class="px-4 py-2">
                    <LanguageSwitcher variant="form" />
                  </div>

                  <div class="border-t border-border my-1" />

                  <button
                    @click="handleLogout"
                    class="block w-full text-left px-4 py-2 text-sm text-danger-600 hover:bg-surface-alt transition"
                    tabindex="-1"
                  >
                    {{ t('nav.logOut') }}
                  </button>
                </div>
              </Transition>
            </div>
          </template>

          <template v-else>
            <LanguageSwitcher />

            <router-link to="/login" class="text-sm text-muted hover:text-foreground transition">{{
              t('nav.logIn')
            }}</router-link>
            <router-link
              to="/register"
              class="text-sm bg-brand-600 text-white px-4 py-1.5 rounded-lg hover:bg-brand-700 transition"
            >
              {{ t('nav.signUp') }}
            </router-link>
          </template>
        </div>

        <!-- Mobile right side: notification bell + hamburger -->
        <div class="flex items-center gap-1.5 lg:hidden">
          <router-link
            v-if="auth.isAuthenticated && !auth.isGuest"
            to="/messages"
            class="relative p-2.5 text-muted hover:text-foreground transition"
            aria-label="Messages"
          >
            <MessageSquare class="w-5 h-5" aria-hidden="true" />
            <span
              v-if="dmStore.unreadCount > 0"
              class="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[11px] font-bold text-white bg-danger-500 rounded-full"
            >
              {{ dmStore.unreadCount > 99 ? '99+' : dmStore.unreadCount }}
            </span>
          </router-link>
          <NotificationBell v-if="auth.isAuthenticated" />
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="p-2.5 text-muted hover:text-foreground transition"
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
            to="/qa"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.qa') }}
          </router-link>
          <router-link
            to="/sigs"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.sigs') }}
          </router-link>
          <router-link
            to="/albums"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.albums') }}
          </router-link>
          <router-link
            to="/forms"
            class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.forms') }}
          </router-link>

          <template v-if="auth.isAuthenticated">
            <template v-if="auth.isAdmin">
              <button
                type="button"
                @click="mobileAdminOpen = !mobileAdminOpen"
                class="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider hover:bg-surface-alt rounded-lg transition"
                :aria-expanded="mobileAdminOpen"
              >
                {{ t('nav.sectionAdmin') }}
                <ChevronDown
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': mobileAdminOpen }"
                  aria-hidden="true"
                />
              </button>
              <Transition name="mobile-admin">
                <div v-if="mobileAdminOpen" class="space-y-1">
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
                  <router-link
                    v-if="auth.isSuperAdmin"
                    to="/admin/audit-logs"
                    class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition border-t border-border"
                    @click="mobileMenuOpen = false"
                    >{{ t('nav.auditLogs') }}</router-link
                  >
                </div>
              </Transition>
            </template>

            <!-- About accordion (mobile) -->
            <template v-if="!auth.isGuest">
              <button
                type="button"
                @click="mobileAboutOpen = !mobileAboutOpen"
                class="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-muted uppercase tracking-wider hover:bg-surface-alt rounded-lg transition"
                :aria-expanded="mobileAboutOpen"
              >
                {{ t('nav.about') }}
                <ChevronDown
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': mobileAboutOpen }"
                  aria-hidden="true"
                />
              </button>
              <Transition name="mobile-admin">
                <div v-if="mobileAboutOpen" class="space-y-1">
                  <router-link
                    to="/about"
                    class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                    @click="mobileMenuOpen = false"
                    >{{ t('nav.introduction') }}</router-link
                  >
                  <router-link
                    to="/about/org-chart"
                    class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                    @click="mobileMenuOpen = false"
                    >{{ t('nav.orgChart') }}</router-link
                  >
                  <router-link
                    to="/about/members"
                    class="nav-link-mobile block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                    @click="mobileMenuOpen = false"
                    >{{ t('nav.members') }}</router-link
                  >
                </div>
              </Transition>
            </template>

            <div class="pt-2 pb-1 px-3 text-xs font-medium text-muted uppercase tracking-wider">
              {{ t('nav.sectionAccount') }}
            </div>
            <div class="flex items-center gap-2 px-3 py-2">
              <BaseBadge :variant="roleBadgeVariant[auth.role || ''] || 'neutral'">
                {{ roleLabels[auth.role || ''] || auth.role }}
              </BaseBadge>
              <span class="text-sm text-foreground">{{ auth.user?.display_name || '—' }}</span>
            </div>
            <div class="px-3 py-2">
              <LanguageSwitcher variant="form" />
            </div>
            <template v-if="!auth.isGuest">
              <router-link
                to="/profile"
                class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
              >
                {{ t('nav.profile') }}
              </router-link>
              <router-link
                to="/friends"
                class="block px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
                @click="mobileMenuOpen = false"
              >
                {{ t('nav.friends') }}
              </router-link>
            </template>
            <router-link
              to="/guide"
              class="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface-alt rounded-lg transition"
              @click="mobileMenuOpen = false"
            >
              <BookOpen class="w-4 h-4" aria-hidden="true" />
              {{ t('nav.userGuide') }}
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
                <LanguageSwitcher variant="form" />
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
                {{ t('nav.signUp') }}
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

/* Mobile admin accordion animation */
.mobile-admin-enter-active,
.mobile-admin-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.mobile-admin-enter-from,
.mobile-admin-leave-to {
  opacity: 0;
  max-height: 0;
}
.mobile-admin-enter-to,
.mobile-admin-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>
