import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AboutView from '../AboutView.vue'

const mockGet = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn(),
  },
}))

const mockContributors = [
  {
    id: 1,
    display_name: 'Alice',
    role: 'Project Lead',
    avatar_url: '/api/v1/about/contributors/1/avatar',
  },
  {
    id: 2,
    display_name: 'Bob',
    role: 'Developer',
    avatar_url: '/api/v1/about/contributors/2/avatar',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/about', component: AboutView }],
  })
}

async function mountAbout() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const wrapper = mount(AboutView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return wrapper
}

describe('AboutView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: { contributors: mockContributors } })
  })

  it('renders the About AI3L Community heading', async () => {
    const wrapper = await mountAbout()
    expect(wrapper.text()).toContain('About AI3L Community')
  })

  it('mentions Professor Yu-Ju Lan', async () => {
    const wrapper = await mountAbout()
    expect(wrapper.text()).toContain('Professor Yu-Ju Lan')
  })

  it('renders contributor avatars after API loads', async () => {
    const wrapper = await mountAbout()
    const images = wrapper.findAll('img')
    expect(images.length).toBe(2)
    expect(images[0].attributes('src')).toBe('/api/v1/about/contributors/1/avatar')
    expect(images[1].attributes('src')).toBe('/api/v1/about/contributors/2/avatar')
  })

  it('displays contributor names and roles', async () => {
    const wrapper = await mountAbout()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Project Lead')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Developer')
  })

  it('does not contain any GitHub links', async () => {
    const wrapper = await mountAbout()
    const links = wrapper.findAll('a')
    const githubLinks = links.filter((l) => (l.attributes('href') || '').includes('github.com'))
    expect(githubLinks.length).toBe(0)
  })

  it('shows loading state initially', () => {
    mockGet.mockReturnValue(new Promise(() => { })) // never resolves
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const wrapper = mount(AboutView, {
      global: { plugins: [pinia, router] },
    })
    expect(wrapper.text()).toContain('Loading contributors...')
  })

  it('handles API error gracefully', async () => {
    mockGet.mockRejectedValue(new Error('Network error'))
    const wrapper = await mountAbout()
    expect(wrapper.text()).toContain('No contributor information available')
  })
})
