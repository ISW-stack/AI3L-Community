import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onUnmounted,
  type Ref,
  type ComputedRef,
  type MaybeRefOrGetter,
  toValue,
} from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import type { Post, HistoryItem, Comment } from '@/types'
import type { CoAuthor } from '@/types/coauthor'
import type { CitationEntry } from '@/types/citation'
import {
  getPost,
  updatePost,
  deletePost as apiDeletePost,
  getPostHistory,
  togglePinPost,
  togglePostReaction as apiTogglePostReaction,
} from '@/api/posts'
import {
  listComments,
  createComment,
  deleteComment as apiDeleteComment,
  updateComment as apiUpdateComment,
  toggleReaction as apiToggleReaction,
} from '@/api/comments'
import { createReport } from '@/api/reports'
import { getMySigRole } from '@/api/sigs'
import { getFileScanStatus } from '@/api/files'
import { listCoAuthors } from '@/api/coauthors'
import { getCitedBy, getCiting } from '@/api/citations'
import { sanitizeHtml, addLinkSafety } from '@/utils/sanitize'
import { extractMentions } from '@/utils/html'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { formatDate } from '@/utils/date'
import { i18n } from '@/locales'

export interface CommentNode {
  root: Comment
  replies: Comment[]
}

export interface ContentSegment {
  type: 'html' | 'sig-card' | 'form-card'
  content: string
}

export const UUID_RE =
  /\/(sigs|forms)\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i

export const FILE_CONTENT_RE = /\/api\/v1\/files\/content\/(.+)/

const domParser = new DOMParser()

export interface AuthLike {
  user: { id: string } | null
  isAdmin: MaybeRefOrGetter<boolean>
  isAuthenticated: MaybeRefOrGetter<boolean>
  isGuest: MaybeRefOrGetter<boolean>
}

export interface UsePostDetailOptions {
  postId: Ref<string> | ComputedRef<string>
  auth: AuthLike
  router: { push: (path: string) => void }
}

