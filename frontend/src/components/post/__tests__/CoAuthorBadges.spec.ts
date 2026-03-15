import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CoAuthorBadges from '../CoAuthorBadges.vue'
import type { CoAuthor } from '../../../types/coauthor'

vi.mock('@/components/base/BaseAvatar.vue', () => ({
  default: {
    props: ['src', 'name', 'size'],
    template: '<img :alt="name" />',
  },
}))

function makeCoAuthor(overrides: Partial<CoAuthor> = {}): CoAuthor {
  return {
    id: 'ca-1',
    post_id: 'post-1',
    user_id: 'user-1',
    display_name: 'Alice',
    affiliation: null,
    orcid: null,
    is_external: false,
    status: 'ACCEPTED',
    avatar_url: null,
    invited_at: new Date().toISOString(),
    responded_at: null,
    ...overrides,
  }
}

describe('CoAuthorBadges', () => {
  it('renders nothing when coAuthors is empty', () => {
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors: [] },
    })
    expect(wrapper.text()).toBe('')
  })

  it('renders co-author names', () => {
    const coAuthors = [
      makeCoAuthor({ id: 'ca-1', display_name: 'Alice' }),
      makeCoAuthor({ id: 'ca-2', display_name: 'Bob' }),
    ]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    expect(wrapper.text()).toContain('with')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('shows "and N more" when more than 3 co-authors', () => {
    const coAuthors = [
      makeCoAuthor({ id: 'ca-1', display_name: 'Alice' }),
      makeCoAuthor({ id: 'ca-2', display_name: 'Bob' }),
      makeCoAuthor({ id: 'ca-3', display_name: 'Carol' }),
      makeCoAuthor({ id: 'ca-4', display_name: 'Dave' }),
      makeCoAuthor({ id: 'ca-5', display_name: 'Eve' }),
    ]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Carol')
    expect(wrapper.text()).not.toContain('Dave')
    expect(wrapper.text()).not.toContain('Eve')
    expect(wrapper.text()).toContain('and 2 more')
  })

  it('does not show "and N more" when exactly 3 co-authors', () => {
    const coAuthors = [
      makeCoAuthor({ id: 'ca-1', display_name: 'Alice' }),
      makeCoAuthor({ id: 'ca-2', display_name: 'Bob' }),
      makeCoAuthor({ id: 'ca-3', display_name: 'Carol' }),
    ]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Carol')
    expect(wrapper.text()).not.toContain('more')
  })

  it('renders avatar components for visible co-authors', () => {
    const coAuthors = [
      makeCoAuthor({ id: 'ca-1', display_name: 'Alice' }),
      makeCoAuthor({ id: 'ca-2', display_name: 'Bob' }),
    ]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    const imgs = wrapper.findAll('img')
    expect(imgs.length).toBe(2)
    expect(imgs[0].attributes('alt')).toBe('Alice')
    expect(imgs[1].attributes('alt')).toBe('Bob')
  })

  it('shows single co-author with "with" prefix', () => {
    const coAuthors = [makeCoAuthor({ id: 'ca-1', display_name: 'Alice' })]
    const wrapper = mount(CoAuthorBadges, {
      props: { coAuthors },
    })
    expect(wrapper.text()).toContain('with')
    expect(wrapper.text()).toContain('Alice')
  })
})
