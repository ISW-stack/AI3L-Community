<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="border-t border-border bg-surface mt-auto">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2">
        <p class="text-sm text-muted">{{ t('footer.copyright') }}</p>
        <p class="text-sm text-muted">{{ t('footer.tagline') }}</p>
      </div>
    </div>
  </footer>
</template>
