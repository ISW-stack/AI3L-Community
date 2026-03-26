import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useDropdownKeyNav } from '../useDropdownKeyNav'

// jsdom does not compute layout, so offsetParent is always null.
// isElementVisible() checks offsetParent to detect hidden elements.
// We stub offsetParent on each item so it returns a truthy value for
// "visible" elements and null for elements we want to treat as hidden.
function stubOffsetParent(el: HTMLElement, parent: HTMLElement | null) {
  Object.defineProperty(el, 'offsetParent', {
    get: () => parent,
    configurable: true,
  })
}

function buildDOM(wrapperClass: string, triggerSelector?: string) {
  const wrapper = document.createElement('div')
  wrapper.classList.add(wrapperClass)

  const trigger = document.createElement('button')
  trigger.textContent = 'Toggle'
  if (triggerSelector) {
    // Apply selector as a class (strip leading dot)
    trigger.classList.add(triggerSelector.replace(/^\./, ''))
  }
  wrapper.appendChild(trigger)

  const menu = document.createElement('div')
  const items: HTMLElement[] = []
  for (let i = 0; i < 3; i++) {
    const item = document.createElement('a')
    item.setAttribute('tabindex', '-1')
    item.textContent = `Item ${i}`
    menu.appendChild(item)
    items.push(item)
    // By default, all items are "visible" (offsetParent = wrapper)
    stubOffsetParent(item, wrapper)
  }
  wrapper.appendChild(menu)

  document.body.appendChild(wrapper)
  return { wrapper, trigger, items }
}

function makeKeyEvent(
  key: string,
  target: HTMLElement,
  currentTarget?: HTMLElement,
): KeyboardEvent {
  const event = new KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
  })
  Object.defineProperty(event, 'target', { value: target })
  if (currentTarget) {
    Object.defineProperty(event, 'currentTarget', { value: currentTarget })
  }
  return event
}

