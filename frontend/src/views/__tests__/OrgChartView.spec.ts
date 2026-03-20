import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OrgChartView from '../about/OrgChartView.vue'
import { useAuthStore } from '@/stores/auth'

// ── Mock router (auth store imports it at module level) ────────────────
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { name: '' } },
  },
}))

// ── Mock users API (prevents fetchProfile from overriding auth.user) ───
vi.mock('@/api/users', () => ({
  getProfile: vi.fn().mockRejectedValue(new Error('mocked')),
}))

// ── Mock API module ────────────────────────────────────────────────────
const mockGetOrgChart = vi.fn()
const mockUpdateOverride = vi.fn()
const mockUpdateSigDescription = vi.fn()
const mockUpdateMemberBio = vi.fn()

vi.mock('@/api/about', () => ({
  getOrgChart: (...a: unknown[]) => mockGetOrgChart(...a),
  updateOverride: (...a: unknown[]) => mockUpdateOverride(...a),
  updateSigDescription: (...a: unknown[]) => mockUpdateSigDescription(...a),
  updateMemberBio: (...a: unknown[]) => mockUpdateMemberBio(...a),
  getMembers: vi.fn(),
}))

// ── Fixture data ───────────────────────────────────────────────────────
const MEMBER_USER_ID = 'u-alice'
const SIG_ID = 'sig-1'
const CAT_ID = 'cat-1'

const fakeSig = {
  id: SIG_ID,
  name: 'AI & NLP',
  description: 'NLP SIG',
  org_chart_description: null,
  member_count: 2,
  members: [
    {
      user_id: MEMBER_USER_ID,
      display_name: 'Alice',
      username: 'alice',
      avatar_url: null,
      role: 'ADMIN',
      org_chart_bio: null,
    },
  ],
  override: null,
}

const fakeSigHidden = {
  ...fakeSig,
  id: 'sig-hidden',
  name: 'Hidden SIG',
  members: [],
  override: {
    entity_type: 'sig',
    entity_id: 'sig-hidden',
    custom_title: null,
    custom_description: null,
    display_order: 0,
    is_visible: false,
  },
}

const fakeCat = {
  id: CAT_ID,
  name: 'General',
  description: null,
  creator_id: MEMBER_USER_ID,
  creator_display_name: 'Alice',
  creator_avatar_url: null,
  override: null,
}

// Common stubs used across tests
const globalStubs = {
  RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
  RouterView: true,
  SkeletonLoader: { template: '<div class="skeleton-loader" />' },
  BaseBadge: {
    template: '<span class="badge" :data-variant="variant"><slot /></span>',
    props: ['variant', 'size'],
  },
}

function mountView(userRole = 'MEMBER', userId = 'other-user') {
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.setSession(userRole, 3600)
  auth.user = {
    id: userId,
    username: 'testuser',
    display_name: 'Test User',
    role: userRole,
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    preferred_language: 'en',
    is_banned: false,
    ban_reason: null,
    created_at: new Date().toISOString(),
  } as any

  return mount(OrgChartView, {
    global: {
      plugins: [pinia],
      stubs: globalStubs,
    },
  })
}

describe('OrgChartView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSig],
      categories: [fakeCat],
    })
  })

  it('shows skeleton while loading', () => {
    mockGetOrgChart.mockReturnValue(new Promise(() => {}))
    const wrapper = mountView()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('renders SIG name after load', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('AI & NLP')
  })

  it('renders category name after load', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('General')
  })

  it('renders SIG member display name', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Alice')
  })

  it('shows error message on API failure', async () => {
    mockGetOrgChart.mockRejectedValue(new Error('Network error'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('An unexpected error occurred')
  })

  it('shows hidden badge for hidden SIG when SuperAdmin', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigHidden],
      categories: [],
    })
    const wrapper = mountView('SUPER_ADMIN')
    await flushPromises()
    const badges = wrapper.findAll('.badge')
    const hiddenBadges = badges.filter((b) => b.text().trim() === 'Hidden')
    expect(hiddenBadges.length).toBeGreaterThan(0)
  })

  it('does not show hidden badge for visible SIG', async () => {
    const wrapper = mountView()
    await flushPromises()
    const badges = wrapper.findAll('.badge')
    const hiddenBadges = badges.filter((b) => b.text().trim() === 'Hidden')
    expect(hiddenBadges.length).toBe(0)
  })

  it('shows override edit button only for SuperAdmin', async () => {
    const wrapper = mountView('SUPER_ADMIN', 'other-id')
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const settingsBtn = buttons.filter((b) =>
      b.attributes('title')?.includes('display settings'),
    )
    expect(settingsBtn.length).toBeGreaterThan(0)
  })

  it('does not show override button for plain MEMBER', async () => {
    const wrapper = mountView('MEMBER', 'other-id')
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const settingsBtn = buttons.filter((b) =>
      b.attributes('title')?.includes('display settings'),
    )
    expect(settingsBtn.length).toBe(0)
  })

  it('shows edit description button for SIG admin', async () => {
    // Alice (MEMBER_USER_ID) is ADMIN in fakeSig
    const wrapper = mountView('MEMBER', MEMBER_USER_ID)
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const editBtn = buttons.filter((b) => b.attributes('title')?.includes('Edit description'))
    expect(editBtn.length).toBeGreaterThan(0)
  })

  it('shows bio edit button for member in SIG', async () => {
    // Alice is both the auth user and a member of the SIG
    const wrapper = mountView('MEMBER', MEMBER_USER_ID)
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const bioBtn = buttons.filter((b) => b.attributes('title')?.includes('Edit your bio'))
    expect(bioBtn.length).toBeGreaterThan(0)
  })

  it('does not show bio edit button for non-member user', async () => {
    const wrapper = mountView('MEMBER', 'completely-other-user')
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const bioBtn = buttons.filter((b) => b.attributes('title')?.includes('Edit your bio'))
    expect(bioBtn.length).toBe(0)
  })
})
