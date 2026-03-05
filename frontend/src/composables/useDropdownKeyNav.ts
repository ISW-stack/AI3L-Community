import { nextTick, type Ref } from 'vue'

/**
 * Reusable keyboard navigation for dropdown menus.
 * Handles ArrowUp/Down, Escape, and Space activation following WAI-ARIA patterns.
 */
export function useDropdownKeyNav(
  isOpen: Ref<boolean>,
  options?: {
    onOpen?: () => void
    onClose?: () => void
  },
) {
  function focusFirstItem(wrapper: Element) {
    nextTick(() => {
      const items = wrapper.querySelectorAll<HTMLElement>('[tabindex="-1"]')
      items[0]?.focus()
    })
  }

  function handleKeydown(e: KeyboardEvent, wrapperSelector: string) {
    const wrapper =
      (e.target as HTMLElement).closest(wrapperSelector) ||
      (e.currentTarget as HTMLElement).closest(wrapperSelector)
    if (!wrapper) return

    // Open on ArrowDown when closed
    if (!isOpen.value && e.key === 'ArrowDown') {
      e.preventDefault()
      isOpen.value = true
      options?.onOpen?.()
      focusFirstItem(wrapper)
      return
    }

    if (!isOpen.value) return

    if (e.key === 'Escape') {
      e.preventDefault()
      isOpen.value = false
      options?.onClose?.()
      ;(wrapper.querySelector('button') as HTMLElement)?.focus()
      return
    }

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const items = Array.from(wrapper.querySelectorAll<HTMLElement>('[tabindex="-1"]'))
      const current = document.activeElement as HTMLElement
      const idx = items.indexOf(current)

      if (idx === -1) {
        ;(e.key === 'ArrowDown' ? items[0] : items[items.length - 1])?.focus()
      } else {
        const next =
          e.key === 'ArrowDown'
            ? items[(idx + 1) % items.length]
            : items[(idx - 1 + items.length) % items.length]
        next?.focus()
      }
      return
    }

    if (e.key === ' ') {
      const current = document.activeElement as HTMLElement
      if (current && (current.tagName === 'A' || current.tagName === 'BUTTON')) {
        e.preventDefault()
        current.click()
      }
    }
  }

  return { handleKeydown }
}
