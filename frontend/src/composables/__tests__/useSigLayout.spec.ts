import { describe, it, expect, vi } from 'vitest'
import { defineComponent, ref, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useSigLayout } from '../useSigLayout'
import type { Sig } from '@/types/sig'

// Helper component that calls useSigLayout and exposes results
const TestConsumer = defineComponent({
  setup() {
    const result = useSigLayout()
    return { result }
  },
  render() {
    return h('div', 'consumer')
  },
})

// Helper component that provides inject values and renders the consumer
function createProvider(options: {
  sig?: Sig | null
  userSigRole?: string | null
  refreshSigRole?: () => Promise<void>
}) {
  return defineComponent({
    setup() {
      return {}
    },
    provide() {
      const provide: Record<string, unknown> = {}
      if ('sig' in options) {
        provide.sig = ref(options.sig)
      }
      if ('userSigRole' in options) {
        provide.userSigRole = ref(options.userSigRole)
      }
      if (options.refreshSigRole) {
        provide.refreshSigRole = options.refreshSigRole
      }
      return provide
    },
    render() {
      return h(TestConsumer)
    },
  })
}

const fakeSig: Sig = {
  id: 'sig-1',
  name: 'Test SIG',
  description: 'A test SIG',
  created_by: 'user-1',
  creator_display_name: 'Alice',
  member_count: 10,
  created_at: '2026-01-01T00:00:00Z',
}

describe('useSigLayout', () => {
  it('returns injected values when available', () => {
    const mockRefresh = vi.fn().mockResolvedValue(undefined)
    const Provider = createProvider({
      sig: fakeSig,
      userSigRole: 'ADMIN',
      refreshSigRole: mockRefresh,
    })

    const wrapper = mount(Provider)
    const consumer = wrapper.findComponent(TestConsumer)
    const result = (consumer.vm as InstanceType<typeof TestConsumer>).result

    expect(result.sig.value).toEqual(fakeSig)
    expect(result.userSigRole.value).toBe('ADMIN')
    expect(result.refreshSigRole).toBe(mockRefresh)
  })

  it('returns null sig value when provided as null', () => {
    const Provider = createProvider({
      sig: null,
      userSigRole: null,
    })

    const wrapper = mount(Provider)
    const consumer = wrapper.findComponent(TestConsumer)
    const result = (consumer.vm as InstanceType<typeof TestConsumer>).result

    expect(result.sig.value).toBeNull()
    expect(result.userSigRole.value).toBeNull()
  })

  it('refreshSigRole is undefined when not provided', () => {
    const Provider = createProvider({
      sig: fakeSig,
      userSigRole: 'MEMBER',
    })

    const wrapper = mount(Provider)
    const consumer = wrapper.findComponent(TestConsumer)
    const result = (consumer.vm as InstanceType<typeof TestConsumer>).result

    expect(result.refreshSigRole).toBeUndefined()
  })

  it('throws error when used outside SigLayout (no inject values)', () => {
    // Mount TestConsumer directly without any provider
    expect(() => {
      mount(TestConsumer)
    }).toThrow('useSigLayout must be used within SigLayout')
  })

  it('throws error when only sig is provided but userSigRole is missing', () => {
    const Provider = defineComponent({
      provide() {
        return {
          sig: ref(fakeSig),
          // userSigRole intentionally omitted
        }
      },
      render() {
        return h(TestConsumer)
      },
    })

    expect(() => {
      mount(Provider)
    }).toThrow('useSigLayout must be used within SigLayout')
  })

  it('throws error when only userSigRole is provided but sig is missing', () => {
    const Provider = defineComponent({
      provide() {
        return {
          userSigRole: ref('MEMBER'),
          // sig intentionally omitted
        }
      },
      render() {
        return h(TestConsumer)
      },
    })

    expect(() => {
      mount(Provider)
    }).toThrow('useSigLayout must be used within SigLayout')
  })
})
