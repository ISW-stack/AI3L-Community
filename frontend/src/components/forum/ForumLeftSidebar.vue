<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listMySigs } from '@/api/sigs'
import type { Sig } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import { Home, Users, PenSquare, Bell } from 'lucide-vue-next'

const { t } = useI18n()
const auth = useAuthStore()
const mySigs = ref<Sig[]>([])

onMounted(async () => {
  if (auth.isAuthenticated && !auth.isGuest) {
    try {
      mySigs.value = await listMySigs()
    } catch {
      // silent — sidebar is non-critical
    }
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Quick Links -->
    <BaseCard>
      <h3 class="text-sm font-semibold text-foreground mb-3">
        {{ t('forum.leftSidebar.quickLinks') }}
      </h3>
      <nav class="space-y-1">
        <router-link
          to="/forum"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-foreground hover:bg-surface-alt transition"
        >
          <Home class="w-4 h-4 text-muted" />
          {{ t('forum.leftSidebar.home') }}
        </router-link>
        <router-link
          to="/sigs"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-foreground hover:bg-surface-alt transition"
        >
          <Users class="w-4 h-4 text-muted" />
          {{ t('forum.leftSidebar.allSigs') }}
        </router-link>
        <router-link
          v-if="auth.isAuthenticated && !auth.isGuest"
          to="/forum/create"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-foreground hover:bg-surface-alt transition"
        >
          <PenSquare class="w-4 h-4 text-muted" />
          {{ t('forum.leftSidebar.createPost') }}
        </router-link>
        <router-link
          v-if="auth.isAuthenticated && !auth.isGuest"
          to="/notifications"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-foreground hover:bg-surface-alt transition"
        >
          <Bell class="w-4 h-4 text-muted" />
          {{ t('forum.leftSidebar.notifications') }}
        </router-link>
      </nav>
    </BaseCard>

    <!-- My SIGs -->
    <BaseCard v-if="mySigs.length > 0">
      <h3 class="text-sm font-semibold text-foreground mb-3">
        {{ t('forum.leftSidebar.mySigs') }}
      </h3>
      <ul class="space-y-1">
        <li v-for="sig in mySigs" :key="sig.id">
          <router-link
            :to="`/sigs/${sig.id}`"
            class="block px-3 py-2 rounded-lg text-sm text-foreground hover:bg-surface-alt transition truncate"
          >
            {{ sig.name }}
          </router-link>
        </li>
      </ul>
    </BaseCard>
  </div>
</template>
