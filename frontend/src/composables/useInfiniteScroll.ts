import { onMounted, onUnmounted, type Ref } from 'vue'

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

  onMounted(() => {
    if (!sentinelRef.value) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onLoadMore()
        }
      },
      { threshold, rootMargin },
    )
    observer.observe(sentinelRef.value)
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
  })
}
