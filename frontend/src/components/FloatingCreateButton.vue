<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { PenLine } from 'lucide-vue-next'

defineProps<{
  to: string
}>()

const { t } = useI18n()
const auth = useAuthStore()
</script>

<template>
  <router-link
    v-if="auth.isAuthenticated && !auth.isGuest"
    :to="to"
    class="fab"
    :aria-label="t('forum.newPost')"
    :title="t('forum.newPost')"
  >
    <PenLine class="w-5 h-5" />
    <span class="fab-label">{{ t('forum.newPost') }}</span>
  </router-link>
</template>

<style scoped>
.fab {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-radius: 9999px;
  background-color: var(--color-brand-600);
  color: white;
  font-weight: 600;
  font-size: 0.875rem;
  box-shadow:
    0 4px 14px -2px rgb(0 0 0 / 0.2),
    0 2px 6px -1px rgb(0 0 0 / 0.1);
  transition: all 0.2s ease;
  text-decoration: none;
}

.fab:hover {
  background-color: var(--color-brand-700);
  box-shadow:
    0 6px 20px -2px rgb(0 0 0 / 0.25),
    0 4px 8px -1px rgb(0 0 0 / 0.15);
  transform: translateY(-1px);
}

.fab:active {
  transform: translateY(0);
}

/* On small screens, collapse to icon-only */
@media (max-width: 640px) {
  .fab {
    padding: 0.875rem;
  }
  .fab-label {
    display: none;
  }
}
</style>
