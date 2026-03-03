<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DOMPurify from 'dompurify'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { Sig, SigMember, SigForm, Post } from '@/types'
import {
  getSig,
  updateSig,
  deleteSig as deleteSigApi,
  getSigPosts,
  getSigMembers,
  getSigForms,
  leaveSig as leaveSigApi,
  removeMember as removeMemberApi,
  assignSubAdmin as assignSubAdminApi,
  joinSig as joinSigApi,
} from '@/api/sigs'
import { deleteForm as deleteFormApi, listFormResponses } from '@/api/forms'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toastStore = useToastStore()
const sigId = computed(() => route.params.id as string)

const sig = ref<Sig | null>(null)
const members = ref<SigMember[]>([])
const membersTotal = ref(0)
const posts = ref<Post[]>([])
const postsTotal = ref(0)
const forms = ref<SigForm[]>([])
const formsTotal = ref(0)
const loading = ref(true)
const activeTab = ref<'posts' | 'members' | 'forms'>('posts')

const editing = ref(false)
const editName = ref('')
const editDescription = ref('')
const editSaving = ref(false)
const showDeleteConfirm = ref(false)
const userSigRole = ref<string | null>(null)

const joining = ref(false)

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
const canCreateForm = computed(() => {
  if (auth.isAdmin) return true
  if (forms.value.length > 0 && forms.value[0].user_is_sig_admin) return true
  return false
})

function canRemoveMember(m: SigMember) {
  if (m.user_id === auth.user?.id) return false
  return auth.isAdmin || isSigAdmin.value
}

const memberRoleBadge: Record<string, 'orange' | 'purple' | 'brand'> = {
  ADMIN: 'orange',
  SUB_ADMIN: 'purple',
  MEMBER: 'brand',
}

async function fetchSig() {
  loading.value = true
  try {
    sig.value = await getSig(sigId.value)
  } catch {
    sig.value = null
  } finally {
    loading.value = false
  }
}
async function fetchPosts() {
  try {
    const data = await getSigPosts(sigId.value)
    posts.value = data.posts
    postsTotal.value = data.total
  } catch (e) {
    console.error(e)
  }
}
async function fetchMembers() {
  try {
    const data = await getSigMembers(sigId.value)
    members.value = data.members
    membersTotal.value = data.total
    const me = members.value.find((m) => m.user_id === auth.user?.id)
    userSigRole.value = me?.role ?? null
  } catch (e) {
    console.error(e)
  }
}
async function fetchForms() {
  try {
    const data = await getSigForms(sigId.value)
    forms.value = data.forms
    formsTotal.value = data.total
  } catch (e) {
    console.error(e)
  }
}

function switchTab(tab: 'posts' | 'members' | 'forms') {
  activeTab.value = tab
  if (tab === 'posts') fetchPosts()
  else if (tab === 'members') fetchMembers()
  else fetchForms()
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
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to delete SIG.', 'error')
  } finally {
    showDeleteConfirm.value = false
  }
}

async function handleLeaveSig() {
  try {
    await leaveSigApi(sigId.value)
    await fetchSig()
    await fetchMembers()
    toastStore.show('You have left the SIG.', 'info')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to leave SIG.', 'error')
  }
}

async function handleJoinSig() {
  joining.value = true
  try {
    await joinSigApi(sigId.value)
    await fetchSig()
    await fetchMembers()
    toastStore.show('You have joined the SIG.', 'success')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to join SIG.', 'error')
  } finally {
    joining.value = false
  }
}

async function handleRemoveMember(userId: string) {
  try {
    await removeMemberApi(sigId.value, userId)
    await fetchSig()
    await fetchMembers()
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to remove member.', 'error')
  }
}

async function handleAssignSubAdmin(userId: string) {
  try {
    await assignSubAdminApi(sigId.value, userId)
    await fetchMembers()
    toastStore.show('Member promoted to Sub-Admin.', 'success')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to assign Sub-Admin.', 'error')
  }
}

// Form deletion
const showFormDeleteConfirm = ref(false)
const formToDelete = ref<string | null>(null)

function confirmDeleteForm(formId: string) {
  formToDelete.value = formId
  showFormDeleteConfirm.value = true
}

