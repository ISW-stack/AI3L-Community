import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AlbumMembersView from '../AlbumMembersView.vue'
import { useAuthStore } from '@/stores/auth'
import type { Album } from '@/types/album'
import type { UserProfile } from '@/types/user'

const mockListAlbumMembers = vi.fn()
const mockJoinAlbum = vi.fn()
const mockRemoveAlbumMember = vi.fn()
const mockApproveAlbumMember = vi.fn()
const mockAddAlbumMember = vi.fn()

vi.mock('@/api/albums', () => ({
  listAlbumMembers: (...args: unknown[]) => mockListAlbumMembers(...args),
  joinAlbum: (...args: unknown[]) => mockJoinAlbum(...args),
  removeAlbumMember: (...args: unknown[]) => mockRemoveAlbumMember(...args),
  approveAlbumMember: (...args: unknown[]) => mockApproveAlbumMember(...args),
  addAlbumMember: (...args: unknown[]) => mockAddAlbumMember(...args),
}))

vi.mock('@/api/coauthors', () => ({
  searchUsers: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeAlbum: Album = {
  id: 'album-1',
  title: 'Test Album',
  description: null,
  cover_photo_url: null,
  created_by: 'user1',
  created_by_name: 'Alice',
  is_archived: false,
  photo_count: 0,
  member_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

vi.mock('@/composables/useAlbumLayout', () => ({
  useAlbumLayout: () => ({
    album: ref(fakeAlbum),
    userAlbumRole: ref('ADMIN'),
  }),
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/albums/:id/members', component: AlbumMembersView },
      { path: '/', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['hoverable'] },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    BaseAvatar: { template: '<span class="base-avatar" />', props: ['src', 'name', 'size'] },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'placeholder', 'label'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
  }
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession('ADMIN', 3600)
  auth.user = {
    id: 'user1',
    username: 'admin',
    display_name: 'Admin User',
    role: 'ADMIN',
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as unknown as UserProfile

  await router.push('/albums/album-1/members')
  await router.isReady()

  const wrapper = mount(AlbumMembersView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('AlbumMembersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAlbumMembers.mockResolvedValue({ members: [] })
  })

  it('fetches members on mount', async () => {
    await mountView()
    expect(mockListAlbumMembers).toHaveBeenCalledWith('album-1')
  })

  it('clears search debounce timer on unmount', async () => {
    const { wrapper } = await mountView()
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    // Trigger search to start debounce timer
    const vm = wrapper.vm as unknown as { handleSearchInput: (val: string) => void }
    vm.handleSearchInput('test')

    // Unmount should clear the pending timer
    wrapper.unmount()

    expect(clearTimeoutSpy).toHaveBeenCalled()
    clearTimeoutSpy.mockRestore()
  })
})
