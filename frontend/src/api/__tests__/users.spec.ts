import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()
const mockPatch = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
  },
}))

import {
  getProfile,
  updateProfile,
  uploadAvatar,
  changePassword,
  acceptConsent,
  deleteAccount,
  getPublicProfile,
  applyForMembership,
  getMyApplication,
} from '../users'

describe('users API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getProfile', () => {
    it('calls GET /users/me and returns data', async () => {
      const mockData = { id: 'u-1', username: 'alice', display_name: 'Alice', role: 'MEMBER' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getProfile()

      expect(mockGet).toHaveBeenCalledWith('/users/me')
      expect(result).toEqual(mockData)
    })

    it('calls GET /users/me exactly once', async () => {
      mockGet.mockResolvedValue({ data: { id: 'u-1' } })

      await getProfile()

      expect(mockGet).toHaveBeenCalledTimes(1)
    })
  })

  describe('updateProfile', () => {
    it('calls PUT /users/me with payload and returns data', async () => {
      const payload = { display_name: 'Updated Name', bio: 'New bio' }
      const mockData = { id: 'u-1', display_name: 'Updated Name' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updateProfile(payload)

      expect(mockPut).toHaveBeenCalledWith('/users/me', payload)
      expect(result).toEqual(mockData)
    })

    it('calls PUT /users/me with all optional fields', async () => {
      const payload = {
        display_name: 'Alice Smith',
        bio: 'Researcher',
        affiliation: 'MIT',
        orcid: '0000-0001-2345-6789',
      }
      mockPut.mockResolvedValue({ data: { id: 'u-1' } })

      await updateProfile(payload)

      expect(mockPut).toHaveBeenCalledWith('/users/me', payload)
    })

    it('calls PUT /users/me with partial payload', async () => {
      const payload = { bio: 'Just a bio update' }
      mockPut.mockResolvedValue({ data: { id: 'u-1' } })

      await updateProfile(payload)

      expect(mockPut).toHaveBeenCalledWith('/users/me', payload)
    })
  })

  describe('uploadAvatar', () => {
    it('calls PUT /users/me/avatar with FormData and multipart/form-data header', async () => {
      const file = new File(['image-content'], 'avatar.png', { type: 'image/png' })
      const mockData = { id: 'u-1', avatar_url: 'https://example.com/avatar.png' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await uploadAvatar(file)

      expect(mockPut).toHaveBeenCalledTimes(1)
      const [url, formData, config] = mockPut.mock.calls[0]
      expect(url).toBe('/users/me/avatar')
      expect(formData).toBeInstanceOf(FormData)
      expect(formData.get('file')).toBe(file)
      expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
      expect(result).toEqual(mockData)
    })

    it('appends the file under the key "file" in FormData', async () => {
      const file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' })
      mockPut.mockResolvedValue({ data: { id: 'u-1' } })

      await uploadAvatar(file)

      const formData: FormData = mockPut.mock.calls[0][1]
      expect(formData.get('file')).toBe(file)
    })

    it('returns updated UserProfile from uploadAvatar', async () => {
      const file = new File(['data'], 'img.png', { type: 'image/png' })
      const mockData = { id: 'u-1', display_name: 'Alice', avatar_url: 'http://cdn/avatar.png' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await uploadAvatar(file)

      expect(result).toEqual(mockData)
    })
  })

  describe('changePassword', () => {
    it('calls PUT /users/me/password with payload', async () => {
      const payload = { current_password: 'OldPass1!', new_password: 'NewPass2!' }
      mockPut.mockResolvedValue({})

      await changePassword(payload)

      expect(mockPut).toHaveBeenCalledWith('/users/me/password', payload)
    })

    it('calls PUT /users/me/password exactly once', async () => {
      mockPut.mockResolvedValue({})

      await changePassword({ current_password: 'old', new_password: 'new' })

      expect(mockPut).toHaveBeenCalledTimes(1)
    })

    it('does not use GET, POST, DELETE, or PATCH', async () => {
      mockPut.mockResolvedValue({})

      await changePassword({ current_password: 'old', new_password: 'new' })

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPost).not.toHaveBeenCalled()
      expect(mockDelete).not.toHaveBeenCalled()
      expect(mockPatch).not.toHaveBeenCalled()
    })
  })

  describe('acceptConsent', () => {
    it('calls POST /users/me/consent', async () => {
      mockPost.mockResolvedValue({})

      await acceptConsent()

      expect(mockPost).toHaveBeenCalledWith('/users/me/consent')
    })

    it('calls POST /users/me/consent exactly once', async () => {
      mockPost.mockResolvedValue({})

      await acceptConsent()

      expect(mockPost).toHaveBeenCalledTimes(1)
    })

    it('does not use GET, PUT, DELETE, or PATCH', async () => {
      mockPost.mockResolvedValue({})

      await acceptConsent()

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
      expect(mockDelete).not.toHaveBeenCalled()
      expect(mockPatch).not.toHaveBeenCalled()
    })
  })

  describe('deleteAccount', () => {
    it('calls DELETE /users/me', async () => {
      mockDelete.mockResolvedValue({})

      await deleteAccount()

      expect(mockDelete).toHaveBeenCalledWith('/users/me')
    })

    it('calls DELETE /users/me exactly once', async () => {
      mockDelete.mockResolvedValue({})

      await deleteAccount()

      expect(mockDelete).toHaveBeenCalledTimes(1)
    })

    it('does not use GET, POST, or PUT', async () => {
      mockDelete.mockResolvedValue({})

      await deleteAccount()

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPost).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
    })
  })

  describe('getPublicProfile', () => {
    it('calls GET /users/{userId} and returns data', async () => {
      const mockData = { id: 'u-2', display_name: 'Bob', role: 'MEMBER' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getPublicProfile('u-2')

      expect(mockGet).toHaveBeenCalledWith('/users/u-2')
      expect(result).toEqual(mockData)
    })

    it('includes userId in the URL path', async () => {
      mockGet.mockResolvedValue({ data: { id: 'abc-123' } })

      await getPublicProfile('abc-123')

      expect(mockGet).toHaveBeenCalledWith('/users/abc-123')
    })

    it('does not call /users/me for public profile', async () => {
      mockGet.mockResolvedValue({ data: { id: 'u-5' } })

      await getPublicProfile('u-5')

      expect(mockGet).not.toHaveBeenCalledWith('/users/me')
    })
  })

  describe('applyForMembership', () => {
    const payload = {
      username: 'newuser',
      password: 'Passw0rd!',
      display_name: 'New User',
      description: 'I am a researcher in AI and language learning.',
    }

    it('calls POST /users/apply-member with full payload and returns data', async () => {
      const mockData = { message: 'Application submitted successfully.' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await applyForMembership(payload)

      expect(mockPost).toHaveBeenCalledWith('/users/apply-member', payload)
      expect(result).toEqual(mockData)
    })

    it('sends all fields in the request body', async () => {
      mockPost.mockResolvedValue({ data: { message: 'ok' } })

      await applyForMembership(payload)

      const callArgs = mockPost.mock.calls[0][1]
      expect(callArgs).toHaveProperty('username')
      expect(callArgs).toHaveProperty('password')
      expect(callArgs).toHaveProperty('display_name')
      expect(callArgs).toHaveProperty('description')
    })

    it('returns the message from the API response', async () => {
      mockPost.mockResolvedValue({ data: { message: 'Under review.' } })

      const result = await applyForMembership(payload)

      expect(result.message).toBe('Under review.')
    })
  })

  describe('getMyApplication', () => {
    it('calls GET /users/my-application and returns data', async () => {
      const mockData = { application: { id: '1', status: 'PENDING', created_at: '2026-03-19' } }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getMyApplication()

      expect(mockGet).toHaveBeenCalledWith('/users/my-application')
      expect(result.application?.status).toBe('PENDING')
    })

    it('returns null application when none exists', async () => {
      mockGet.mockResolvedValue({ data: { application: null } })

      const result = await getMyApplication()

      expect(result.application).toBeNull()
    })
  })
})
