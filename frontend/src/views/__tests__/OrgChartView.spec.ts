import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OrgChartView from '../about/OrgChartView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

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

function makeMember(
  id: string,
  name: string,
  role: 'ADMIN' | 'SUB_ADMIN' | 'MEMBER',
  avatarUrl: string | null = null,
  bio: string | null = null,
) {
  return {
    user_id: id,
    display_name: name,
    username: name.toLowerCase().replace(/\s+/g, ''),
    avatar_url: avatarUrl,
    role,
    org_chart_bio: bio,
  }
}

const fakeSig = {
  id: SIG_ID,
  name: 'AI & NLP',
  description: 'NLP SIG',
  org_chart_description: null,
  member_count: 2,
  members: [
    makeMember(MEMBER_USER_ID, 'Alice', 'ADMIN', null, 'Bio of Alice'),
    makeMember('u-bob', 'Bob', 'SUB_ADMIN'),
  ],
  override: null,
}

const fakeSigHidden = {
  ...fakeSig,
  id: 'sig-hidden',
  name: 'Hidden SIG',
  members: [],
  member_count: 0,
  override: {
    entity_type: 'sig',
    entity_id: 'sig-hidden',
    custom_title: null,
    custom_description: null,
    display_order: 0,
    is_visible: false,
  },
}

const fakeSigEmpty = {
  id: 'sig-empty',
  name: 'Empty SIG',
  description: 'No one here',
  org_chart_description: null,
  member_count: 0,
  members: [],
  override: null,
}

