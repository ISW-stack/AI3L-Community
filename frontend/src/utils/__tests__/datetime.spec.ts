import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { relativeTime } from '../datetime'

describe('relativeTime', () => {
  beforeEach(() => {
    // Fix Date.now to 2026-03-09T12:00:00.000Z for predictable tests
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-09T12:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('just now', () => {
    it('returns "just now" for current time', () => {
      expect(relativeTime('2026-03-09T12:00:00.000Z')).toBe('just now')
    })

    it('returns "just now" for 30 seconds ago', () => {
      expect(relativeTime('2026-03-09T11:59:30.000Z')).toBe('just now')
    })

    it('returns "just now" for 59 seconds ago', () => {
      expect(relativeTime('2026-03-09T11:59:01.000Z')).toBe('just now')
    })
  })

  describe('minutes ago', () => {
    it('returns "1 min ago" for exactly 1 minute ago', () => {
      expect(relativeTime('2026-03-09T11:59:00.000Z')).toBe('1 min ago')
    })

    it('returns "5 min ago" for 5 minutes ago', () => {
      expect(relativeTime('2026-03-09T11:55:00.000Z')).toBe('5 min ago')
    })

    it('returns "59 min ago" for 59 minutes ago', () => {
      expect(relativeTime('2026-03-09T11:01:00.000Z')).toBe('59 min ago')
    })

    it('returns "30 min ago" for 30 minutes ago', () => {
      expect(relativeTime('2026-03-09T11:30:00.000Z')).toBe('30 min ago')
    })
  })

  describe('hours ago', () => {
    it('returns "1h ago" for exactly 1 hour ago', () => {
      expect(relativeTime('2026-03-09T11:00:00.000Z')).toBe('1h ago')
    })

    it('returns "12h ago" for 12 hours ago', () => {
      expect(relativeTime('2026-03-09T00:00:00.000Z')).toBe('12h ago')
    })

    it('returns "23h ago" for 23 hours ago', () => {
      expect(relativeTime('2026-03-08T13:00:00.000Z')).toBe('23h ago')
    })
  })

  describe('days ago', () => {
    it('returns "1d ago" for exactly 1 day ago', () => {
      expect(relativeTime('2026-03-08T12:00:00.000Z')).toBe('1d ago')
    })

    it('returns "7d ago" for 7 days ago', () => {
      expect(relativeTime('2026-03-02T12:00:00.000Z')).toBe('7d ago')
    })

    it('returns "29d ago" for 29 days ago', () => {
      expect(relativeTime('2026-02-08T12:00:00.000Z')).toBe('29d ago')
    })
  })

  describe('locale date for older dates', () => {
    it('returns locale date string for 30 days ago', () => {
      const thirtyDaysAgo = '2026-02-07T12:00:00.000Z'
      const result = relativeTime(thirtyDaysAgo)
      const expected = new Date(thirtyDaysAgo).toLocaleDateString()
      expect(result).toBe(expected)
    })

    it('returns locale date string for 90 days ago', () => {
      const ninetyDaysAgo = '2025-12-10T12:00:00.000Z'
      const result = relativeTime(ninetyDaysAgo)
      const expected = new Date(ninetyDaysAgo).toLocaleDateString()
      expect(result).toBe(expected)
    })

    it('returns locale date string for a date over a year ago', () => {
      const oldDate = '2024-01-01T00:00:00.000Z'
      const result = relativeTime(oldDate)
      const expected = new Date(oldDate).toLocaleDateString()
      expect(result).toBe(expected)
    })
  })

  describe('edge cases', () => {
    it('handles ISO date with timezone offset', () => {
      expect(relativeTime('2026-03-09T11:00:00+00:00')).toBe('1h ago')
    })

    it('handles boundary between minutes and hours (exactly 60 minutes)', () => {
      expect(relativeTime('2026-03-09T11:00:00.000Z')).toBe('1h ago')
    })

    it('handles boundary between hours and days (exactly 24 hours)', () => {
      expect(relativeTime('2026-03-08T12:00:00.000Z')).toBe('1d ago')
    })

    it('handles boundary between days and locale date (exactly 30 days)', () => {
      const thirtyDaysAgo = new Date('2026-03-09T12:00:00.000Z')
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
      const iso = thirtyDaysAgo.toISOString()
      const result = relativeTime(iso)
      const expected = new Date(iso).toLocaleDateString()
      expect(result).toBe(expected)
    })
  })
})
