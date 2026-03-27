export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export interface Category {
  id: string
  name: string
  description: string | null
  post_count: number
}

export interface DashboardStats {
  users: number
  posts: number
  sigs: number
  forms: number
  pending_reports: number
  pending_applications: number
}

export interface AuditLog {
  id: string
  user_id: string
  username: string | null
  display_name: string | null
  action: string
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  created_at: string
}

export interface Report {
  id: string
  post_id: string
  user_id: string
  reason: string
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
  post_title: string | null
}

export interface Application {
  id: string
  user_id: string
  username: string
  display_name: string
  description: string
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

export interface InviteCode {
  id: string
  code: string
  creator_username: string | null
  consumed_by_username: string | null
  status: string
  created_at: string
  expires_at: string | null
}

export interface ExportProgress {
  task_id: string
  status: string
  phase: string | null
  current: number
  total: number
  detail: string | null
  zip_size: number
  download_url: string | null
  started_at: string | null
  error: string | null
}

export interface ExportHistoryItem {
  task_id: string
  status: string
  created_at: string
  created_by: string
  options: { include_database?: boolean; include_files?: boolean }
  file_size: number | null
  download_url: string | null
}
