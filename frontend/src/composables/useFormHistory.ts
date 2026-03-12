import { ref, type Ref } from 'vue'
import type { Question } from '@/types'

export interface FormHistoryState {
  canUndo: Ref<boolean>
  canRedo: Ref<boolean>
  pushState: (questions: Question[]) => void
  undo: () => Question[] | null
  redo: () => Question[] | null
  clear: () => void
}

const MAX_HISTORY = 50

function deepCloneQuestions(questions: Question[]): Question[] {
  return JSON.parse(JSON.stringify(questions))
}

export function useFormHistory(): FormHistoryState {
  const undoStack = ref<string[]>([])
  const redoStack = ref<string[]>([])
  const canUndo = ref(false)
  const canRedo = ref(false)

  function updateFlags(): void {
    canUndo.value = undoStack.value.length > 1
    canRedo.value = redoStack.value.length > 0
  }

  function pushState(questions: Question[]): void {
    const snapshot = JSON.stringify(deepCloneQuestions(questions))
    // Avoid pushing duplicate consecutive states
    if (undoStack.value.length > 0 && undoStack.value[undoStack.value.length - 1] === snapshot) {
      return
    }
    undoStack.value.push(snapshot)
    if (undoStack.value.length > MAX_HISTORY) {
      undoStack.value.shift()
    }
    // Clear redo stack on new action
    redoStack.value = []
    updateFlags()
  }

  function undo(): Question[] | null {
    if (undoStack.value.length <= 1) return null
    const current = undoStack.value.pop()!
    redoStack.value.push(current)
    const previous = undoStack.value[undoStack.value.length - 1]
    updateFlags()
    return JSON.parse(previous) as Question[]
  }

  function redo(): Question[] | null {
    if (redoStack.value.length === 0) return null
    const next = redoStack.value.pop()!
    undoStack.value.push(next)
    updateFlags()
    return JSON.parse(next) as Question[]
  }

  function clear(): void {
    undoStack.value = []
    redoStack.value = []
    updateFlags()
  }

  return {
    canUndo,
    canRedo,
    pushState,
    undo,
    redo,
    clear,
  }
}
