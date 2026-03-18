import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

import { setAlbumCoverFromPhoto, uploadAlbumCover } from '../albums'

describe('albums cover API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('setAlbumCoverFromPhoto', () => {
    it('calls PUT /albums/{id}/cover with photo_id', async () => {
      const fakeAlbum = { id: 'a1', title: 'Test', cover_photo_url: 'http://example.com/cover.jpg' }
      mockPut.mockResolvedValue({ data: fakeAlbum })

      const result = await setAlbumCoverFromPhoto('a1', 'photo-1')

      expect(mockPut).toHaveBeenCalledWith('/albums/a1/cover', { photo_id: 'photo-1' })
      expect(result).toEqual(fakeAlbum)
    })

    it('returns album data directly (not wrapped in data)', async () => {
      const fakeAlbum = { id: 'a1', cover_photo_url: 'url' }
      mockPut.mockResolvedValue({ data: fakeAlbum })

      const result = await setAlbumCoverFromPhoto('a1', 'p1')

      expect(result).toEqual(fakeAlbum)
      expect(result).not.toHaveProperty('data')
    })
  })

  describe('uploadAlbumCover', () => {
    it('calls POST /albums/{id}/cover with FormData', async () => {
      const fakeAlbum = { id: 'a1', cover_photo_url: 'http://example.com/new-cover.jpg' }
      mockPost.mockResolvedValue({ data: fakeAlbum })

      const formData = new FormData()
      formData.append('file', new Blob(['test']), 'cover.jpg')

      const result = await uploadAlbumCover('a1', formData)

      expect(mockPost).toHaveBeenCalledWith('/albums/a1/cover', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      expect(result).toEqual(fakeAlbum)
    })

    it('returns album data directly', async () => {
      const fakeAlbum = { id: 'a2', cover_photo_url: 'url' }
      mockPost.mockResolvedValue({ data: fakeAlbum })

      const formData = new FormData()
      const result = await uploadAlbumCover('a2', formData)

      expect(result).toEqual(fakeAlbum)
    })
  })
})