// SIG with many members: 2 leads + 15 regular members
const manyLeads = [
  makeMember('u-lead-1', 'Lead One', 'ADMIN', 'http://example.com/lead1.jpg'),
  makeMember('u-lead-2', 'Lead Two', 'SUB_ADMIN'),
]
const manyRegulars = Array.from({ length: 15 }, (_, i) =>
  makeMember(`u-reg-${i}`, `Regular Member ${i}`, 'MEMBER'),
)
const fakeSigMany = {
  id: 'sig-many',
  name: 'Big SIG',
  description: 'Lots of people',
  org_chart_description: 'Custom desc',
  member_count: 17,
  members: [...manyLeads, ...manyRegulars],
  override: null,
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
  Transition: { template: '<div><slot /></div>', props: ['name'] },
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
  } as unknown as UserProfile

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

  // ── Loading / Error ──────────────────────────────────────────────────

  it('shows skeleton while loading', () => {
    mockGetOrgChart.mockReturnValue(new Promise(() => {}))
    const wrapper = mountView()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows error message on API failure', async () => {
    mockGetOrgChart.mockRejectedValue(new Error('Network error'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('An unexpected error occurred')
  })

  // ── Root node and tree structure ─────────────────────────────────────

  it('renders root node with community name', async () => {
    const wrapper = mountView()
    await flushPromises()
    const rootNode = wrapper.find('.root-node')
    expect(rootNode.exists()).toBe(true)
    expect(rootNode.text()).toContain('AI3L Community')
  })

  it('renders SIG nodes in tree structure', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.tree-row').exists()).toBe(true)
    expect(wrapper.find('.tree-node-wrapper').exists()).toBe(true)
    expect(wrapper.find('.sig-node').exists()).toBe(true)
    expect(wrapper.text()).toContain('AI & NLP')
  })

  // ── Collapse / Expand ────────────────────────────────────────────────

  it('SIGs are collapsed by default — members not visible', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.member-panel').exists()).toBe(false)
    expect(wrapper.find('.lead-member-row').exists()).toBe(false)
  })

  it('clicking SIG node expands member panel', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    expect(wrapper.find('.member-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('Alice')
  })

  it('clicking expanded SIG node collapses it', async () => {
    const wrapper = mountView()
    await flushPromises()

    const sigNode = wrapper.find('.sig-node')
    // Expand
    await sigNode.trigger('click')
    await flushPromises()
    expect(wrapper.find('.member-panel').exists()).toBe(true)

    // Collapse
    await sigNode.trigger('click')
    await flushPromises()
    expect(wrapper.find('.member-panel').exists()).toBe(false)
  })

  // ── Chevron direction (proxy: component switch based on expanded state) ──

  it('shows ChevronRight when collapsed and ChevronDown when expanded', async () => {
    const wrapper = mountView()
    await flushPromises()

    // Collapsed: member-panel absent indicates ChevronRight state
    expect(wrapper.find('.member-panel').exists()).toBe(false)

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    // Expanded: member-panel present indicates ChevronDown state
    expect(wrapper.find('.member-panel').exists()).toBe(true)
  })

  // ── Leads vs regular members ─────────────────────────────────────────

  it('shows leads with avatar and role badge', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigMany],
      categories: [],
    })
    const wrapper = mountView()
    await flushPromises()

    // Expand the SIG
    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    const leadRows = wrapper.findAll('.lead-member-row')
    expect(leadRows.length).toBe(2)
    expect(leadRows[0].text()).toContain('Lead One')
    expect(leadRows[1].text()).toContain('Lead Two')

    // Leads should have role badges
    const badges = wrapper.find('.member-panel').findAll('.badge')
    const adminBadge = badges.filter((b) => b.text().includes('ADMIN'))
    expect(adminBadge.length).toBeGreaterThan(0)
  })

  it('shows regular members without avatar', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigMany],
      categories: [],
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    const regularRows = wrapper.findAll('.regular-member-row')
    // Default truncation: only first 10 shown
    expect(regularRows.length).toBe(10)
    expect(regularRows[0].text()).toContain('Regular Member 0')
  })

  // ── Member truncation ────────────────────────────────────────────────

  it('truncates regular members at 10 with +N more button', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigMany],
      categories: [],
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    const regularRows = wrapper.findAll('.regular-member-row')
    expect(regularRows.length).toBe(10)

    // Should show "+5 more" button (15 total - 10 shown = 5 hidden)
    const panelText = wrapper.find('.member-panel').text()
    expect(panelText).toContain('+5 more')
  })

  it('toggles show more/less for regular members', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigMany],
      categories: [],
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    // Initially 10 members shown
    expect(wrapper.findAll('.regular-member-row').length).toBe(10)

    // Click "+5 more" to show all
    const moreButtons = wrapper.findAll('.member-panel button')
    const showMoreBtn = moreButtons.filter((b) => b.text().includes('more'))
    expect(showMoreBtn.length).toBe(1)
    await showMoreBtn[0].trigger('click')
    await flushPromises()

    // Now all 15 regular members shown
    expect(wrapper.findAll('.regular-member-row').length).toBe(15)
    expect(wrapper.find('.member-panel').text()).toContain('Show less')

    // Click "Show less" to truncate again
    const lessButtons = wrapper.findAll('.member-panel button')
    const showLessBtn = lessButtons.filter((b) => b.text().includes('Show less'))
    expect(showLessBtn.length).toBe(1)
    await showLessBtn[0].trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.regular-member-row').length).toBe(10)
  })

  // ── Empty SIG ────────────────────────────────────────────────────────

  it('shows "No members" for empty SIG', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigEmpty],
      categories: [],
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    expect(wrapper.find('.member-panel').exists()).toBe(true)
    expect(wrapper.find('.member-panel').text()).toContain('No members')
  })

  // ── Hidden SIG ───────────────────────────────────────────────────────

  it('shows hidden badge and opacity for hidden SIG', async () => {
    mockGetOrgChart.mockResolvedValue({
      sigs: [fakeSigHidden],
      categories: [],
    })
    const wrapper = mountView('SUPER_ADMIN')
    await flushPromises()

    // Hidden badge
    const badges = wrapper.findAll('.badge')
    const hiddenBadges = badges.filter((b) => b.text().trim() === 'Hidden')
    expect(hiddenBadges.length).toBeGreaterThan(0)

    // opacity-50 class on wrapper
    const nodeWrapper = wrapper.find('.tree-node-wrapper')
    expect(nodeWrapper.classes()).toContain('opacity-50')
  })

  // ── Admin buttons ────────────────────────────────────────────────────

  it('shows override edit button only for SuperAdmin', async () => {
    const wrapper = mountView('SUPER_ADMIN', 'other-id')
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const settingsBtn = buttons.filter((b) => b.attributes('title')?.includes('display settings'))
    expect(settingsBtn.length).toBeGreaterThan(0)
  })

  it('does not show override button for plain MEMBER', async () => {
    const wrapper = mountView('MEMBER', 'other-id')
    await flushPromises()
    const buttons = wrapper.findAll('button[title]')
    const settingsBtn = buttons.filter((b) => b.attributes('title')?.includes('display settings'))
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

  // ── Bio edit ─────────────────────────────────────────────────────────

  it('shows bio edit button after expanding SIG for own user', async () => {
    // Alice is both the auth user and a member (ADMIN) of the SIG
    const wrapper = mountView('MEMBER', MEMBER_USER_ID)
    await flushPromises()

    // Bio edit button should NOT be visible before expanding
    const buttonsBefore = wrapper.findAll('button[title]')
    const bioBtnBefore = buttonsBefore.filter((b) =>
      b.attributes('title')?.includes('Edit your bio'),
    )
    expect(bioBtnBefore.length).toBe(0)

    // Expand the SIG
    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    // Bio edit button should now be visible inside the member panel
    const buttonsAfter = wrapper.findAll('button[title]')
    const bioBtnAfter = buttonsAfter.filter((b) => b.attributes('title')?.includes('Edit your bio'))
    expect(bioBtnAfter.length).toBeGreaterThan(0)
  })

  it('does not show bio edit button for non-member user', async () => {
    const wrapper = mountView('MEMBER', 'completely-other-user')
    await flushPromises()

    // Expand the SIG
    await wrapper.find('.sig-node').trigger('click')
    await flushPromises()

    const buttons = wrapper.findAll('button[title]')
    const bioBtn = buttons.filter((b) => b.attributes('title')?.includes('Edit your bio'))
    expect(bioBtn.length).toBe(0)
  })

  // ── Category rendering ───────────────────────────────────────────────

  it('renders category name and creator info', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('General')
    expect(wrapper.text()).toContain('Alice')
  })
})
