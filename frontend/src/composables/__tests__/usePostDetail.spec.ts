import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { Post, Comment } from '@/types'

// Mock Vue lifecycle hooks to prevent them from firing during tests
const onMountedCallbacks: (() => void)[] = []
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb: () => void) => {
      onMountedCallbacks.push(cb)
    }),
    onUnmounted: vi.fn(),
  }
})

// Mock vue-router navigation guard to avoid "no active router" errors
vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    onBeforeRouteLeave: vi.fn(),
  }
})

// Mock all API modules
vi.mock('@/api/posts', () => ({
  getPost: vi.fn(),
  updatePost: vi.fn(),
  deletePost: vi.fn(),
  getPostHistory: vi.fn(),
  togglePinPost: vi.fn(),
  togglePostReaction: vi.fn(),
}))

vi.mock('@/api/comments', () => ({
  listComments: vi.fn(),
  createComment: vi.fn(),
  deleteComment: vi.fn(),
  updateComment: vi.fn(),
  toggleReaction: vi.fn(),
}))

vi.mock('@/api/reports', () => ({
  createReport: vi.fn(),
}))

vi.mock('@/api/files', () => ({
  getFileScanStatus: vi.fn(),
}))

vi.mock('dompurify', () => ({
  default: { sanitize: (html: string) => html },
}))

import { usePostDetail } from '../usePostDetail'
import { useToastStore } from '@/stores/toast'
import { getPost, updatePost, deletePost, getPostHistory, togglePinPost } from '@/api/posts'
import { listComments, createComment, deleteComment, toggleReaction } from '@/api/comments'
import { createReport } from '@/api/reports'

const mockGetPost = getPost as ReturnType<typeof vi.fn>
const mockUpdatePost = updatePost as ReturnType<typeof vi.fn>
const mockDeletePost = deletePost as ReturnType<typeof vi.fn>
const mockGetPostHistory = getPostHistory as ReturnType<typeof vi.fn>
const mockTogglePinPost = togglePinPost as ReturnType<typeof vi.fn>
const mockListComments = listComments as ReturnType<typeof vi.fn>
const mockCreateComment = createComment as ReturnType<typeof vi.fn>
const mockDeleteComment = deleteComment as ReturnType<typeof vi.fn>
const mockToggleReaction = toggleReaction as ReturnType<typeof vi.fn>
const mockCreateReport = createReport as ReturnType<typeof vi.fn>

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 'post1',
    title: 'Test Post',
    content: '<p>Hello</p>',
    author: { id: 'user1', username: 'alice', display_name: 'Alice', avatar_url: null },
    category_id: null,
    category_name: null,
    sig_id: null,
    sig_name: null,
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 0,
    is_pinned: false,
    view_count: 5,
    last_comment_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeComment(overrides: Partial<Comment> = {}): Comment {
  return {
    id: 'c1',
    post_id: 'post1',
    content: 'A comment',
    author: { id: 'user2', username: 'bob', display_name: 'Bob', avatar_url: null },
    parent_id: null,
    mentions: null,
    reactions: null,
    created_at: '2026-01-01T01:00:00Z',
    updated_at: '2026-01-01T01:00:00Z',
    ...overrides,
  }
}

function createDefaultAuth() {
  return {
    user: { id: 'user1' } as { id: string },
    isAdmin: false,
    isAuthenticated: true,
    isGuest: false,
  }
}

function createHarness(authOverrides: Partial<ReturnType<typeof createDefaultAuth>> = {}) {
  const postId = ref('post1')
  const mockRouter = { push: vi.fn() }
  const auth = { ...createDefaultAuth(), ...authOverrides }

  // Clear the captured callbacks before each harness creation
  onMountedCallbacks.length = 0

  const result = usePostDetail({ postId, auth, router: mockRouter })
  return { ...result, postId, mockRouter, auth }
}

