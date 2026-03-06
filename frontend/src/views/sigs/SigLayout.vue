<script setup lang="ts">
import { ref, computed, onMounted, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { Sig, SigMember } from '@/types'
import {
  getSig,
  updateSig,
  deleteSig as deleteSigApi,
  getSigMembers,
  leaveSig as leaveSigApi,
  joinSig as joinSigApi,
} from '@/api/sigs'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'

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
const joining = ref(false)

// Shared state for children
provide('sig', sig)
provide('userSigRole', userSigRole)

const sigShareUrl = computed(() => `${window.location.origin}/sigs/${sigId.value}`)
const isMember = computed(() => userSigRole.value !== null)
const isSigAdmin = computed(
  () => userSigRole.value === 'ADMIN' || userSigRole.value === 'SUB_ADMIN',
)
const canJoin = computed(() => auth.isAuthenticated && !auth.isGuest && !isMember.value)
const canEdit = computed(() => auth.isAdmin || isSigAdmin.value)
const canDelete = computed(() => auth.isAdmin)
const canLeave = computed(
  () =>
    userSigRole.value !== null && !(isSigAdmin.value && sig.value && sig.value.member_count <= 1),
)

async function fetchSigData() {
  loading.value = true
  try {
    const [sigData, membersData] = await Promise.all([
      getSig(sigId.value),
      getSigMembers(sigId.value),
    ])
    sig.value = sigData
    const me = membersData.members.find((m: SigMember) => m.user_id === auth.user?.id)
    userSigRole.value = me?.role ?? null
  } catch (e) {
    console.error('Failed to fetch SIG data:', e)
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
    toastStore.show('SIG updated successfully.', 'success')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to update SIG.', 'error')
  } finally {
    editSaving.value = false
  }
}

async function handleDeleteSig() {
  try {
    await deleteSigApi(sigId.value)
    router.push('/sigs')
    toastStore.show('SIG deleted.', 'info')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to delete SIG.', 'error')
  } finally {
    showDeleteConfirm.value = false
  }
}

async function handleLeaveSig() {
  try {
    await leaveSigApi(sigId.value)
    await fetchSigData()
    toastStore.show('You have left the SIG.', 'info')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to leave SIG.', 'error')
  }
}

async function handleJoinSig() {
  joining.value = true
  try {
    await joinSigApi(sigId.value)
    await fetchSigData()
    toastStore.show('You have joined the SIG.', 'success')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to join SIG.', 'error')
  } finally {
    joining.value = false
  }
}

onMounted(fetchSigData)
watch(sigId, fetchSigData)

const navItems = [
  { name: 'Posts', route: 'sig-posts' },
  { name: 'Members', route: 'sig-members' },
  { name: 'Forms', route: 'sig-forms' },
]

const currentRouteName = computed(() => route.name)
</script>

<template>
  <div class="space-y-6 lg:pb-12">
    <!-- Back to Sigs -->
    <div class="mb-4">
      <router-link
        to="/sigs"
        class="text-sm text-brand-600 hover:underline flex items-center gap-1"
      >
        <span>&larr;</span> All SIGs
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
      <p class="text-lg text-muted mb-4">SIG not found.</p>
      <BaseButton @click="router.push('/sigs')">Return to Directory</BaseButton>
    </div>

    <!-- Content -->
    <template v-else>
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
                <span>Created by {{ sig.creator_display_name || 'Unknown' }}</span>
                <span>{{ sig.member_count }} member{{ sig.member_count === 1 ? '' : 's' }}</span>
                <span>Established {{ new Date(sig.created_at).toLocaleDateString() }}</span>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2 shrink-0">
              <CopyShareLinkButton :url="sigShareUrl" />

              <BaseButton v-if="canJoin" size="sm" :loading="joining" @click="handleJoinSig">
                Join SIG
              </BaseButton>

              <BaseButton v-if="canEdit" size="sm" variant="secondary" @click="startEdit">
                Edit
              </BaseButton>

              <BaseButton
                v-if="canLeave && userSigRole !== 'ADMIN'"
                size="sm"
                class="bg-warning-50 text-warning-700 hover:bg-warning-100"
                @click="handleLeaveSig"
              >
                Leave SIG
              </BaseButton>

              <BaseButton
                v-if="canDelete"
                size="sm"
                variant="soft-danger"
                @click="showDeleteConfirm = true"
              >
                Delete SIG
              </BaseButton>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="space-y-4">
            <BaseInput v-model="editName" label="Name" placeholder="SIG Name" />
            <BaseTextarea
              v-model="editDescription"
              label="Description (Markdown supported)"
              :rows="4"
              placeholder="Tell people what this SIG is about..."
            />
            <div class="flex gap-2">
              <BaseButton :loading="editSaving" @click="saveEdit">Save Changes</BaseButton>
              <BaseButton variant="secondary" @click="cancelEdit">Cancel</BaseButton>
            </div>
          </div>
        </template>
      </BaseCard>

      <!-- Delete confirmation -->
      <BaseModal v-model="showDeleteConfirm" title="Delete SIG?" size="sm">
        <p class="text-sm text-muted mb-4 leading-relaxed">
          This will soft-delete this Special Interest Group and all its posts. This action cannot be
          easily undone.
        </p>
        <template #footer>
          <BaseButton variant="secondary" @click="showDeleteConfirm = false">Cancel</BaseButton>
          <BaseButton variant="danger" @click="handleDeleteSig">Confirm Delete</BaseButton>
        </template>
      </BaseModal>

      <!-- Main Layout Grid -->
      <div class="flex flex-col lg:flex-row gap-6 scrollbars-stable">
        <!-- Sidebar Navigation / Tabs -->
        <aside class="w-full lg:w-64 shrink-0 lg:sticky lg:top-24 lg:self-start z-10">
          <!-- Desktop Sidebar (Underline style on the left) -->
          <nav
            class="hidden lg:flex flex-col space-y-1 bg-surface rounded-xl border border-border overflow-hidden shadow-sm"
          >
            <router-link
              v-for="item in navItems"
              :key="item.name"
              :to="{ name: item.route }"
              class="px-4 py-3 text-sm font-medium border-l-4 transition-all duration-200"
              :class="
                currentRouteName === item.route
                  ? 'bg-brand-50 border-brand-600 text-brand-700'
                  : 'border-transparent text-muted hover:bg-surface-alt hover:text-foreground'
              "
            >
              {{ item.name }}
            </router-link>
          </nav>

          <!-- Mobile Tabs (Horizontal Underline style) -->
          <nav
            class="lg:hidden flex items-center border-b border-border overflow-x-auto no-scrollbar scroll-smooth"
          >
            <router-link
              v-for="item in navItems"
              :key="item.name"
              :to="{ name: item.route }"
              class="px-6 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-all duration-200"
              :class="
                currentRouteName === item.route
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-muted hover:text-foreground'
              "
            >
              {{ item.name }}
            </router-link>
          </nav>
        </aside>

        <!-- Dynamic Content Panel -->
        <main class="flex-1 min-w-0 min-h-[500px] [scrollbar-gutter:stable]">
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

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
