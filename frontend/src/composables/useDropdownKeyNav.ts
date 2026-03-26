import { nextTick, isRef, type Ref } from 'vue'

export interface DropdownKeyNavOptions {
  isOpen: Ref<boolean> | (() => boolean)
  onOpen: () => void
  onClose: () => void
  wrapperClass: string
  triggerSelector?: string
}

function isElementVisible(el: HTMLElement): boolean {
  if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return false
  const style = getComputedStyle(el)
  return style.display !== 'none' && style.visibility !== 'hidden'
}

export function useDropdownKeyNav(options: DropdownKeyNavOptions) {
  const getIsOpen = () => {
    return isRef(options.isOpen) ? options.isOpen.value : options.isOpen()
  }

  const getVisibleItems = (wrapper: Element): HTMLElement[] => {
    return Array.from(wrapper.querySelectorAll<HTMLElement>('[tabindex="-1"]')).filter(
      isElementVisible,
    )
  }

  const handleDropdownKeydown = (e: KeyboardEvent) => {
    const wrapper =
      (e.target as HTMLElement).closest(`.${options.wrapperClass}`) ||
      (e.currentTarget as HTMLElement).closest(`.${options.wrapperClass}`)

    if (!wrapper) return

    const isOpen = getIsOpen()

    // If closed and user presses ArrowDown, open it
    if (!isOpen && e.key === 'ArrowDown') {
      e.preventDefault()
      options.onOpen()

      nextTick(() => {
        const menuItems = getVisibleItems(wrapper)
        menuItems[0]?.focus()
      })
      return
    }

    if (!isOpen) return

    if (e.key === 'Escape') {
      e.preventDefault()
      options.onClose()
      const trigger = options.triggerSelector
        ? (wrapper.querySelector(options.triggerSelector) as HTMLElement)
        : (wrapper.querySelector('button') as HTMLElement)
      trigger?.focus()
      return
    }

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const items = getVisibleItems(wrapper)
      const current = document.activeElement as HTMLElement
      const idx = items.indexOf(current)

      if (idx === -1) {
        if (e.key === 'ArrowDown') items[0]?.focus()
        else items[items.length - 1]?.focus()
      } else {
        const next =
          e.key === 'ArrowDown'
            ? items[(idx + 1) % items.length]
            : items[(idx - 1 + items.length) % items.length]
        next?.focus()
      }
      return
    }

    // Handle Space key for activation (standard for buttons, but needed for <a> tags)
    if (e.key === ' ') {
      const current = document.activeElement as HTMLElement
      if (current && (current.tagName === 'A' || current.tagName === 'BUTTON')) {
        e.preventDefault()
        current.click()
      }
    }
  }

  return {
    handleDropdownKeydown,
  }
}