describe('useDropdownKeyNav', () => {
  const wrapperClass = 'dropdown-wrapper'
  let onOpen: ReturnType<typeof vi.fn>
  let onClose: ReturnType<typeof vi.fn>

  beforeEach(() => {
    onOpen = vi.fn()
    onClose = vi.fn()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('ArrowDown when closed calls onOpen', () => {
    const { trigger } = buildDOM(wrapperClass)
    const isOpen = ref(false)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const event = makeKeyEvent('ArrowDown', trigger)
    handleDropdownKeydown(event)

    expect(onOpen).toHaveBeenCalledOnce()
  })

  it('ArrowDown when closed focuses first menu item', async () => {
    const { trigger, items } = buildDOM(wrapperClass)
    const isOpen = ref(false)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const event = makeKeyEvent('ArrowDown', trigger)
    handleDropdownKeydown(event)

    await nextTick()

    expect(document.activeElement).toBe(items[0])
  })

  it('Escape when open calls onClose', () => {
    const { items } = buildDOM(wrapperClass)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const event = makeKeyEvent('Escape', items[0])
    handleDropdownKeydown(event)

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('Escape when open focuses the trigger button', () => {
    const { trigger, items } = buildDOM(wrapperClass)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const event = makeKeyEvent('Escape', items[0])
    handleDropdownKeydown(event)

    expect(document.activeElement).toBe(trigger)
  })

  it('Escape with custom triggerSelector focuses the specified element', () => {
    const triggerSelector = '.custom-trigger'
    const { items } = buildDOM(wrapperClass, triggerSelector)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
      triggerSelector,
    })

    const event = makeKeyEvent('Escape', items[0])
    handleDropdownKeydown(event)

    const customTrigger = document.querySelector(triggerSelector) as HTMLElement
    expect(document.activeElement).toBe(customTrigger)
  })

  it('ArrowDown cycles forward through items', () => {
    const { items } = buildDOM(wrapperClass)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    // Focus the first item
    items[0].focus()
    expect(document.activeElement).toBe(items[0])

    // ArrowDown -> second item
    handleDropdownKeydown(makeKeyEvent('ArrowDown', items[0]))
    expect(document.activeElement).toBe(items[1])

    // ArrowDown -> third item
    handleDropdownKeydown(makeKeyEvent('ArrowDown', items[1]))
    expect(document.activeElement).toBe(items[2])

    // ArrowDown -> wraps to first item
    handleDropdownKeydown(makeKeyEvent('ArrowDown', items[2]))
    expect(document.activeElement).toBe(items[0])
  })

  it('ArrowUp cycles backward through items (wraps around)', () => {
    const { items } = buildDOM(wrapperClass)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    // Focus the first item
    items[0].focus()
    expect(document.activeElement).toBe(items[0])

    // ArrowUp -> wraps to last item
    handleDropdownKeydown(makeKeyEvent('ArrowUp', items[0]))
    expect(document.activeElement).toBe(items[2])

    // ArrowUp -> second item
    handleDropdownKeydown(makeKeyEvent('ArrowUp', items[2]))
    expect(document.activeElement).toBe(items[1])

    // ArrowUp -> first item
    handleDropdownKeydown(makeKeyEvent('ArrowUp', items[1]))
    expect(document.activeElement).toBe(items[0])
  })

  it('Space key clicks the focused element', () => {
    const { items } = buildDOM(wrapperClass)
    const isOpen = ref(true)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const clickSpy = vi.fn()
    items[1].addEventListener('click', clickSpy)
    items[1].focus()

    const event = makeKeyEvent(' ', items[1])
    handleDropdownKeydown(event)

    expect(clickSpy).toHaveBeenCalledOnce()
  })

  it('does nothing when wrapper element is not found', () => {
    // Do NOT build DOM with the wrapperClass — no matching wrapper exists
    const orphan = document.createElement('button')
    document.body.appendChild(orphan)

    const isOpen = ref(false)
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen,
      onOpen,
      onClose,
      wrapperClass,
    })

    const event = makeKeyEvent('ArrowDown', orphan, orphan)
    handleDropdownKeydown(event)

    expect(onOpen).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  // ---------- F-11: hidden/invisible elements are skipped ----------

  describe('skips hidden and invisible elements', () => {
    it('ArrowDown skips display:none items', () => {
      const { items } = buildDOM(wrapperClass)
      // Hide the second item
      items[1].style.display = 'none'
      stubOffsetParent(items[1], null)
      const isOpen = ref(true)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      items[0].focus()
      expect(document.activeElement).toBe(items[0])

      // ArrowDown should skip item[1] (display:none) and go to item[2]
      handleDropdownKeydown(makeKeyEvent('ArrowDown', items[0]))
      expect(document.activeElement).toBe(items[2])
    })

    it('ArrowUp skips display:none items', () => {
      const { items } = buildDOM(wrapperClass)
      items[1].style.display = 'none'
      stubOffsetParent(items[1], null)
      const isOpen = ref(true)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      items[2].focus()
      expect(document.activeElement).toBe(items[2])

      // ArrowUp should skip item[1] (display:none) and go to item[0]
      handleDropdownKeydown(makeKeyEvent('ArrowUp', items[2]))
      expect(document.activeElement).toBe(items[0])
    })

    it('ArrowDown skips visibility:hidden items', () => {
      const { items } = buildDOM(wrapperClass)
      // visibility:hidden keeps offsetParent in real browsers, so we keep it set
      // isElementVisible detects it via getComputedStyle().visibility check
      items[1].style.visibility = 'hidden'
      const isOpen = ref(true)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      items[0].focus()

      handleDropdownKeydown(makeKeyEvent('ArrowDown', items[0]))
      expect(document.activeElement).toBe(items[2])
    })

    it('wraps correctly when last visible item reached', () => {
      const { items } = buildDOM(wrapperClass)
      // Hide item[2] — only item[0] and item[1] are visible
      items[2].style.display = 'none'
      stubOffsetParent(items[2], null)
      const isOpen = ref(true)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      items[1].focus()

      // ArrowDown from last visible item should wrap to first visible item
      handleDropdownKeydown(makeKeyEvent('ArrowDown', items[1]))
      expect(document.activeElement).toBe(items[0])
    })

    it('ArrowDown when closed focuses first visible item (skips hidden)', async () => {
      const { trigger, items } = buildDOM(wrapperClass)
      // Hide item[0]
      items[0].style.display = 'none'
      stubOffsetParent(items[0], null)
      const isOpen = ref(false)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      handleDropdownKeydown(makeKeyEvent('ArrowDown', trigger))

      await nextTick()

      // Should focus item[1] since item[0] is hidden
      expect(document.activeElement).toBe(items[1])
    })

    it('navigation works when multiple consecutive items are hidden', () => {
      const { items } = buildDOM(wrapperClass)
      // Hide items[0] and items[1] — only items[2] is visible
      items[0].style.display = 'none'
      stubOffsetParent(items[0], null)
      items[1].style.visibility = 'hidden'
      stubOffsetParent(items[1], null)
      const isOpen = ref(true)
      const { handleDropdownKeydown } = useDropdownKeyNav({
        isOpen,
        onOpen,
        onClose,
        wrapperClass,
      })

      items[2].focus()

      // ArrowDown from the only visible item wraps to itself
      handleDropdownKeydown(makeKeyEvent('ArrowDown', items[2]))
      expect(document.activeElement).toBe(items[2])

      // ArrowUp also wraps to itself
      handleDropdownKeydown(makeKeyEvent('ArrowUp', items[2]))
      expect(document.activeElement).toBe(items[2])
    })
  })

  it('works with getter function for isOpen', () => {
    const { trigger, items } = buildDOM(wrapperClass)
    let open = false
    const { handleDropdownKeydown } = useDropdownKeyNav({
      isOpen: () => open,
      onOpen,
      onClose,
      wrapperClass,
    })

    // When closed, ArrowDown calls onOpen
    handleDropdownKeydown(makeKeyEvent('ArrowDown', trigger))
    expect(onOpen).toHaveBeenCalledOnce()

    // Simulate open state via getter
    open = true

    // When open, Escape calls onClose
    items[0].focus()
    handleDropdownKeydown(makeKeyEvent('Escape', items[0]))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
