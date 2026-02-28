<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationBell from '@/components/NotificationBell.vue'

const auth = useAuthStore()
const router = useRouter()
const menuOpen = ref(false)

const roleLabels: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  MEMBER: 'Member',
  GUEST: 'Guest',
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-14 items-center">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2">
          <span class="text-lg font-bold text-blue-700">AI3L Community</span>
        </router-link>

        <!-- Right side -->
        <div class="flex items-center gap-4">
          <!-- Forum link (visible to all) -->
          <router-link to="/forum" class="text-sm text-gray-600 hover:text-gray-900">Forum</router-link>
          <router-link to="/sigs" class="text-sm text-gray-600 hover:text-gray-900">SIGs</router-link>

          <template v-if="auth.isAuthenticated">
            <!-- Admin links -->
            <template v-if="auth.isAdmin">
              <router-link
                to="/admin/users"
                class="text-sm text-gray-600 hover:text-gray-900"
              >
                Users
              </router-link>
              <router-link
                to="/admin/applications"
                class="text-sm text-gray-600 hover:text-gray-900"
              >
                Applications
              </router-link>
              <router-link
                to="/admin/reports"
                class="text-sm text-gray-600 hover:text-gray-900"
              >
                Reports
              </router-link>
            </template>
            <router-link
              v-if="auth.isSuperAdmin"
              to="/admin/audit-logs"
              class="text-sm text-gray-600 hover:text-gray-900"
            >
              Audit Logs
            </router-link>

            <!-- Notification bell -->
            <NotificationBell />

            <!-- User dropdown -->
            <div class="relative">
              <button
                @click="menuOpen = !menuOpen"
                class="flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900"
              >
                <span>{{ auth.user?.display_name || auth.role }}</span>
                <span
                  class="text-xs px-1.5 py-0.5 rounded-full"
                  :class="{
                    'bg-red-100 text-red-700': auth.isSuperAdmin,
                    'bg-orange-100 text-orange-700': auth.role === 'ADMIN',
                    'bg-blue-100 text-blue-700': auth.role === 'MEMBER',
                    'bg-gray-100 text-gray-600': auth.isGuest,
                  }"
                >
                  {{ roleLabels[auth.role || ''] || auth.role }}
                </span>
              </button>

              <div
                v-if="menuOpen"
                class="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg py-1"
                @click="menuOpen = false"
              >
                <router-link
                  v-if="!auth.isGuest"
                  to="/profile"
                  class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Profile
                </router-link>
                <button
                  @click="handleLogout"
                  class="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
                >
                  Log Out
                </button>
              </div>
            </div>
          </template>

          <template v-else>
            <router-link to="/login" class="text-sm text-gray-600 hover:text-gray-900">Log In</router-link>
            <router-link
              to="/register"
              class="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700 transition"
            >
              Sign Up
            </router-link>
          </template>
        </div>
      </div>
    </div>
  </nav>
</template>
