import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
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

// Mock all API modules
vi.mock('@/api/posts', () => ({
  getPost: vi.fn(),
  updatePost: vi.fn(),
  deletePost: vi.fn(),
  getPostHistory: vi.fn(),
  togglePinPost: vi.fn(),
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
import { getPost, updatePost, deletePost, getPostHistory, togglePinPost } from '@/api/posts'
import { listComments, createComment, deleteComment, updateComment } from '@/api/comments'
import { createReport } from '@/api/reports'

const mockGetPost = getPost as ReturnType<typeof vi.fn>
const mockUpdatePost = updatePost as ReturnType<typeof vi.fn>
const mockDeletePost = deletePost as ReturnType<typeof vi.fn>
const mockGetPostHistory = getPostHistory as ReturnType<typeof vi.fn>
const mockListComments = listComments as ReturnType<typeof vi.fn>
const mockCreateComment = createComment as ReturnType<typeof vi.fn>
const mockDeleteComment = deleteComment as ReturnType<typeof vi.fn>
const mockUpdateComment = updateComment as ReturnType<typeof vi.fn>
const mockCreateReport = createReport as ReturnType<typeof vi.fn>
const mockTogglePinPost = togglePinPost as ReturnType<typeof vi.fn>

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 'post1',
    title: 'Test Post',
    content: '<p>Hello</p>',
    author: { id: 'user1', display_name: 'Alice', avatar_url: null },
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
    author: { id: 'user2', display_name: 'Bob', avatar_url: null },
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
    mockGetPost.mockResolvedValue(makePost())
    mockListComments.mockResolvedValue({ comments: [], total: 0 })
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
    const testPost = makePost({ author: { id: 'user1', display_name: 'Me', avatar_url: null } })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' } })
    await fetchPost()

    expect(canModify.value).toBe(true)
  })

  it('canModify is true for admin even if not author', async () => {
    const testPost = makePost({ author: { id: 'other', display_name: 'Other', avatar_url: null } })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' }, isAdmin: true })
    await fetchPost()

    expect(canModify.value).toBe(true)
  })

  it('canModify is false for non-author non-admin', async () => {
    const testPost = makePost({ author: { id: 'other', display_name: 'Other', avatar_url: null } })
    mockGetPost.mockResolvedValue(testPost)

    const { canModify, fetchPost } = createHarness({ user: { id: 'user1' }, isAdmin: false })
    await fetchPost()

    expect(canModify.value).toBe(false)
  })

  // 9. canReport
  it('canReport is false for guest', async () => {
    const testPost = makePost({ author: { id: 'other', display_name: 'Other', avatar_url: null } })
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
    const testPost = makePost({ author: { id: 'user1', display_name: 'Me', avatar_url: null } })
    mockGetPost.mockResolvedValue(testPost)

    const { canReport, fetchPost } = createHarness({ user: { id: 'user1' } })
    await fetchPost()

    expect(canReport.value).toBe(false)
  })

  it('canReport is true for authenticated non-guest on other user post', async () => {
    const testPost = makePost({
      author: { id: 'other', display_name: 'Other', avatar_url: null },
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

    expect(editMessage.value).toContain('edited by someone else')
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

  // Additional: canDeleteComment
  it('canDeleteComment returns true for admin', () => {
    const { canDeleteComment } = createHarness({ isAdmin: true })
    const comment = makeComment({ author: { id: 'other', display_name: 'O', avatar_url: null } })
    expect(canDeleteComment(comment)).toBe(true)
  })

  it('canDeleteComment returns true for comment author', () => {
    const { canDeleteComment } = createHarness({ user: { id: 'user2' } })
    const comment = makeComment({ author: { id: 'user2', display_name: 'Bob', avatar_url: null } })
    expect(canDeleteComment(comment)).toBe(true)
  })

  it('canDeleteComment returns false for non-author non-admin', () => {
    const { canDeleteComment } = createHarness({ user: { id: 'user1' }, isAdmin: false })
    const comment = makeComment({ author: { id: 'other', display_name: 'O', avatar_url: null } })
    expect(canDeleteComment(comment)).toBe(false)
  })
})
