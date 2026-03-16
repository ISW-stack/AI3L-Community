export interface QuestionOption {
  id: string
  label: string
}

export interface Question {
  id: string
  type: string
  label: string
  required?: boolean
  placeholder?: string
  max_length?: number
  options?: QuestionOption[]
  min?: number
  max?: number
  labels?: Record<string, string>
  allowed_types?: string[]
  max_size_mb?: number
}

export interface FormData {
  id: string
  sig_id: string | null
  title: string
  description: string | null
  banner_url: string | null
  deadline: string | null
  max_respondents: number | null
  questions: Question[]
  is_schema_locked: boolean
  allow_non_members: boolean
  response_count: number
  has_responded?: boolean
  is_active: boolean
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
  user_is_sig_admin?: boolean
}

export interface FormResponse {
  id: string
  form_id?: string
  user_id?: string
  display_name: string
  username?: string
  created_at: string
  answers: Record<string, unknown>
}

export interface QuestionStats {
  question_id: string
  question_type: string
  question_label: string
  stats: Record<string, unknown>
}

export interface FormStatsResponse {
  form_id: string
  total_responses: number
  question_stats: QuestionStats[]
}