async function handleDeleteForm() {
  if (!formToDelete.value) return
  try {
    await deleteFormApi(formToDelete.value)
    await fetchForms()
    toastStore.show('Form deleted.', 'success')
  } catch (e: any) {
    toastStore.show(e.response?.data?.detail || 'Failed to delete form.', 'error')
  } finally {
    showFormDeleteConfirm.value = false
    formToDelete.value = null
  }
}

// Form response viewing
const showResponsesModal = ref(false)
const responsesFormId = ref('')
const responsesFormTitle = ref('')
const responses = ref<any[]>([])
const responsesPage = ref(1)
const responsesTotalPages = ref(1)
const responsesLoading = ref(false)

async function fetchResponses(formId: string, title: string, page = 1) {
  responsesFormId.value = formId
  responsesFormTitle.value = title
  responsesPage.value = page
  responsesLoading.value = true
  showResponsesModal.value = true
  try {
    const data = await listFormResponses(formId, page)
    responses.value = data.responses || []
    const total = data.total || 0
    responsesTotalPages.value = Math.ceil(total / 20) || 1
  } catch {
    toastStore.show('Failed to load responses.', 'error')
  } finally {
    responsesLoading.value = false
  }
}

onMounted(() => {
  fetchSig()
  fetchPosts()
  fetchMembers()
})
</script>

