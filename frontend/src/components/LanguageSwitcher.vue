<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Globe, ChevronDown, ChevronRight, Check } from 'lucide-vue-next'
import { useLocale } from '@/composables/useLocale'
import { LOCALE_GROUPS, LOCALE_OPTIONS, type SupportedLocale } from '@/locales'

const props = withDefaults(
  defineProps<{
    variant?: 'compact' | 'form'
  }>(),
  { variant: 'compact' },
)

const { t, currentLocale, setLocale } = useLocale()
const isOpen = ref(false)
const expandedGroups = ref(new Set<string>())
const wrapperRef = ref<HTMLElement>()

const currentLabel = computed(() => {
  return LOCALE_OPTIONS.find((o) => o.value === currentLocale.value)?.label ?? 'English'
})

function toggle() {
  isOpen.value = !isOpen.value
}

function toggleGroup(groupId: string) {
  const next = new Set(expandedGroups.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  expandedGroups.value = next
}

function selectLocale(locale: SupportedLocale) {
  setLocale(locale)
  isOpen.value = false
}

function getLabel(locale: SupportedLocale): string {
  return LOCALE_OPTIONS.find((o) => o.value === locale)?.label ?? locale
}

// Auto-expand the group containing the current locale when opening
watch(isOpen, (open) => {
  if (!open) return
  const next = new Set<string>()
  if (currentLocale.value !== 'en') {
    const group = LOCALE_GROUPS.find((g) => g.locales.includes(currentLocale.value))
    if (group) next.add(group.id)
  }
  expandedGroups.value = next
})

function handleClickOutside(e: MouseEvent) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isOpen.value) {
    e.preventDefault()
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div ref="wrapperRef" class="relative" :class="{ 'w-full': variant === 'form' }">
    <!-- Trigger -->
    <button
      @click="toggle"
      @keydown="handleKeydown"
      :aria-expanded="isOpen"
      aria-haspopup="true"
      class="flex items-center gap-2 text-sm transition rounded-lg"
      :class="
        variant === 'form'
          ? 'w-full border border-border bg-surface px-3 py-2 text-foreground hover:border-brand-300'
          : 'border border-border bg-transparent px-2 py-1 text-foreground hover:bg-surface-alt'
      "
    >
      <Globe class="w-4 h-4 shrink-0 text-muted" aria-hidden="true" />
      <span class="truncate" :class="{ 'flex-1 text-left': variant === 'form' }">
        {{ currentLabel }}
      </span>
      <ChevronDown
        class="w-3.5 h-3.5 shrink-0 text-muted transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        aria-hidden="true"
      />
    </button>

    <!-- Panel -->
    <Transition name="locale-dropdown">
      <div
        v-if="isOpen"
        class="absolute z-50 mt-1 bg-surface border border-border rounded-lg shadow-lg overflow-hidden"
        :class="variant === 'form' ? 'inset-x-0' : 'inset-e-0 w-56'"
        @keydown="handleKeydown"
        role="listbox"
        :aria-label="t('language.label')"
      >
        <div class="max-h-80 overflow-y-auto py-1">
          <!-- English (ungrouped, always visible) -->
          <button
            @click="selectLocale('en')"
            class="flex items-center justify-between w-full px-3 py-2 text-sm hover:bg-surface-alt transition"
            :class="currentLocale === 'en' ? 'font-medium text-brand-600' : 'text-foreground'"
            role="option"
            :aria-selected="currentLocale === 'en'"
          >
            <span>English</span>
            <Check
              v-if="currentLocale === 'en'"
              class="w-4 h-4 text-brand-600"
              aria-hidden="true"
            />
          </button>

          <div class="border-t border-border my-1" />

          <!-- Region groups -->
          <div v-for="group in LOCALE_GROUPS" :key="group.id">
            <!-- Group header -->
            <button
              @click="toggleGroup(group.id)"
              class="flex items-center gap-1.5 w-full px-3 py-1.5 text-xs font-medium text-muted uppercase tracking-wider hover:bg-surface-alt transition"
              :aria-expanded="expandedGroups.has(group.id)"
            >
              <ChevronRight
                class="w-3 h-3 shrink-0 transition-transform duration-200"
                :class="{ 'rotate-90': expandedGroups.has(group.id) }"
                aria-hidden="true"
              />
              <span>{{ t(group.labelKey) }}</span>
              <span class="ml-auto tabular-nums opacity-60">{{ group.locales.length }}</span>
            </button>

            <!-- Accordion content -->
            <div
              class="grid transition-[grid-template-rows] duration-200 ease-out"
              :class="expandedGroups.has(group.id) ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
            >
              <div class="overflow-hidden">
                <button
                  v-for="locale in group.locales"
                  :key="locale"
                  @click="selectLocale(locale)"
                  class="flex items-center justify-between w-full pl-7 pr-3 py-2 text-sm hover:bg-surface-alt transition"
                  :class="
                    currentLocale === locale ? 'font-medium text-brand-600' : 'text-foreground'
                  "
                  role="option"
                  :aria-selected="currentLocale === locale"
                >
                  <span>{{ getLabel(locale) }}</span>
                  <Check
                    v-if="currentLocale === locale"
                    class="w-4 h-4 text-brand-600"
                    aria-hidden="true"
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.locale-dropdown-enter-active,
.locale-dropdown-leave-active {
  transition: all 0.15s ease;
}
.locale-dropdown-enter-from,
.locale-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
