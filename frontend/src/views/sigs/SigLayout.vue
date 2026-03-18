<script setup lang="ts">
import { ref, computed, onMounted, watch, provide, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { Sig } from '@/types'
import {
  getSig,
  updateSig,
  deleteSig as deleteSigApi,
  getMySigRole,
  leaveSig as leaveSigApi,
  joinSig as joinSigApi,
} from '@/api/sigs'
import { getErrorMessage } from '@/utils/error'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toastStore = useToastStore()

const sigId = computed(() => route.params.id as string)

const sig = ref<Sig | null>(null)
const loading = ref(true)
const userSigRole = ref<string | null>(null)
const editing = ref(false)
const editName = ref('')
const editDescription = ref('')
const editSaving = ref(false)
const showDeleteConfirm = ref(false)
const deletingGroup = ref(false)
const joining = ref(false)

const showLeaveConfirm = ref(false)

// Shared state for children
provide('sig', sig)
provide('userSigRole', userSigRole)

async function refreshSigRole() {
  if (!auth.isAuthenticated || auth.isGuest) {
    userSigRole.value = null
    return
  }
  try {
    userSigRole.value = await getMySigRole(sigId.value)
  } catch {
    // Silently fail — role stays as-is
  }
}

provide('refreshSigRole', refreshSigRole)

const sigShareUrl = computed(() => `${window.location.origin}/sigs/${sigId.value}`)
const isMember = computed(() => userSigRole.value !== null)
const isSigAdmin = computed(
  () => userSigRole.value === 'ADMIN' || userSigRole.value === 'SUB_ADMIN',
)
const canJoin = computed(() => auth.isAuthenticated && !auth.isGuest && !isMember.value)
const canEdit = computed(() => auth.isAdmin || isSigAdmin.value)
const canDelete = computed(() => auth.isAdmin)
const canLeave = computed(() => userSigRole.value !== null)

async function fetchSigData() {
  loading.value = true
  try {
    const sigData = await getSig(sigId.value)
    sig.value = sigData
    if (auth.isAuthenticated && !auth.isGuest) {
      userSigRole.value = await getMySigRole(sigId.value)
    } else {
      userSigRole.value = null
    }
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.detail.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!sig.value) return
  editName.value = sig.value.name
  editDescription.value = sig.value.description || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  editSaving.value = true
  try {
    sig.value = await updateSig(sigId.value, {
      name: editName.value,
      description: editDescription.value || null,
    })
    editing.value = false
    toastStore.show(t('sigs.detail.updateSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.detail.updateError')), 'error')
  } finally {
    editSaving.value = false
  }
}

async function handleDeleteSig() {
  deletingGroup.value = true
  try {
    await deleteSigApi(sigId.value)
    router.push('/sigs')
    toastStore.show(t('sigs.detail.deleteSuccess'), 'info')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.detail.deleteError')), 'error')
  } finally {
    deletingGroup.value = false
    showDeleteConfirm.value = false
  }
}

function promptLeaveSig() {
  showLeaveConfirm.value = true
}

async function executeLeaveSig() {
  try {
    await leaveSigApi(sigId.value)
    await fetchSigData()
    toastStore.show(t('sigs.detail.leaveSuccess'), 'info')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.detail.leaveError')), 'error')
  } finally {
    showLeaveConfirm.value = false
  }
}

async function handleJoinSig() {
  joining.value = true
  try {
    await joinSigApi(sigId.value)
    await fetchSigData()
    toastStore.show(t('sigs.detail.joinSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.detail.joinError')), 'error')
  } finally {
    joining.value = false
  }
}

onMounted(fetchSigData)
watch(sigId, fetchSigData)

const navItems = [
  { key: 'sigs.detail.navPosts', route: 'sig-posts' },
  { key: 'sigs.detail.navMembers', route: 'sig-members' },
  { key: 'sigs.detail.navForms', route: 'sig-forms' },
]

const currentRouteName = computed(() => route.name)

