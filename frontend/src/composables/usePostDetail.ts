import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onUnmounted,
  type Ref,
  type ComputedRef,
} from 'vue'
import type { Post, HistoryItem, Comment } from '@/types'
import {
  getPost,
  updatePost,
  deletePost as apiDeletePost,
  getPostHistory,
  togglePinPost,
} from '@/api/posts'
import {
  listComments,
  createComment,
  deleteComment as apiDeleteComment,
  updateComment as apiUpdateComment,
  toggleReaction as apiToggleReaction,
} from '@/api/comments'
import { createReport } from '@/api/reports'
import { getFileScanStatus } from '@/api/files'
import DOMPurify from 'dompurify'
import { extractMentions } from '@/utils/html'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'

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

export interface UsePostDetailOptions {
  postId: Ref<string> | ComputedRef<string>
  auth: {
    user: { id: string } | null
    isAdmin: boolean
    isAuthenticated: boolean
    isGuest: boolean
  }
  router: { push: (path: string) => void }
}

export function usePostDetail(options: UsePostDetailOptions) {
  const { postId, auth, router } = options

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

  // --- Report ---
  const showReportModal = ref(false)
  const reportReason = ref('')
  const reportSaving = ref(false)
  const reportMessage = ref('')

  // --- Pin ---
  const pinSaving = ref(false)

  // --- VirusTotal scan ---
  const imageScanStatuses = ref<Record<string, 'pending' | 'clean' | 'malicious' | 'unknown'>>({})
  const postContentRef = ref<HTMLElement | null>(null)
  let scanPollTimers: ReturnType<typeof setTimeout>[] = []
  let isUnmounted = false

  // --- Computed ---
  const isAuthor = computed(() => post.value && auth.user && post.value.author.id === auth.user.id)
  const canModify = computed(() => isAuthor.value || auth.isAdmin)

  const canReport = computed(() => {
    if (!auth.isAuthenticated || auth.isGuest) return false
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
    const sanitized = DOMPurify.sanitize(post.value.content)

    const doc = new DOMParser().parseFromString(`<div>${sanitized}</div>`, 'text/html')
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

    const html = wrapper.innerHTML
    const parts = html.split(/(\x00CARD\d+\x00)/)
    const segments: ContentSegment[] = []
    for (const part of parts) {
      if (!part) continue
      const card = cardMap.get(part)
      if (card) {
        segments.push({ type: card.type, content: card.id })
      } else {
        segments.push({ type: 'html', content: part })
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
    } catch {
      if (!isUnmounted) post.value = null
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
    } catch (e) {
      console.error(e)
    }
  }

  function goToCommentPage(p: number) {
    setCommentPage(p)
    fetchComments()
  }

  async function fetchHistory() {
    try {
      history.value = await getPostHistory(postId.value)
      showHistory.value = true
    } catch (e) {
      console.error(e)
    }
  }

  function startEdit() {
    if (!post.value) return
    editTitle.value = post.value.title
    editContent.value = post.value.content
    editMessage.value = ''
    editing.value = true
  }

  async function saveEdit() {
    if (!post.value) return
    editSaving.value = true
    editMessage.value = ''
    try {
      post.value = await updatePost(postId.value, {
        title: editTitle.value,
        content: editContent.value,
        version: post.value.version,
      })
      editing.value = false
    } catch (err: unknown) {
      const apiError = err as {
        response?: { status?: number; data?: { detail?: string | { code?: string } } }
      }
      const detail = apiError.response?.data?.detail
      const code = typeof detail === 'object' ? detail?.code : undefined
      if (code === 'SYS_409' || apiError.response?.status === 409) {
        editMessage.value =
          'This post was edited by someone else. Please reload to see the latest version.'
      } else {
        editMessage.value = getErrorMessage(err, 'Failed to save changes.')
      }
    } finally {
      editSaving.value = false
    }
  }

  async function deletePostHandler() {
    try {
      await apiDeletePost(postId.value)
      router.push('/forum')
    } catch (e) {
      console.error(e)
    } finally {
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
    commentSaving.value = true
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
      commentSaving.value = false
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
      if (post.value && post.value.comment_count > 0) post.value.comment_count--
    } catch (e) {
      console.error(e)
    } finally {
      showDeleteCommentConfirm.value = false
      deleteTargetCommentId.value = null
    }
  }

  function canDeleteComment(comment: Comment): boolean {
    if (auth.isAdmin) return true
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
    } catch (e) {
      console.error(e)
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
    return new Date(dateStr).toLocaleDateString()
  }

  async function toggleReactionHandler(commentId: string, reaction: string) {
    try {
      await apiToggleReaction(postId.value, commentId, reaction)
      await fetchComments()
    } catch (e) {
      console.error(e)
    }
  }

  function getReactionCount(comment: Comment, reaction: string): number {
    return comment.reactions?.[reaction]?.length || 0
  }

  function hasReacted(comment: Comment, reaction: string): boolean {
    if (!auth.user) return false
    return comment.reactions?.[reaction]?.includes(auth.user.id) || false
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

  async function pollImageScanStatus(fileKey: string) {
    if (isUnmounted) return
    try {
      const data = await getFileScanStatus(fileKey)
      if (isUnmounted) return
      imageScanStatuses.value[fileKey] = data.status
      if (data.status === 'pending') {
        const timer = setTimeout(() => pollImageScanStatus(fileKey), 5000)
        scanPollTimers.push(timer)
      }
    } catch {
      // Endpoint not available or file not scanned - ignore
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
  watch(imageScanStatuses, () => applyMaliciousOverlays(), { deep: true })

  // --- Lifecycle ---
  onMounted(() => {
    fetchPost().then(() => scanPostImages())
    fetchComments()
  })

  onUnmounted(() => {
    isUnmounted = true
    scanPollTimers.forEach(clearTimeout)
    scanPollTimers = []
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
    // Report
    showReportModal,
    reportReason,
    reportSaving,
    reportMessage,
    canReport,
    // Pin
    pinSaving,
    // Permissions
    isAuthor,
    canModify,
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