describe('usePostDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    onMountedCallbacks.length = 0
    localStorage.clear()
    setActivePinia(createPinia())
    mockGetPost.mockResolvedValue(makePost())
    mockListComments.mockResolvedValue({ comments: [], total: 0 })
  })

  // 0. Instance isolation
  it('each usePostDetail() call gets independent state', async () => {
    const testPost1 = makePost({ id: 'post1', title: 'Post One' })
    const testPost2 = makePost({ id: 'post2', title: 'Post Two' })
    mockGetPost.mockResolvedValueOnce(testPost1).mockResolvedValueOnce(testPost2)
    mockListComments.mockResolvedValue({ comments: [], total: 0 })

    const harness1 = createHarness()
    const postId2 = ref('post2')
    const mockRouter2 = { push: vi.fn() }
    const auth2 = createDefaultAuth()
    onMountedCallbacks.length = 0
    const harness2 = usePostDetail({ postId: postId2, auth: auth2, router: mockRouter2 })

    await harness1.fetchPost()
    await harness2.fetchPost()

    // Each instance should have its own post state
    expect(harness1.post.value?.title).toBe('Post One')
    expect(harness2.post.value?.title).toBe('Post Two')

    // Modifying one should not affect the other
    harness1.editing.value = true
    expect(harness2.editing.value).toBe(false)

    harness1.newComment.value = 'Comment from harness1'
    expect(harness2.newComment.value).toBe('')
  })

  it('scan poll timers are instance-scoped', () => {
    const harness1 = createHarness()
    const postId2 = ref('post2')
    const mockRouter2 = { push: vi.fn() }
    const auth2 = createDefaultAuth()
    onMountedCallbacks.length = 0
    const harness2 = usePostDetail({ postId: postId2, auth: auth2, router: mockRouter2 })

    // Both instances should have independent imageScanStatuses
    harness1.imageScanStatuses.value['key1'] = 'clean'
    expect(harness2.imageScanStatuses.value['key1']).toBeUndefined()
  })

  // 1. Initial state
  it('has correct initial state', () => {
    const { post, loading, editing, comments, newComment, showHistory } = createHarness()
    expect(loading.value).toBe(true)
    expect(post.value).toBeNull()
    expect(editing.value).toBe(false)
    expect(comments.value).toEqual([])
    expect(newComment.value).toBe('')
    expect(showHistory.value).toBe(false)
  })

  // 2. fetchPost success
  it('fetchPost sets post and loading becomes false', async () => {
    const testPost = makePost({ title: 'Fetched' })
    mockGetPost.mockResolvedValue(testPost)

    const { post, loading, fetchPost } = createHarness()
    await fetchPost()

    expect(post.value).toEqual(testPost)
    expect(loading.value).toBe(false)
  })

  // 3. fetchPost failure
  it('fetchPost failure sets post to null', async () => {
    mockGetPost.mockRejectedValue(new Error('Not found'))

    const { post, loading, fetchPost } = createHarness()
    await fetchPost()

    expect(post.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  // 4. fetchComments success
  it('fetchComments populates comments and updates pagination', async () => {
    const testComments = [makeComment({ id: 'c1' }), makeComment({ id: 'c2' })]
    mockListComments.mockResolvedValue({ comments: testComments, total: 2 })

    const { comments, commentsTotal, fetchComments } = createHarness()
    await fetchComments()

    expect(comments.value).toEqual(testComments)
    expect(commentsTotal.value).toBe(2)
  })

  // 5. Comment pagination
  it('goToCommentPage changes page and re-fetches', async () => {
    mockListComments.mockResolvedValue({ comments: [], total: 40 })

    const { commentPage, goToCommentPage } = createHarness()
    await goToCommentPage(3)

    expect(commentPage.value).toBe(3)
    expect(mockListComments).toHaveBeenCalledWith('post1', { page: 3, page_size: 20 })
  })

  // 6. submitComment
  it('submitComment calls createComment, clears input, increments comment_count', async () => {
    const testPost = makePost({ comment_count: 5 })
    mockGetPost.mockResolvedValue(testPost)
    mockCreateComment.mockResolvedValue(makeComment())
    mockListComments.mockResolvedValue({ comments: [makeComment()], total: 1 })

    const { post, newComment, submitComment, fetchPost } = createHarness()
    await fetchPost()

    newComment.value = 'New comment text'
    await submitComment()

    expect(mockCreateComment).toHaveBeenCalledWith('post1', { content: 'New comment text' })
    expect(newComment.value).toBe('')
    expect(post.value!.comment_count).toBe(6)
  })

  // 7. deletePostHandler
  it('deletePostHandler calls apiDeletePost and navigates to /forum', async () => {
    mockDeletePost.mockResolvedValue(undefined)

    const { deletePostHandler, showDeletePostConfirm, mockRouter } = createHarness()
    showDeletePostConfirm.value = true
    await deletePostHandler()

    expect(mockDeletePost).toHaveBeenCalledWith('post1')
    expect(mockRouter.push).toHaveBeenCalledWith('/forum')
    expect(showDeletePostConfirm.value).toBe(false)
  })

  // 8. canModify
  it('canModify is true for author', async () => {
    const testPost = makePost({
      author: { id: 'user1', username: 'user1', display_name: 'Me', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' } })
    await fetchPost()

    expect(canModify.value).toBe(true)
  })

  it('canModify is true for admin even if not author', async () => {
    const testPost = makePost({
      author: { id: 'other', username: 'other', display_name: 'Other', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' }, isAdmin: true })
    await fetchPost()

    expect(canModify.value).toBe(true)
  })

  it('canModify is false for non-author non-admin', async () => {
    const testPost = makePost({
      author: { id: 'other', username: 'other', display_name: 'Other', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' }, isAdmin: false })
    await fetchPost()

    expect(canModify.value).toBe(false)
  })

  // 9. canReport
  it('canReport is false for guest', async () => {
    const testPost = makePost({
      author: { id: 'other', username: 'other', display_name: 'Other', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canReport, fetchPost } = createHarness({
      isGuest: true,
      isAuthenticated: true,
      user: { id: 'user1' },
    })
    await fetchPost()

    expect(canReport.value).toBe(false)
  })

  it('canReport is false for own post', async () => {
    const testPost = makePost({
      author: { id: 'user1', username: 'user1', display_name: 'Me', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canReport, fetchPost } = createHarness({ user: { id: 'user1' } })
    await fetchPost()

    expect(canReport.value).toBe(false)
  })

  it('canReport is true for authenticated non-guest on other user post', async () => {
    const testPost = makePost({
      author: { id: 'other', username: 'other', display_name: 'Other', avatar_url: null },
    })
    mockGetPost.mockResolvedValue(testPost)

    const { canReport, fetchPost } = createHarness({
      user: { id: 'user1' },
      isAuthenticated: true,
      isGuest: false,
    })
    await fetchPost()

    expect(canReport.value).toBe(true)
  })

  // 10. formatRelativeTime
  it('formatRelativeTime returns correct relative strings', () => {
    const { formatRelativeTime } = createHarness()

    // "just now" for < 60 seconds
    const now = new Date().toISOString()
    expect(formatRelativeTime(now)).toBe('just now')

    // minutes ago
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    expect(formatRelativeTime(fiveMinAgo)).toBe('5m ago')

    // hours ago
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString()
    expect(formatRelativeTime(threeHoursAgo)).toBe('3h ago')

    // days ago
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
    expect(formatRelativeTime(twoDaysAgo)).toBe('2d ago')

    // older than 7 days returns locale date string
    const twoWeeksAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000)
    expect(formatRelativeTime(twoWeeksAgo.toISOString())).toBe(twoWeeksAgo.toLocaleDateString())
  })

  // Additional: commentTree computed
  it('commentTree groups root and replies correctly', async () => {
    const root = makeComment({ id: 'r1', parent_id: null })
    const reply1 = makeComment({ id: 'rp1', parent_id: 'r1' })
    const reply2 = makeComment({ id: 'rp2', parent_id: 'r1' })
    const root2 = makeComment({ id: 'r2', parent_id: null })

    mockListComments.mockResolvedValue({
      comments: [root, reply1, root2, reply2],
      total: 4,
    })

    const { commentTree, fetchComments } = createHarness()
    await fetchComments()

    expect(commentTree.value).toHaveLength(2)
    expect(commentTree.value[0].root.id).toBe('r1')
    expect(commentTree.value[0].replies).toHaveLength(2)
    expect(commentTree.value[1].root.id).toBe('r2')
    expect(commentTree.value[1].replies).toHaveLength(0)
  })

  // Additional: saveEdit with 409 conflict
  it('saveEdit shows conflict message on 409', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)
    mockUpdatePost.mockRejectedValue({
      response: { status: 409, data: { detail: { code: 'SYS_409' } } },
    })

    const { fetchPost, startEdit, saveEdit, editMessage, editing } = createHarness()
    await fetchPost()
    startEdit()
    await saveEdit()

    expect(editMessage.value).toBe('VERSION_CONFLICT')
    expect(editing.value).toBe(true)
  })

  // Additional: saveEdit with non-409 error uses getErrorMessage
  it('saveEdit shows generic error for non-conflict failures', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)
    mockUpdatePost.mockRejectedValue({
      response: { status: 500, data: { detail: 'Internal error' } },
    })

    const { fetchPost, startEdit, saveEdit, editMessage } = createHarness()
    await fetchPost()
    startEdit()
    await saveEdit()

    expect(editMessage.value).toBe('Internal error')
  })

  // Additional: submitReport
  it('submitReport calls createReport and clears modal', async () => {
    mockCreateReport.mockResolvedValue(undefined)

    const { submitReport, reportReason, showReportModal } = createHarness()
    showReportModal.value = true
    reportReason.value = 'Spam content'
    await submitReport()

    expect(mockCreateReport).toHaveBeenCalledWith('post1', 'Spam content')
    expect(showReportModal.value).toBe(false)
    expect(reportReason.value).toBe('')
  })

  // Additional: handleReply toggles
  it('handleReply toggles inline reply', () => {
    const { inlineReplyTo, handleReply } = createHarness()

    handleReply('c1')
    expect(inlineReplyTo.value).toBe('c1')

    handleReply('c1')
    expect(inlineReplyTo.value).toBeNull()

    handleReply('c2')
    expect(inlineReplyTo.value).toBe('c2')
  })

  // saveEdit validation: empty title
  it('saveEdit rejects empty title without calling API', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)

    const { fetchPost, startEdit, saveEdit, editMessage, editTitle } = createHarness()
    await fetchPost()
    startEdit()
    editTitle.value = '   '
    await saveEdit()

    expect(mockUpdatePost).not.toHaveBeenCalled()
    expect(editMessage.value).toContain('Title cannot be empty')
  })

  // saveEdit validation: empty Tiptap content
  it('saveEdit rejects Tiptap empty content <p></p> without calling API', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)

    const { fetchPost, startEdit, saveEdit, editMessage, editContent } = createHarness()
    await fetchPost()
    startEdit()
    editContent.value = '<p></p>'
    await saveEdit()

    expect(mockUpdatePost).not.toHaveBeenCalled()
    expect(editMessage.value).toContain('Content cannot be empty')
  })

  // Draft save on edit
  it('draft is saved to localStorage when editing and title changes', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)

    const { fetchPost, startEdit, editTitle, editing } = createHarness()
    await fetchPost()
    startEdit()
    editing.value = true // ensure editing flag is set for the watch
    editTitle.value = 'Changed Title'

    // Wait for the watch to fire
    await new Promise((r) => setTimeout(r, 0))

    const stored = localStorage.getItem('post_edit_draft_post1')
    expect(stored).not.toBeNull()
    const parsed = JSON.parse(stored!)
    expect(parsed.title).toBe('Changed Title')
  })

  // Draft restore on startEdit
  it('startEdit restores draft from localStorage if recent', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)
    localStorage.setItem(
      'post_edit_draft_post1',
      JSON.stringify({ title: 'Draft Title', content: '<p>Draft</p>', savedAt: Date.now() }),
    )

    const { fetchPost, startEdit, editTitle, editContent } = createHarness()
    await fetchPost()
    startEdit()

    expect(editTitle.value).toBe('Draft Title')
    expect(editContent.value).toBe('<p>Draft</p>')
  })

  // cancelEdit clears draft
  it('cancelEdit clears draft and sets editing to false', async () => {
    const testPost = makePost({ version: 1 })
    mockGetPost.mockResolvedValue(testPost)
    localStorage.setItem(
      'post_edit_draft_post1',
      JSON.stringify({ title: 'Draft', content: '<p>X</p>', savedAt: Date.now() }),
    )

    const { fetchPost, startEdit, cancelEdit, editing } = createHarness()
    await fetchPost()
    startEdit()
    expect(editing.value).toBe(true)

    cancelEdit()
    expect(editing.value).toBe(false)
    expect(localStorage.getItem('post_edit_draft_post1')).toBeNull()
  })

  // saveEdit success clears draft
  it('saveEdit on success clears draft from localStorage', async () => {
    const testPost = makePost({ version: 1 })
    const updatedPost = makePost({ version: 2, title: 'New Title' })
    mockGetPost.mockResolvedValue(testPost)
    mockUpdatePost.mockResolvedValue(updatedPost)
    localStorage.setItem(
      'post_edit_draft_post1',
      JSON.stringify({ title: 'New Title', content: '<p>X</p>', savedAt: Date.now() }),
    )

    const { fetchPost, startEdit, saveEdit, editing } = createHarness()
    await fetchPost()
    startEdit()
    await saveEdit()

    expect(editing.value).toBe(false)
    expect(localStorage.getItem('post_edit_draft_post1')).toBeNull()
  })

  // Additional: canDeleteComment
  it('canDeleteComment returns true for admin', () => {
    const { canDeleteComment } = createHarness({ isAdmin: true })
    const comment = makeComment({
      author: { id: 'other', username: 'other', display_name: 'O', avatar_url: null },
    })
    expect(canDeleteComment(comment)).toBe(true)
  })

  it('canDeleteComment returns true for comment author', () => {
    const { canDeleteComment } = createHarness({ user: { id: 'user2' } })
    const comment = makeComment({
      author: { id: 'user2', username: 'bob', display_name: 'Bob', avatar_url: null },
    })
    expect(canDeleteComment(comment)).toBe(true)
  })

  it('canDeleteComment returns false for non-author non-admin', () => {
    const { canDeleteComment } = createHarness({ user: { id: 'user1' }, isAdmin: false })
    const comment = makeComment({
      author: { id: 'other', username: 'other', display_name: 'O', avatar_url: null },
    })
    expect(canDeleteComment(comment)).toBe(false)
  })

  // --- Error handling: toast notifications ---
  it('fetchPost failure shows toast error', async () => {
    mockGetPost.mockRejectedValue({ response: { data: { detail: 'Not found' } } })

    const { fetchPost } = createHarness()
    await fetchPost()

    const toast = useToastStore()
    expect(toast.toasts.length).toBe(1)
    expect(toast.toasts[0].message).toBe('Not found')
    expect(toast.toasts[0].type).toBe('error')
  })

  it('fetchComments failure shows toast error', async () => {
    mockListComments.mockRejectedValue(new Error('Network error'))

    const { fetchComments } = createHarness()
    await fetchComments()

    const toast = useToastStore()
    expect(toast.toasts.length).toBe(1)
    expect(toast.toasts[0].message).toBe('Failed to load comments.')
    expect(toast.toasts[0].type).toBe('error')
  })

  it('fetchHistory failure shows toast error', async () => {
    mockGetPostHistory.mockRejectedValue(new Error('Server error'))

    const { fetchHistory } = createHarness()
    await fetchHistory()

    const toast = useToastStore()
    expect(toast.toasts.length).toBe(1)
    expect(toast.toasts[0].message).toBe('Failed to load edit history.')
    expect(toast.toasts[0].type).toBe('error')
  })

  it('deletePostHandler failure shows toast error', async () => {
    mockDeletePost.mockRejectedValue({ response: { data: { detail: 'Forbidden' } } })

    const { deletePostHandler, showDeletePostConfirm } = createHarness()
    showDeletePostConfirm.value = true
    await deletePostHandler()

    const toast = useToastStore()
    expect(toast.toasts.length).toBe(1)
    expect(toast.toasts[0].message).toBe('Forbidden')
    expect(toast.toasts[0].type).toBe('error')
    expect(showDeletePostConfirm.value).toBe(false)
  })

  it('deleteCommentHandler failure shows toast error', async () => {
    const harness = createHarness()
    harness.showDeleteCommentConfirm.value = true
    harness.confirmDeleteComment('c1')
    mockDeleteComment.mockRejectedValue(new Error('Delete failed'))
    await harness.deleteCommentHandler()

    const toast = useToastStore()
    expect(
      toast.toasts.some((t: { message: string }) => t.message === 'Failed to delete comment.'),
    ).toBe(true)
  })

  // B06: deleteCommentHandler re-fetches post for accurate comment_count
  it('deleteCommentHandler re-fetches post comment_count instead of decrementing locally', async () => {
    // Post starts with comment_count 5 (1 root comment with 4 replies)
    const testPost = makePost({ comment_count: 5 })
    mockGetPost.mockResolvedValue(testPost)
    mockDeleteComment.mockResolvedValue(undefined)
    mockListComments.mockResolvedValue({ comments: [], total: 0 })

    const harness = createHarness()
    await harness.fetchPost()
    expect(harness.post.value!.comment_count).toBe(5)

    // Backend cascade-deletes the root + 4 replies, returning count=0
    mockGetPost.mockResolvedValue(makePost({ comment_count: 0 }))

    harness.confirmDeleteComment('c1')
    await harness.deleteCommentHandler()

    // Should be 0 (from server), not 4 (local decrement by 1)
    expect(harness.post.value!.comment_count).toBe(0)
    // getPost should have been called to re-fetch the accurate count
    expect(mockGetPost).toHaveBeenCalledTimes(2) // once for fetchPost, once for deleteCommentHandler
  })

  it('deleteCommentHandler gets accurate count even for single comment deletion', async () => {
    const testPost = makePost({ comment_count: 3 })
    mockGetPost.mockResolvedValue(testPost)
    mockDeleteComment.mockResolvedValue(undefined)
    mockListComments.mockResolvedValue({ comments: [], total: 0 })

    const harness = createHarness()
    await harness.fetchPost()

    // Backend deletes only 1 comment, returns count=2
    mockGetPost.mockResolvedValue(makePost({ comment_count: 2 }))

    harness.confirmDeleteComment('c1')
    await harness.deleteCommentHandler()

    expect(harness.post.value!.comment_count).toBe(2)
  })

  it('handleTogglePin failure shows toast error', async () => {
    const testPost = makePost({ is_pinned: false })
    mockGetPost.mockResolvedValue(testPost)
    mockTogglePinPost.mockRejectedValue(new Error('Pin failed'))

    const { fetchPost, handleTogglePin } = createHarness({ isAdmin: true })
    await fetchPost()
    await handleTogglePin()

    const toast = useToastStore()
    expect(toast.toasts.length).toBe(1)
    expect(toast.toasts[0].message).toBe('Failed to toggle pin.')
    expect(toast.toasts[0].type).toBe('error')
  })

  it('toggleReactionHandler failure shows toast error', async () => {
    mockToggleReaction.mockRejectedValue(new Error('Reaction failed'))

    const { toggleReactionHandler } = createHarness()
    await toggleReactionHandler('c1', 'LIKE')

    const toast = useToastStore()
    expect(
      toast.toasts.some((t: { message: string }) => t.message === 'Failed to toggle reaction.'),
    ).toBe(true)
  })
})

describe('usePostDetail — auth reactivity (N-U16)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    onMountedCallbacks.length = 0
    localStorage.clear()
    setActivePinia(createPinia())
    mockGetPost.mockResolvedValue({
      id: 'post1',
      title: 'Test Post',
      content: '<p>Hello</p>',
      author: { id: 'other-user', username: 'other', display_name: 'Other', avatar_url: null },
      category_id: null,
      category_name: null,
      sig_id: null,
      sig_name: null,
      keywords: null,
      allow_comments: true,
      version: 1,
      comment_count: 0,
      is_pinned: false,
      view_count: 5,
      last_comment_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    mockListComments.mockResolvedValue({ comments: [], total: 0 })
  })

  it('canModify reflects reactive isAdmin updates via MaybeRefOrGetter', () => {
    const isAdminRef = ref(false)
    const postId = ref('post1')
    const mockRouter = { push: vi.fn() }
    onMountedCallbacks.length = 0

    const result = usePostDetail({
      postId,
      auth: {
        user: { id: 'user1' },
        isAdmin: isAdminRef,
        isAuthenticated: true,
        isGuest: false,
      },
      router: mockRouter,
    })

    // Initially user is not author (post author is 'other-user'), not coAuthor, not admin
    expect(result.canModify.value).toBe(false)

    // Simulate admin privileges being granted reactively
    isAdminRef.value = true
    expect(result.canModify.value).toBe(true)

    // Revoke admin
    isAdminRef.value = false
    expect(result.canModify.value).toBe(false)
  })

  it('canReport reflects reactive isAuthenticated/isGuest updates', async () => {
    const isAuthenticatedRef = ref(false)
    const isGuestRef = ref(false)
    const postId = ref('post1')
    const mockRouter = { push: vi.fn() }
    onMountedCallbacks.length = 0

    const result = usePostDetail({
      postId,
      auth: {
        user: { id: 'user1' },
        isAdmin: false,
        isAuthenticated: isAuthenticatedRef,
        isGuest: isGuestRef,
      },
      router: mockRouter,
    })

    // Load the post so canReport has a non-null post.value (author is 'other-user')
    await result.fetchPost()

    // Not authenticated => canReport false
    expect(result.canReport.value).toBe(false)

    // Authenticate the user — post author is 'other-user', user is 'user1' => true
    isAuthenticatedRef.value = true
    expect(result.canReport.value).toBe(true)

    // Downgrade to guest => canReport false
    isGuestRef.value = true
    expect(result.canReport.value).toBe(false)
  })
})