export function usePostDetail(options: UsePostDetailOptions) {
  const { postId, auth, router } = options
  const toastStore = useToastStore()

  // Wrap auth fields in computed so they stay reactive even if the caller passes
  // a plain Pinia store (where properties are getters, not plain booleans).
  const authIsAdmin = computed(() => toValue(auth.isAdmin))
  const authIsAuthenticated = computed(() => toValue(auth.isAuthenticated))
  const authIsGuest = computed(() => toValue(auth.isGuest))

  // --- Post state ---
  const post = ref<Post | null>(null)
  const loading = ref(true)
  const history = ref<HistoryItem[]>([])
  const showHistory = ref(false)

  // --- Edit state ---
  const editing = ref(false)
  const editTitle = ref('')
  const editContent = ref('')
  const editSaving = ref(false)
  const editMessage = ref('')

  // --- Comment state ---
  const comments = ref<Comment[]>([])
  const {
    page: commentPage,
    total: commentsTotal,
    totalPages: commentTotalPages,
    pageSize: commentPageSize,
    setPage: setCommentPage,
    updateFromResponse: updateCommentPagination,
  } = usePagination()

  const newComment = ref('')
  const commentSaving = ref(false)
  const replySaving = ref(false)
  const commentMessage = ref('')

  const inlineReplyTo = ref<string | null>(null)
  const inlineReplyContent = ref('')

  // --- Comment editing ---
  const editingComment = ref<string | null>(null)
  const editCommentContent = ref('')
  const editCommentSaving = ref(false)

  // --- Delete modals ---
  const showDeletePostConfirm = ref(false)
  const showDeleteCommentConfirm = ref(false)
  const deleteTargetCommentId = ref<string | null>(null)
  const isDeleting = ref(false)

  // --- Report ---
  const showReportModal = ref(false)
  const reportReason = ref('')
  const reportSaving = ref(false)
  const reportMessage = ref('')

  // --- Pin ---
  const pinSaving = ref(false)
  const sigRole = ref<string | null>(null)

  // --- Co-Authors ---
  const coAuthors = ref<CoAuthor[]>([])

  // --- Citations ---
  const citedBy = ref<CitationEntry[]>([])
  const citing = ref<CitationEntry[]>([])
  const citedByTotal = ref(0)
  const citingTotal = ref(0)

  // --- VirusTotal scan ---
  const imageScanStatuses = ref<
    Record<string, 'pending' | 'clean' | 'malicious' | 'unknown' | 'skipped' | 'timeout'>
  >({})
  const postContentRef = ref<HTMLElement | null>(null)

  // Instance-level state (must be inside function so each usePostDetail() call gets its own)
  const scanPollTimers = new Set<ReturnType<typeof setTimeout>>()
  let isUnmounted = false

  // --- Computed ---
  const isAuthor = computed(() => post.value && auth.user && post.value.author.id === auth.user.id)
  const isCoAuthor = computed(() => {
    if (!auth.user) return false
    return coAuthors.value.some((ca) => ca.user_id === auth.user!.id && ca.status === 'ACCEPTED')
  })
  const canModify = computed(() => isAuthor.value || authIsAdmin.value || isCoAuthor.value)

  const canPin = computed(() => {
    if (authIsAdmin.value) return true
    // SIG ADMIN can pin posts in their SIG
    if (post.value?.sig_id && sigRole.value === 'ADMIN') return true
    return false
  })

  const canReport = computed(() => {
    if (!authIsAuthenticated.value || authIsGuest.value) return false
    if (!post.value || !auth.user) return false
    return post.value.author.id !== auth.user.id
  })

  const commentTree = computed<CommentNode[]>(() => {
    const roots: Comment[] = []
    const replyMap: Record<string, Comment[]> = {}
    for (const c of comments.value) {
      if (!c.parent_id) {
        roots.push(c)
      } else {
        if (!replyMap[c.parent_id]) replyMap[c.parent_id] = []
        replyMap[c.parent_id].push(c)
      }
    }
    return roots.map((root) => ({
      root,
      replies: replyMap[root.id] || [],
    }))
  })

  const contentSegments = computed<ContentSegment[]>(() => {
    if (!post.value) return []
    const sanitized = addLinkSafety(sanitizeHtml(post.value.content))

    const doc = domParser.parseFromString(`<div>${sanitized}</div>`, 'text/html')
    const wrapper = doc.body.firstElementChild!

    let markerIndex = 0
    const cardMap = new Map<string, { type: 'sig-card' | 'form-card'; id: string }>()

    wrapper.querySelectorAll('a[href]').forEach((a) => {
      const href = a.getAttribute('href') || ''
      let path = href
      try {
        path = new URL(href, 'http://x').pathname
      } catch {
        /* href is already a relative path */
      }
      // Skip form edit/export sub-routes
      if (/\/(edit|export)$/.test(path)) return
      const m = UUID_RE.exec(path)
      if (!m) return

      const marker = `\x00CARD${markerIndex}\x00`
      const entityType = m[1].toLowerCase() === 'sigs' ? 'sig-card' : 'form-card'
      cardMap.set(marker, {
        type: entityType as 'sig-card' | 'form-card',
        id: m[2].toLowerCase(),
      })
      a.replaceWith(doc.createTextNode(marker))
      markerIndex++
    })

    if (cardMap.size === 0) {
      return [{ type: 'html', content: sanitized }]
    }

    // Split on markers BEFORE sanitizing — DOMPurify strips \x00 null bytes.
    // Each HTML fragment is individually sanitized below (line 231) to prevent mXSS.
    const html = wrapper.innerHTML
    const parts = html.split(/(\x00CARD\d+\x00)/)
    const segments: ContentSegment[] = []
    for (const part of parts) {
      if (!part) continue
      const card = cardMap.get(part)
      if (card) {
        segments.push({ type: card.type, content: card.id })
      } else {
        // Re-sanitize each HTML fragment after DOM manipulation to prevent mXSS.
        segments.push({ type: 'html', content: addLinkSafety(sanitizeHtml(part)) })
      }
    }
    return segments
  })

  // --- Methods ---

  async function fetchPost() {
    loading.value = true
    try {
      const data = await getPost(postId.value)
      if (isUnmounted) return
      post.value = data
      // Fetch SIG role for pin permission if this is a SIG post
      if (data.sig_id && toValue(auth.isAuthenticated) && !toValue(auth.isGuest)) {
        try {
          sigRole.value = await getMySigRole(data.sig_id)
        } catch {
          sigRole.value = null
        }
      } else {
        sigRole.value = null
      }
    } catch (e: unknown) {
      if (!isUnmounted) {
        post.value = null
        toastStore.show(getErrorMessage(e, 'Failed to load post.'), 'error')
      }
    } finally {
      if (!isUnmounted) loading.value = false
    }
  }

  async function fetchComments() {
    try {
      const data = await listComments(postId.value, {
        page: commentPage.value,
        page_size: commentPageSize,
      })
      if (isUnmounted) return
      comments.value = data.comments
      updateCommentPagination(data.total)
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to load comments.'), 'error')
    }
  }

  function goToCommentPage(p: number) {
    setCommentPage(p)
    fetchComments()
  }

  async function fetchHistory() {
    try {
      const result = await getPostHistory(postId.value)
      history.value = result.history
      showHistory.value = true
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to load edit history.'), 'error')
    }
  }

  async function fetchCoAuthors() {
    try {
      const res = await listCoAuthors(postId.value)
      coAuthors.value = res.co_authors
    } catch {
      // Silently fail — co-authors section is non-critical
    }
  }

  async function fetchCitedBy() {
    try {
      const res = await getCitedBy(postId.value)
      citedBy.value = res.citations
      citedByTotal.value = res.total
    } catch {
      // Silently fail
    }
  }

  async function fetchCiting() {
    try {
      const res = await getCiting(postId.value)
      citing.value = res.citations
      citingTotal.value = res.total
    } catch {
      // Silently fail
    }
  }

  const editDraftKey = () => {
    const uid = auth.user?.id ?? 'anon'
    return `post_edit_draft_${postId.value}_${uid}`
  }
  const EDIT_DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000

  function saveEditDraft() {
    try {
      localStorage.setItem(
        editDraftKey(),
        JSON.stringify({ title: editTitle.value, content: editContent.value, savedAt: Date.now() }),
      )
    } catch {
      /* storage full or private mode */
    }
  }

  function clearEditDraft() {
    localStorage.removeItem(editDraftKey())
  }

  function startEdit() {
    if (!post.value) return
    // Restore draft if recent, otherwise use current post data
    try {
      const raw = localStorage.getItem(editDraftKey())
      if (raw) {
        const draft = JSON.parse(raw)
        if (draft.savedAt && Date.now() - draft.savedAt < EDIT_DRAFT_MAX_AGE_MS) {
          editTitle.value = draft.title ?? post.value.title
          editContent.value = draft.content ?? post.value.content
          editMessage.value = ''
          editing.value = true
          return
        }
      }
    } catch {
      /* ignore malformed draft */
    }
    editTitle.value = post.value.title
    editContent.value = post.value.content
    editMessage.value = ''
    editing.value = true
  }

  function cancelEdit() {
    editing.value = false
    editMessage.value = ''
    clearEditDraft()
  }

  // Auto-save draft while editing
  watch([editTitle, editContent, editing], () => {
    if (editing.value) saveEditDraft()
  })

  async function saveEdit() {
    if (!post.value || editSaving.value) return
    if (!editTitle.value.trim()) {
      editMessage.value = 'Title cannot be empty.'
      return
    }
    const rawText = editContent.value.replace(/<[^>]*>/g, '').trim()
    if (!editContent.value || editContent.value === '<p></p>' || !rawText) {
      editMessage.value = 'Content cannot be empty.'
      return
    }
    editSaving.value = true
    editMessage.value = ''
    try {
      post.value = await updatePost(postId.value, {
        title: editTitle.value,
        content: editContent.value,
        version: post.value.version,
      })
      editing.value = false
      clearEditDraft()
    } catch (err: unknown) {
      const apiError = err as {
        response?: { status?: number; data?: { detail?: string | { code?: string } } }
      }
      const detail = apiError.response?.data?.detail
      const code = typeof detail === 'object' ? detail?.code : undefined
      if (code === 'SYS_409' || apiError.response?.status === 409) {
        editMessage.value = 'VERSION_CONFLICT'
      } else {
        editMessage.value = getErrorMessage(err, 'Failed to save changes.')
      }
    } finally {
      editSaving.value = false
    }
  }

  async function deletePostHandler() {
    if (isDeleting.value) return
    isDeleting.value = true
    try {
      await apiDeletePost(postId.value)
      router.push('/forum')
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to delete post.'), 'error')
    } finally {
      isDeleting.value = false
      showDeletePostConfirm.value = false
    }
  }

  async function submitComment() {
    if (!newComment.value.trim()) return
    commentSaving.value = true
    commentMessage.value = ''
    try {
      const mentions = extractMentions(newComment.value)
      await createComment(postId.value, {
        content: newComment.value,
        ...(mentions.length > 0 && { mentions }),
      })
      newComment.value = ''
      await fetchComments()
      if (post.value) post.value.comment_count++
    } catch (e: unknown) {
      commentMessage.value = getErrorMessage(e, 'Failed to post comment.')
    } finally {
      commentSaving.value = false
    }
  }

  async function submitInlineReply() {
    if (!inlineReplyTo.value || !inlineReplyContent.value.trim()) return
    replySaving.value = true
    commentMessage.value = ''
    try {
      const mentions = extractMentions(inlineReplyContent.value)
      await createComment(postId.value, {
        content: inlineReplyContent.value,
        parent_id: inlineReplyTo.value,
        ...(mentions.length > 0 && { mentions }),
      })
      inlineReplyTo.value = null
      inlineReplyContent.value = ''
      await fetchComments()
      if (post.value) post.value.comment_count++
    } catch (e: unknown) {
      commentMessage.value = getErrorMessage(e, 'Failed to post reply.')
    } finally {
      replySaving.value = false
    }
  }

  function confirmDeleteComment(commentId: string) {
    deleteTargetCommentId.value = commentId
    showDeleteCommentConfirm.value = true
  }

  async function deleteCommentHandler() {
    if (!deleteTargetCommentId.value) return
    try {
      await apiDeleteComment(postId.value, deleteTargetCommentId.value)
      await fetchComments()
      // Re-fetch post to get accurate comment_count after cascade deletion
      const updatedPost = await getPost(postId.value)
      if (post.value && updatedPost) {
        post.value.comment_count = updatedPost.comment_count
      }
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to delete comment.'), 'error')
    } finally {
      showDeleteCommentConfirm.value = false
      deleteTargetCommentId.value = null
    }
  }

  function canDeleteComment(comment: Comment): boolean {
    if (authIsAdmin.value) return true
    return !!(auth.user && comment.author.id === auth.user.id)
  }

  async function submitReport() {
    if (!reportReason.value.trim()) return
    reportSaving.value = true
    reportMessage.value = ''
    try {
      await createReport(postId.value, reportReason.value)
      showReportModal.value = false
      reportReason.value = ''
      reportMessage.value = ''
    } catch (e: unknown) {
      reportMessage.value = getErrorMessage(e, 'Failed to submit report.')
    } finally {
      reportSaving.value = false
    }
  }

  async function handleTogglePin() {
    if (!post.value) return
    pinSaving.value = true
    try {
      const result = await togglePinPost(post.value.id, !post.value.is_pinned)
      post.value.is_pinned = result.is_pinned
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to toggle pin.'), 'error')
    } finally {
      pinSaving.value = false
    }
  }

  function formatRelativeTime(dateStr: string): string {
    const now = Date.now()
    const diff = now - new Date(dateStr).getTime()
    const seconds = Math.floor(diff / 1000)
    if (seconds < 60) return 'just now'
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days}d ago`
    return formatDate(dateStr, i18n.global.locale.value)
  }

  async function toggleReactionHandler(commentId: string, reaction: string) {
    try {
      const updated = await apiToggleReaction(postId.value, commentId, reaction)
      const idx = comments.value.findIndex((c) => c.id === commentId)
      if (idx !== -1) {
        comments.value[idx] = updated
      }
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to toggle reaction.'), 'error')
    }
  }

  async function togglePostReactionHandler(reaction: string) {
    if (!post.value) return
    try {
      const updated = await apiTogglePostReaction(post.value.id, reaction)
      post.value = updated
    } catch (e: unknown) {
      toastStore.show(getErrorMessage(e, 'Failed to toggle reaction.'), 'error')
    }
  }

  function getPostReactionCount(reaction: string): number {
    return post.value?.reaction_counts?.[reaction] || 0
  }

  function hasPostReacted(reaction: string): boolean {
    return post.value?.user_reactions?.includes(reaction) || false
  }

  function getReactionCount(comment: Comment, reaction: string): number {
    return comment.reaction_counts?.[reaction] || 0
  }

  function hasReacted(comment: Comment, reaction: string): boolean {
    return comment.user_reactions?.includes(reaction) || false
  }

  function canEditComment(comment: Comment): boolean {
    return !!(auth.user && comment.author.id === auth.user.id)
  }

  function startEditComment(comment: Comment) {
    editingComment.value = comment.id
    editCommentContent.value = comment.content
  }

  function cancelEditComment() {
    editingComment.value = null
    editCommentContent.value = ''
  }

  async function saveEditComment(commentId: string) {
    if (!editCommentContent.value.trim()) return
    editCommentSaving.value = true
    try {
      await apiUpdateComment(postId.value, commentId, { content: editCommentContent.value })
      editingComment.value = null
      editCommentContent.value = ''
      await fetchComments()
    } catch (e: unknown) {
      commentMessage.value = getErrorMessage(e, 'Failed to update comment.')
    } finally {
      editCommentSaving.value = false
    }
  }

  function handleReply(commentId: string) {
    inlineReplyTo.value = inlineReplyTo.value === commentId ? null : commentId
    inlineReplyContent.value = ''
  }

  // --- VirusTotal scan ---

  function extractFileKeys(): string[] {
    if (!postContentRef.value) return []
    const imgs = postContentRef.value.querySelectorAll('img[src]')
    const keys: string[] = []
    imgs.forEach((img) => {
      const src = img.getAttribute('src') || ''
      const m = FILE_CONTENT_RE.exec(src)
      if (m) keys.push(m[1])
    })
    return [...new Set(keys)]
  }

  const MAX_SCAN_POLL_ATTEMPTS = 20 // ~100s at 5s intervals
  const scanPollAttempts = new Map<string, number>()

  async function pollImageScanStatus(fileKey: string) {
    if (isUnmounted) return
    const attempts = (scanPollAttempts.get(fileKey) ?? 0) + 1
    scanPollAttempts.set(fileKey, attempts)
    if (attempts > MAX_SCAN_POLL_ATTEMPTS) {
      imageScanStatuses.value[fileKey] = 'timeout'
      scanPollAttempts.delete(fileKey)
      return
    }
    try {
      const data = await getFileScanStatus(fileKey)
      if (isUnmounted) return
      imageScanStatuses.value[fileKey] = data.status
      if (data.status === 'pending') {
        const timer = setTimeout(() => {
          scanPollTimers.delete(timer)
          pollImageScanStatus(fileKey)
        }, 5000)
        scanPollTimers.add(timer)
      } else {
        scanPollAttempts.delete(fileKey)
      }
    } catch {
      // Endpoint not available or file not scanned - ignore
      scanPollAttempts.delete(fileKey)
    }
  }

  async function scanPostImages() {
    await nextTick()
    const keys = extractFileKeys()
    for (const key of keys) {
      pollImageScanStatus(key)
    }
  }

  function applyMaliciousOverlays() {
    if (!postContentRef.value?.isConnected) return
    const imgs = postContentRef.value.querySelectorAll('img[src]')
    imgs.forEach((img) => {
      const src = img.getAttribute('src') || ''
      const m = FILE_CONTENT_RE.exec(src)
      if (!m) return
      const status = imageScanStatuses.value[m[1]]
      const wrapper = img.parentElement
      if (!wrapper) return

      // Remove any existing overlay
      const existing = wrapper.querySelector('.vt-scan-overlay')
      if (existing) existing.remove()

      if (status === 'malicious') {
        if (getComputedStyle(wrapper).position === 'static') {
          ;(wrapper as HTMLElement).style.position = 'relative'
        }
        const overlay = document.createElement('div')
        overlay.className = 'vt-scan-overlay'
        overlay.style.cssText =
          'position:absolute;top:4px;left:4px;background:rgba(220,38,38,0.85);color:#fff;font-size:11px;padding:2px 6px;border-radius:4px;pointer-events:none;z-index:10;'
        overlay.textContent = 'Flagged as malicious'
        wrapper.appendChild(overlay)
      }
    })
  }

  // --- Watchers ---
  let overlayDebounceTimer: ReturnType<typeof setTimeout> | null = null
  watch(
    imageScanStatuses,
    () => {
      if (overlayDebounceTimer) clearTimeout(overlayDebounceTimer)
      overlayDebounceTimer = setTimeout(() => applyMaliciousOverlays(), 100)
    },
    { deep: true },
  )

  // Re-fetch when route param (postId) changes (component reuse)
  watch(postId, (newId, oldId) => {
    if (newId === oldId) return
    // Reset state
    post.value = null
    loading.value = true
    sigRole.value = null
    comments.value = []
    setCommentPage(1)
    coAuthors.value = []
    citedBy.value = []
    citing.value = []
    citedByTotal.value = 0
    citingTotal.value = 0
    history.value = []
    showHistory.value = false
    editing.value = false
    editMessage.value = ''
    newComment.value = ''
    commentMessage.value = ''
    inlineReplyTo.value = null
    inlineReplyContent.value = ''
    editingComment.value = null
    imageScanStatuses.value = {}
    // Clear scan poll timers
    scanPollTimers.forEach(clearTimeout)
    scanPollTimers.clear()
    if (overlayDebounceTimer) {
      clearTimeout(overlayDebounceTimer)
      overlayDebounceTimer = null
    }
    // Re-fetch — capture postId to prevent scan timers for stale post
    const capturedId = newId
    fetchPost().then(() => {
      if (postId.value === capturedId) scanPostImages()
    })
    fetchComments()
    fetchCoAuthors()
    fetchCitedBy()
    fetchCiting()
  })

  // --- Leave guard (unsaved edits) ---
  const showLeaveConfirm = ref(false)
  let pendingLeaveNext: ((val?: boolean) => void) | null = null

  onBeforeRouteLeave((_to, _from, next) => {
    if (editing.value) {
      showLeaveConfirm.value = true
      pendingLeaveNext = next
    } else {
      next()
    }
  })

  function confirmLeave() {
    showLeaveConfirm.value = false
    clearEditDraft()
    pendingLeaveNext?.()
    pendingLeaveNext = null
  }

  function cancelLeave() {
    showLeaveConfirm.value = false
    pendingLeaveNext?.(false)
    pendingLeaveNext = null
  }

  const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    if (editing.value) {
      e.preventDefault()
    }
  }

  // --- Lifecycle ---
  onMounted(() => {
    fetchPost().then(() => scanPostImages())
    fetchComments()
    fetchCoAuthors()
    fetchCitedBy()
    fetchCiting()
    window.addEventListener('beforeunload', handleBeforeUnload)
  })

  onUnmounted(() => {
    isUnmounted = true
    scanPollTimers.forEach(clearTimeout)
    scanPollTimers.clear()
    if (overlayDebounceTimer) clearTimeout(overlayDebounceTimer)
    window.removeEventListener('beforeunload', handleBeforeUnload)
  })

  return {
    // Post state
    post,
    loading,
    editing,
    editTitle,
    editContent,
    editSaving,
    editMessage,
    // Comment state
    comments,
    commentTree,
    commentPage,
    commentTotalPages,
    commentsTotal,
    newComment,
    commentSaving,
    replySaving,
    commentMessage,
    inlineReplyTo,
    inlineReplyContent,
    editingComment,
    editCommentContent,
    editCommentSaving,
    // History
    history,
    showHistory,
    // Delete modals
    showDeletePostConfirm,
    showDeleteCommentConfirm,
    isDeleting,
    // Leave guard
    showLeaveConfirm,
    confirmLeave,
    cancelLeave,
    // Report
    showReportModal,
    reportReason,
    reportSaving,
    reportMessage,
    canReport,
    // Pin
    pinSaving,
    canPin,
    // Permissions
    isAuthor,
    isCoAuthor,
    canModify,
    // Co-Authors
    coAuthors,
    fetchCoAuthors,
    // Citations
    citedBy,
    citing,
    citedByTotal,
    citingTotal,
    fetchCitedBy,
    fetchCiting,
    // Content segments
    contentSegments,
    // VirusTotal scan
    imageScanStatuses,
    postContentRef,
    // Methods
    fetchPost,
    fetchComments,
    goToCommentPage,
    fetchHistory,
    startEdit,
    cancelEdit,
    saveEdit,
    deletePostHandler,
    submitComment,
    submitInlineReply,
    confirmDeleteComment,
    deleteCommentHandler,
    canDeleteComment,
    submitReport,
    handleTogglePin,
    formatRelativeTime,
    toggleReactionHandler,
    togglePostReactionHandler,
    getPostReactionCount,
    hasPostReacted,
    getReactionCount,
    hasReacted,
    canEditComment,
    startEditComment,
    cancelEditComment,
    saveEditComment,
    handleReply,
    // Lifecycle
    scanPostImages,
  }
}
