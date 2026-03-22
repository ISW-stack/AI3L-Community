import { describe, it, expect, beforeEach } from 'vitest'
import { useFormHistory } from '../useFormHistory'
import type { Question } from '@/types'

function makeQuestion(id: string, label: string): Question {
  return {
    id,
    type: 'text',
    label,
    required: true,
    placeholder: '',
    options: [],
    min: 1,
    max: 5,
  }
}

describe('useFormHistory', () => {
  let history: ReturnType<typeof useFormHistory>

  beforeEach(() => {
    history = useFormHistory()
  })

  it('starts with canUndo and canRedo as false', () => {
    expect(history.canUndo.value).toBe(false)
    expect(history.canRedo.value).toBe(false)
  })

  it('cannot undo with no states', () => {
    expect(history.undo()).toBeNull()
  })

  it('cannot redo with no states', () => {
    expect(history.redo()).toBeNull()
  })

  it('cannot undo with only one state', () => {
    history.pushState([makeQuestion('q1', 'Q1')])
    expect(history.canUndo.value).toBe(false)
    expect(history.undo()).toBeNull()
  })

  it('can undo after pushing two states', () => {
    const q1 = [makeQuestion('q1', 'Q1')]
    const q2 = [makeQuestion('q1', 'Q1'), makeQuestion('q2', 'Q2')]
    history.pushState(q1)
    history.pushState(q2)

    expect(history.canUndo.value).toBe(true)
    const result = history.undo()
    expect(result).toEqual(q1)
    expect(history.canUndo.value).toBe(false)
  })

  it('can redo after undo', () => {
    const q1 = [makeQuestion('q1', 'Q1')]
    const q2 = [makeQuestion('q1', 'Q1'), makeQuestion('q2', 'Q2')]
    history.pushState(q1)
    history.pushState(q2)

    history.undo()
    expect(history.canRedo.value).toBe(true)

    const result = history.redo()
    expect(result).toEqual(q2)
    expect(history.canRedo.value).toBe(false)
  })

  it('clears redo stack on new push after undo', () => {
    const q1 = [makeQuestion('q1', 'Q1')]
    const q2 = [makeQuestion('q1', 'Q1'), makeQuestion('q2', 'Q2')]
    const q3 = [makeQuestion('q1', 'Q1'), makeQuestion('q3', 'Q3')]

    history.pushState(q1)
    history.pushState(q2)
    history.undo()
    expect(history.canRedo.value).toBe(true)

    history.pushState(q3)
    expect(history.canRedo.value).toBe(false)
    expect(history.redo()).toBeNull()
  })

  it('does not push duplicate consecutive states', () => {
    const q1 = [makeQuestion('q1', 'Q1')]
    history.pushState(q1)
    history.pushState(q1)
    history.pushState(q1)

    expect(history.canUndo.value).toBe(false)
  })

  it('limits history to MAX_HISTORY entries', () => {
    // Use alternating types to guarantee each state is genuinely unique and
    // never deduplicated by the consecutive-duplicate check.
    const types = ['text', 'textarea', 'single_choice', 'multiple_choice', 'dropdown'] as const
    for (let i = 0; i < 60; i++) {
      const q = makeQuestion(`q${i}`, `Q${i}`)
      q.type = types[i % types.length]
      history.pushState([q])
    }
    // MAX_HISTORY = 20: undoStack is capped at 20 entries.
    // canUndo requires undoStack.length > 1, so exactly 19 undos are possible.
    expect(history.canUndo.value).toBe(true)
    let undoCount = 0
    while (history.undo() !== null) {
      undoCount++
    }
    expect(undoCount).toBe(19)
    expect(history.canUndo.value).toBe(false)
  })

  it('deep clones states so mutations do not affect history', () => {
    const questions = [makeQuestion('q1', 'Original')]
    history.pushState(questions)

    // Mutate original
    questions[0].label = 'Mutated'
    history.pushState(questions)

    const restored = history.undo()
    expect(restored![0].label).toBe('Original')
  })

  it('clear resets all state', () => {
    history.pushState([makeQuestion('q1', 'Q1')])
    history.pushState([makeQuestion('q2', 'Q2')])
    history.clear()

    expect(history.canUndo.value).toBe(false)
    expect(history.canRedo.value).toBe(false)
    expect(history.undo()).toBeNull()
    expect(history.redo()).toBeNull()
  })

  it('handles multiple undo/redo cycles', () => {
    const q1 = [makeQuestion('q1', 'Q1')]
    const q2 = [makeQuestion('q2', 'Q2')]
    const q3 = [makeQuestion('q3', 'Q3')]

    history.pushState(q1)
    history.pushState(q2)
    history.pushState(q3)

    // Undo twice
    expect(history.undo()).toEqual(q2)
    expect(history.undo()).toEqual(q1)
    expect(history.canUndo.value).toBe(false)

    // Redo twice
    expect(history.redo()).toEqual(q2)
    expect(history.redo()).toEqual(q3)
    expect(history.canRedo.value).toBe(false)
  })
})