<template>
  <div>
    <div class="mb-6">
      <router-link to="/sigs" class="text-sm text-brand-600 hover:underline"
        >&larr; All SIGs</router-link
      >
    </div>

    <SkeletonLoader v-if="loading" :lines="1" variant="card" />
    <div v-else-if="!sig" class="text-center py-12">
      <p class="text-muted mb-4">SIG not found.</p>
      <router-link to="/sigs" class="text-brand-600 hover:underline">Back to SIGs</router-link>
    </div>

    <template v-else>
      <BaseCard padding="lg" class="mb-6">
        <template v-if="!editing">
          <div class="flex items-start justify-between">
            <div>
              <h1 class="text-2xl font-bold text-foreground mb-2">{{ sig.name }}</h1>
              <p
                v-if="sig.description"
                class="text-sm text-muted mb-3"
                v-html="DOMPurify.sanitize(sig.description)"
              ></p>
            </div>
            <div class="flex gap-2 shrink-0 ml-4">
              <CopyShareLinkButton :url="sigShareUrl" />
              <BaseButton v-if="canJoin" size="sm" :loading="joining" @click="handleJoinSig"
                >Join SIG</BaseButton
              >
              <BaseButton v-if="canEdit" size="sm" variant="secondary" @click="startEdit"
                >Edit</BaseButton
              >
              <BaseButton
                v-if="canLeave && userSigRole !== 'ADMIN'"
                size="sm"
                class="bg-warning-50 text-warning-700 hover:bg-warning-100"
                @click="handleLeaveSig"
                >Leave SIG</BaseButton
              >
              <BaseButton
                v-if="canDelete"
                size="sm"
                variant="soft-danger"
                @click="showDeleteConfirm = true"
                >Delete SIG</BaseButton
              >
            </div>
          </div>
          <div class="flex items-center gap-4 text-xs text-muted">
            <span>Created by {{ sig.creator_display_name || 'Unknown' }}</span>
            <span>{{ sig.member_count }} member(s)</span>
            <span>{{ new Date(sig.created_at).toLocaleDateString() }}</span>
          </div>
        </template>

        <template v-else>
          <div class="space-y-3">
            <BaseInput v-model="editName" label="Name" />
            <BaseTextarea v-model="editDescription" label="Description" :rows="3" />
            <div class="flex gap-2">
              <BaseButton :loading="editSaving" @click="saveEdit">Save</BaseButton>
              <BaseButton variant="secondary" @click="cancelEdit">Cancel</BaseButton>
            </div>
          </div>
        </template>
      </BaseCard>

      <!-- Delete confirmation -->
      <BaseModal v-model="showDeleteConfirm" title="Delete SIG?" size="sm">
        <p class="text-sm text-muted mb-4">
          This will soft-delete this SIG and all its posts. This action cannot be easily undone.
        </p>
        <template #footer>
          <BaseButton variant="secondary" @click="showDeleteConfirm = false">Cancel</BaseButton>
          <BaseButton variant="danger" @click="handleDeleteSig">Delete</BaseButton>
        </template>
      </BaseModal>

      <!-- Tabs -->
      <div class="flex gap-1 mb-4 overflow-x-auto">
        <button
          @click="switchTab('posts')"
          class="px-4 py-2 text-sm rounded-lg transition whitespace-nowrap"
          :class="
            activeTab === 'posts'
              ? 'bg-brand-600 text-white'
              : 'bg-surface-alt text-muted hover:bg-gray-100'
          "
        >
          Posts ({{ postsTotal }})
        </button>
        <button
          @click="switchTab('members')"
          class="px-4 py-2 text-sm rounded-lg transition whitespace-nowrap"
          :class="
            activeTab === 'members'
              ? 'bg-brand-600 text-white'
              : 'bg-surface-alt text-muted hover:bg-gray-100'
          "
        >
          Members ({{ membersTotal }})
        </button>
        <button
          @click="switchTab('forms')"
          class="px-4 py-2 text-sm rounded-lg transition whitespace-nowrap"
          :class="
            activeTab === 'forms'
              ? 'bg-brand-600 text-white'
              : 'bg-surface-alt text-muted hover:bg-gray-100'
          "
        >
          Forms ({{ formsTotal }})
        </button>
      </div>

      <!-- Posts tab -->
      <div v-if="activeTab === 'posts'">
        <div v-if="isMember" class="mb-4">
          <router-link :to="`/forum/create?sig_id=${sigId}`">
            <BaseButton>New Post</BaseButton>
          </router-link>
        </div>
        <div v-if="posts.length === 0" class="text-center text-muted py-8 text-sm">
          No posts in this SIG yet.
        </div>
        <div v-else class="space-y-3">
          <div v-for="p in posts" :key="p.id">
            <BaseCard hoverable>
              <div class="flex items-center gap-2 mb-2">
                <router-link :to="`/users/${p.author.id}`">
                  <BaseAvatar :src="p.author.avatar_url" :name="p.author.display_name" size="sm" />
                </router-link>
                <router-link
                  :to="`/users/${p.author.id}`"
                  class="text-sm font-medium text-foreground hover:text-brand-600 hover:underline"
                >
                  {{ p.author.display_name }}
                </router-link>
                <span class="text-xs text-muted">{{
                  new Date(p.created_at).toLocaleString()
                }}</span>
              </div>
              <router-link :to="`/forum/${p.id}`" class="block">
                <h3 class="font-semibold text-foreground mb-1 hover:text-brand-600">
                  {{ p.title }}
                </h3>
              </router-link>
              <div class="text-xs text-muted">{{ p.comment_count }} comments</div>
            </BaseCard>
          </div>
        </div>
      </div>

      <!-- Members tab -->
      <div v-if="activeTab === 'members'">
        <div v-if="members.length === 0" class="text-center text-muted py-8 text-sm">
          No members yet.
        </div>
        <div v-else class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
          <table class="w-full text-sm min-w-[600px]">
            <thead class="bg-surface-alt border-b border-border">
              <tr>
                <th class="text-left px-4 py-3 font-medium text-muted">Name</th>
                <th class="text-left px-4 py-3 font-medium text-muted">Username</th>
                <th class="text-left px-4 py-3 font-medium text-muted">Role</th>
                <th class="text-left px-4 py-3 font-medium text-muted">Joined</th>
                <th v-if="canEdit" class="text-left px-4 py-3 font-medium text-muted">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="m in members"
                :key="m.id"
                class="border-b border-border last:border-0 hover:bg-surface-alt transition"
              >
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <router-link :to="`/users/${m.user_id}`">
                      <BaseAvatar :src="m.avatar_url" :name="m.display_name" size="sm" />
                    </router-link>
                    <router-link
                      :to="`/users/${m.user_id}`"
                      class="text-foreground hover:text-brand-600 hover:underline"
                    >
                      {{ m.display_name }}
                    </router-link>
                  </div>
                </td>
                <td class="px-4 py-3 text-muted">{{ m.username }}</td>
                <td class="px-4 py-3">
                  <BaseBadge :variant="memberRoleBadge[m.role] || 'brand'">{{ m.role }}</BaseBadge>
                </td>
                <td class="px-4 py-3 text-muted text-xs">
                  {{ new Date(m.created_at).toLocaleDateString() }}
                </td>
                <td v-if="canEdit" class="px-4 py-3">
                  <button
                    v-if="auth.isAdmin && m.role === 'MEMBER'"
                    @click="handleAssignSubAdmin(m.user_id)"
                    class="text-xs text-brand-600 hover:underline mr-2"
                  >
                    Promote
                  </button>
                  <button
                    v-if="canRemoveMember(m)"
                    @click="handleRemoveMember(m.user_id)"
                    class="text-xs text-danger-600 hover:underline"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Forms tab -->
      <div v-if="activeTab === 'forms'">
        <div v-if="canCreateForm" class="mb-4">
          <router-link :to="`/sigs/${sigId}/forms/new`">
            <BaseButton>+ Create Form</BaseButton>
          </router-link>
        </div>
        <div v-if="forms.length === 0" class="text-center text-muted py-8 text-sm">
          No forms in this SIG yet.
        </div>
        <div v-else class="grid gap-4 sm:grid-cols-2">
          <div v-for="f in forms" :key="f.id">
            <BaseCard hoverable class="h-full">
              <div class="flex items-start justify-between mb-2">
                <router-link
                  :to="`/forms/${f.id}`"
                  class="font-semibold text-foreground hover:text-brand-600 hover:underline"
                >
                  {{ f.title }}
                </router-link>
                <BaseBadge :variant="f.is_active ? 'success' : 'danger'" class="shrink-0 ml-2">{{
                  f.is_active ? 'Active' : 'Closed'
                }}</BaseBadge>
              </div>
              <p v-if="f.description" class="text-xs text-muted mb-2 line-clamp-2">
                {{ f.description }}
              </p>
              <div class="flex items-center gap-3 text-xs text-muted">
                <span>{{ f.response_count }} response(s)</span>
                <span v-if="f.deadline"
                  >Deadline: {{ new Date(f.deadline).toLocaleDateString() }}</span
                >
                <span>By {{ f.created_by_name }}</span>
              </div>
              <div
                v-if="f.user_is_sig_admin"
                class="flex items-center gap-3 mt-3 pt-2 border-t border-border"
              >
                <router-link
                  :to="`/forms/${f.id}/edit`"
                  class="text-xs text-brand-600 hover:underline"
                >
                  Edit
                </router-link>
                <button
                  @click="fetchResponses(f.id, f.title)"
                  class="text-xs text-brand-600 hover:underline"
                >
                  View Responses
                </button>
                <button
                  @click="confirmDeleteForm(f.id)"
                  class="text-xs text-danger-600 hover:underline"
                >
                  Delete
                </button>
              </div>
            </BaseCard>
          </div>
        </div>
      </div>

      <!-- Form Delete Confirmation Modal -->
      <BaseModal v-model="showFormDeleteConfirm" title="Delete Form?" size="sm">
        <p class="text-sm text-muted mb-4">
          Are you sure you want to delete this form? This action cannot be undone.
        </p>
        <template #footer>
          <BaseButton variant="secondary" @click="showFormDeleteConfirm = false">Cancel</BaseButton>
          <BaseButton variant="danger" @click="handleDeleteForm">Delete</BaseButton>
        </template>
      </BaseModal>

      <!-- Form Responses Modal -->
      <BaseModal v-model="showResponsesModal" :title="`Responses: ${responsesFormTitle}`" size="xl">
        <div v-if="responsesLoading" class="py-8 text-center text-muted">
          Loading...
        </div>
        <div v-else-if="responses.length === 0" class="py-8 text-center text-muted">
          No responses yet.
        </div>
        <div v-else>
          <div
            v-for="resp in responses"
            :key="resp.id"
            class="border-b border-border py-4 last:border-0"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium text-foreground">{{ resp.display_name }}</span>
              <span class="text-sm text-muted">{{ new Date(resp.created_at).toLocaleString() }}</span>
            </div>
            <div class="space-y-1">
              <div v-for="(value, key) in resp.answers" :key="key" class="text-sm">
                <span class="text-muted">{{ key }}:</span>
                <span class="text-foreground ml-1">
                  {{ Array.isArray(value) ? value.join(', ') : typeof value === 'object' ? JSON.stringify(value) : value }}
                </span>
              </div>
            </div>
          </div>

          <BasePagination
            v-if="responsesTotalPages > 1"
            :current-page="responsesPage"
            :total-pages="responsesTotalPages"
            class="mt-4"
            @update:current-page="(p: number) => fetchResponses(responsesFormId, responsesFormTitle, p)"
          />
        </div>
      </BaseModal>
    </template>
  </div>
</template>
