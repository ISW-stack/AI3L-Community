import { describe, it, expect } from 'vitest'
import type { FormData, FormStatsResponse, QuestionStats, FormResponse, Question } from '../form'
import type { SigForm } from '../sig'

// These tests validate that the TypeScript interfaces match the backend Pydantic schemas.
// They use type-safe mock objects — if the type changes incompatibly, TS compilation fails.

describe('FormData type', () => {
  const validFormData: FormData = {
    id: 'f1',
    sig_id: 'sig-1',
    title: 'Survey',
    description: 'A description',
    banner_url: null,
    deadline: null,
    max_respondents: null,
    questions: [],
    is_schema_locked: false,
    allow_non_members: false,
    response_count: 0,
    is_active: true,
    created_by: 'user-1',
    created_by_name: 'Alice',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  it('accepts a valid FormData object', () => {
    expect(validFormData.id).toBe('f1')
    expect(validFormData.sig_id).toBe('sig-1')
    expect(validFormData.is_active).toBe(true)
  })

  it('has_responded is optional and defaults to undefined', () => {
    expect(validFormData.has_responded).toBeUndefined()
  })

  it('has_responded can be set to true', () => {
    const form: FormData = { ...validFormData, has_responded: true }
    expect(form.has_responded).toBe(true)
  })

  it('has_responded can be set to false', () => {
    const form: FormData = { ...validFormData, has_responded: false }
    expect(form.has_responded).toBe(false)
  })

  it('user_is_sig_admin is optional', () => {
    expect(validFormData.user_is_sig_admin).toBeUndefined()
  })

  it('user_is_sig_admin can be set', () => {
    const form: FormData = { ...validFormData, user_is_sig_admin: true }
    expect(form.user_is_sig_admin).toBe(true)
  })

  it('banner_url accepts a string URL', () => {
    const form: FormData = { ...validFormData, banner_url: 'https://example.com/img.png' }
    expect(form.banner_url).toBe('https://example.com/img.png')
  })

  it('description and banner_url can be null', () => {
    expect(validFormData.description).toBe('A description')
    expect(validFormData.banner_url).toBeNull()
  })
})

describe('FormStatsResponse type', () => {
  it('form_id is a string (UUID), not a number', () => {
    const stats: FormStatsResponse = {
      form_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      total_responses: 10,
      question_stats: [],
    }
    expect(typeof stats.form_id).toBe('string')
    expect(stats.form_id).toBe('a1b2c3d4-e5f6-7890-abcd-ef1234567890')
  })

  it('accepts question_stats with correct shape', () => {
    const qStats: QuestionStats = {
      question_id: 'q1',
      question_type: 'single_choice',
      question_label: 'Favorite color',
      stats: { red: 5, blue: 3 },
    }
    const stats: FormStatsResponse = {
      form_id: 'form-uuid',
      total_responses: 8,
      question_stats: [qStats],
    }
    expect(stats.question_stats).toHaveLength(1)
    expect(stats.question_stats[0].question_id).toBe('q1')
  })
})

describe('SigForm type', () => {
  const validSigForm: SigForm = {
    id: 'form-1',
    sig_id: 'sig-1',
    title: 'Feedback Survey',
    description: 'Please share feedback',
    banner_url: null,
    deadline: null,
    max_respondents: null,
    response_count: 5,
    allow_non_members: false,
    is_active: true,
    created_by: 'user-abc',
    created_by_name: 'Alice',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    user_is_sig_admin: true,
  }

  it('accepts a valid SigForm object', () => {
    expect(validSigForm.id).toBe('form-1')
    expect(validSigForm.created_by).toBe('user-abc')
    expect(validSigForm.user_is_sig_admin).toBe(true)
  })

  it('has banner_url field (string or null)', () => {
    expect(validSigForm.banner_url).toBeNull()
    const withBanner: SigForm = { ...validSigForm, banner_url: 'https://example.com/banner.jpg' }
    expect(withBanner.banner_url).toBe('https://example.com/banner.jpg')
  })

  it('has updated_at field (ISO string)', () => {
    expect(validSigForm.updated_at).toBe('2026-01-02T00:00:00Z')
  })

  it('has created_by field (user UUID string)', () => {
    expect(typeof validSigForm.created_by).toBe('string')
    expect(validSigForm.created_by).toBe('user-abc')
  })

  it('matches backend FormResponseSchema shape for list endpoint', () => {
    // Backend returns FormResponseSchema for both detail and list.
    // SigForm must include all fields returned by the list endpoint.
    const requiredKeys: (keyof SigForm)[] = [
      'id',
      'sig_id',
      'title',
      'description',
      'banner_url',
      'deadline',
      'max_respondents',
      'response_count',
      'allow_non_members',
      'is_active',
      'created_by',
      'created_by_name',
      'created_at',
      'updated_at',
      'user_is_sig_admin',
    ]
    for (const key of requiredKeys) {
      expect(key in validSigForm).toBe(true)
    }
  })
})

describe('FormResponse type', () => {
  it('has correct shape for individual response', () => {
    const resp: FormResponse = {
      id: 'resp-1',
      display_name: 'Alice',
      created_at: '2026-01-01T12:00:00Z',
      answers: { q1: 'answer1', q2: 42 },
    }
    expect(resp.id).toBe('resp-1')
    expect(resp.display_name).toBe('Alice')
    expect(resp.answers).toEqual({ q1: 'answer1', q2: 42 })
  })
})

describe('Question type', () => {
  it('accepts all optional fields', () => {
    const q: Question = {
      id: 'q1',
      type: 'rating',
      label: 'Rate satisfaction',
      required: true,
      min: 1,
      max: 5,
      labels: { '1': 'Very bad', '5': 'Excellent' },
    }
    expect(q.min).toBe(1)
    expect(q.max).toBe(5)
    expect(q.labels).toBeDefined()
  })

  it('accepts file_upload question fields', () => {
    const q: Question = {
      id: 'q2',
      type: 'file_upload',
      label: 'Upload resume',
      allowed_types: ['pdf', 'docx'],
      max_size_mb: 10,
    }
    expect(q.allowed_types).toEqual(['pdf', 'docx'])
    expect(q.max_size_mb).toBe(10)
  })
})
