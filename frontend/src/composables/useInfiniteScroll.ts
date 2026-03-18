import { onMounted, onUnmounted, watch, type Ref } from 'vue'

export interface InfiniteScrollOptions {
  threshold?: number
  rootMargin?: string
}

export function useInfiniteScroll(
  sentinelRef: Ref<HTMLElement | null>,
  onLoadMore: () => void,
  options: InfiniteScrollOptions = {},
) {
  const { threshold = 0.1, rootMargin = '0px' } = options
  let observer: IntersectionObserver | null = null
  let observedElement: HTMLElement | null = null

  function createObserver(el: HTMLElement) {
    if (observedElement === el) return
    observer?.disconnect()
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onLoadMore()
        }
      },
      { threshold, rootMargin },
    )
    observer.observe(el)
    observedElement = el
  }

  function destroyObserver() {
    observer?.disconnect()
    observer = null
    observedElement = null
  }

  onMounted(() => {
    if (sentinelRef.value) {
      createObserver(sentinelRef.value)
    }
  })

  // Watch for sentinel becoming available after mount (e.g. inside v-if)
  watch(sentinelRef, (newEl) => {
    if (newEl) {
      createObserver(newEl)
    } else {
      destroyObserver()
    }
  })

  onUnmounted(() => {
    destroyObserver()
  })
}