const showScrollHint = ref(true)
const tabNavRef = ref<HTMLElement | null>(null)
const tabOverflowTimer = ref<ReturnType<typeof setTimeout> | null>(null)

function handleTabScroll(event: Event) {
  const el = event.target as HTMLElement
  if (!el) return
  const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4
  showScrollHint.value = !atEnd
}

function checkTabOverflow() {
  if (tabNavRef.value) {
    showScrollHint.value = tabNavRef.value.scrollWidth > tabNavRef.value.clientWidth
  }
}

onMounted(() => {
  // Check overflow after initial render
  tabOverflowTimer.value = setTimeout(checkTabOverflow, 100)
})

onUnmounted(() => {
  if (tabOverflowTimer.value) {
    clearTimeout(tabOverflowTimer.value)
    tabOverflowTimer.value = null
  }
})
</script>

<template>
  <div class="flex flex-col h-full w-full lg:px-layout px-4 py-6 sm:py-8">
    <!-- Back to Sigs -->
    <div class="shrink-0 mb-4">
      <router-link
        to="/sigs"
        class="text-sm text-brand-600 hover:underline flex items-center gap-1"
      >
        <span>&larr;</span> {{ t('sigs.detail.backLink') }}
      </router-link>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-6">
      <SkeletonLoader variant="card" :lines="2" />
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="w-full lg:w-80 shrink-0">
          <SkeletonLoader variant="card" :lines="6" />
        </div>
        <div class="flex-1">
          <SkeletonLoader variant="card" :lines="6" />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="!sig" class="text-center py-12">
      <p class="text-lg text-muted mb-4">{{ t('sigs.detail.notFound') }}</p>
      <BaseButton @click="router.push('/sigs')">{{ t('sigs.detail.returnBtn') }}</BaseButton>
    </div>

    <!-- Content -->
    <template v-else>
      <div class="shrink-0">
        <BaseCard padding="lg" class="mb-6">
          <template v-if="!editing">
            <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <div class="min-w-0 flex-1">
                <h1 class="text-2xl font-bold text-foreground mb-2 break-words">{{ sig.name }}</h1>
                <div
                  v-if="sig.description"
                  class="text-sm text-muted mb-3 prose prose-sm max-w-none prose-muted"
                  v-html="DOMPurify.sanitize(sig.description)"
                ></div>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
                  <span
                    >{{ t('sigs.detail.createdBy') }}
                    {{ sig.creator_display_name || 'Unknown' }}</span
                  >
                  <span
                    >{{ sig.member_count }}
                    {{
                      sig.member_count === 1 ? t('sigs.detail.member') : t('sigs.detail.members')
                    }}</span
                  >
                  <span
                    >{{ t('sigs.detail.established') }}
                    {{ new Date(sig.created_at).toLocaleDateString(locale) }}</span
                  >
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2 shrink-0">
                <CopyShareLinkButton :url="sigShareUrl" />

                <BaseButton v-if="canJoin" size="sm" :loading="joining" @click="handleJoinSig">
                  {{ t('sigs.detail.joinBtn') }}
                </BaseButton>

                <BaseButton v-if="canEdit" size="sm" variant="secondary" @click="startEdit">
                  {{ t('sigs.detail.editBtn') }}
                </BaseButton>

                <BaseButton
                  v-if="canLeave"
                  size="sm"
                  class="bg-warning-50 text-warning-700 hover:bg-warning-100"
                  @click="promptLeaveSig"
                >
                  {{ t('sigs.detail.leaveBtn') }}
                </BaseButton>

                <BaseButton
                  v-if="canDelete"
                  size="sm"
                  variant="soft-danger"
                  @click="showDeleteConfirm = true"
                >
                  {{ t('sigs.detail.deleteBtn') }}
                </BaseButton>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="space-y-4">
              <BaseInput
                v-model="editName"
                :label="t('sigs.detail.editForm.nameLabel')"
                :placeholder="t('sigs.detail.editForm.namePlaceholder')"
              />
              <BaseTextarea
                v-model="editDescription"
                :label="t('sigs.detail.editForm.descLabel')"
                :rows="4"
                :placeholder="t('sigs.detail.editForm.descPlaceholder')"
              />
              <div class="flex gap-2">
                <BaseButton :loading="editSaving" @click="saveEdit">{{
                  t('sigs.detail.editForm.saveBtn')
                }}</BaseButton>
                <BaseButton variant="secondary" @click="cancelEdit">{{
                  t('sigs.detail.editForm.cancelBtn')
                }}</BaseButton>
              </div>
            </div>
          </template>
        </BaseCard>

        <!-- Delete confirmation -->
        <BaseModal
          v-model="showDeleteConfirm"
          :title="t('sigs.detail.deleteConfirm.title')"
          size="sm"
        >
          <p class="text-sm text-muted mb-4 leading-relaxed">
            {{ t('sigs.detail.deleteConfirm.message') }}
          </p>
          <template #footer>
            <BaseButton variant="secondary" @click="showDeleteConfirm = false">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton variant="danger" :loading="deletingGroup" :disabled="deletingGroup" @click="handleDeleteSig">
              <span v-if="deletingGroup">{{ t('sigs.detail.deleteConfirm.deletingBtn') }}</span>
              <span v-else>{{ t('sigs.detail.deleteConfirm.confirmBtn') }}</span>
            </BaseButton>
          </template>
        </BaseModal>

        <!-- Leave confirmation -->
        <BaseModal
          v-model="showLeaveConfirm"
          :title="t('sigs.detail.leaveConfirm.title')"
          size="sm"
        >
          <p class="text-sm text-muted mb-4 leading-relaxed">
            {{ t('sigs.detail.leaveConfirm.message') }}
          </p>
          <template #footer>
            <BaseButton variant="secondary" @click="showLeaveConfirm = false">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton variant="danger" @click="executeLeaveSig">{{
              t('sigs.detail.leaveConfirm.confirmBtn')
            }}</BaseButton>
          </template>
        </BaseModal>
      </div>

      <!-- Main Layout Grid -->
      <div class="flex flex-col lg:flex-row gap-6 lg:gap-16 flex-1 min-h-0">
        <!-- Sidebar Navigation / Tabs -->
        <aside class="w-full lg:w-48 xl:w-64 shrink-0 flex flex-col">
          <!-- Desktop Sidebar (Underline style on the left) -->
          <nav
            class="hidden lg:flex flex-col space-y-1 bg-surface rounded-xl border border-border overflow-hidden shadow-sm"
          >
            <router-link
              v-for="item in navItems"
              :key="item.key"
              :to="{ name: item.route }"
              class="px-4 py-3 text-sm font-medium border-l-4 transition-all duration-200"
              :class="
                currentRouteName === item.route
                  ? 'bg-brand-50 border-brand-600 text-brand-700'
                  : 'border-transparent text-muted hover:bg-surface-alt hover:text-foreground'
              "
            >
              {{ t(item.key) }}
            </router-link>
          </nav>

          <!-- Mobile Tabs (Horizontal Underline style) -->
          <div class="lg:hidden relative">
            <nav
              ref="tabNavRef"
              class="tab-scroll-nav flex items-center border-b border-border overflow-x-auto scroll-smooth"
              style="-webkit-overflow-scrolling: touch"
              @scroll="handleTabScroll"
            >
              <router-link
                v-for="item in navItems"
                :key="item.key"
                :to="{ name: item.route }"
                class="px-6 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-all duration-200"
                :class="
                  currentRouteName === item.route
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-muted hover:text-foreground'
                "
              >
                {{ t(item.key) }}
              </router-link>
            </nav>
            <div
              v-if="showScrollHint"
              class="scroll-hint absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none"
              aria-hidden="true"
            ></div>
          </div>
        </aside>

        <!-- Dynamic Content Panel -->
        <main class="flex-1 min-w-0 overflow-y-auto pr-2 [scrollbar-gutter:stable] pb-12">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
