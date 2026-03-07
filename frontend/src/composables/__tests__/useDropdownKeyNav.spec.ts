import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useDropdownKeyNav } from '../useDropdownKeyNav'

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
