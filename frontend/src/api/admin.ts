import api from '@/composables/api'
import type { DashboardStats, AuditLog, Application, Report, InviteCode } from '@/types'

/* ── Dashboard ─────────────────────────────────────────────── */

export async function getDashboard() {
  const { data } = await api.get('/admin/dashboard')
  return data as DashboardStats
}

/* ── Users ─────────────────────────────────────────────────── */

export interface AdminUser {
  id: string
  username: string
  display_name: string
  role: string
  is_banned: boolean
  ban_reason: string | null
}

export interface UsersListResponse {
  users: AdminUser[]
  total: number
}

export async function listUsers(params?: { page?: number; page_size?: number; search?: string }) {
  const { data } = await api.get('/users', { params })
  return data as UsersListResponse
}

export async function createAccount(payload: {
  username: string
  password: string
  display_name: string
  role: string
}) {
  const { data } = await api.post('/users/admin/create-account', payload)
  return data
}

export async function changeRole(userId: string, role: string) {
  await api.put(`/users/${userId}/role`, { role })
}

export async function banUser(userId: string, reason: string) {
  await api.post(`/users/${userId}/ban`, { reason })
}

export async function unbanUser(userId: string) {
  await api.post(`/users/${userId}/unban`)
}

/* ── Audit Logs ────────────────────────────────────────────── */

export interface AuditLogsResponse {
  logs: AuditLog[]
  total: number
}

export async function getAuditLogs(params: {
  page?: number
  page_size?: number
  user_id?: string
  date_from?: string
  date_to?: string
}) {
  const { data } = await api.get('/users/admin/audit-logs', { params })
  return data as AuditLogsResponse
}

/* ── Applications ──────────────────────────────────────────── */

export interface ApplicationsResponse {
  applications: Application[]
  total: number
}

export async function listApplications(params?: { status?: string }) {
  const { data } = await api.get('/admin/applications', { params })
  return data as ApplicationsResponse
}

export async function reviewApplication(appId: string, action: 'APPROVED' | 'REJECTED') {
  await api.put(`/admin/applications/${appId}/review`, { action })
}

/* ── Reports ───────────────────────────────────────────────── */

export interface ReportsResponse {
  reports: Report[]
  total: number
  total_pages?: number
}

export async function listReports(params?: {
  status_filter?: string
  page?: number
  page_size?: number
}) {
  const { data } = await api.get('/admin/reports', { params })
  return data as ReportsResponse
}

export async function reviewReport(reportId: string, status: string) {
  await api.put(`/admin/reports/${reportId}/review`, { status })
}

/* ── Invite Codes ──────────────────────────────────────────── */

export interface InviteCodesResponse {
  codes: InviteCode[]
  total: number
}

export async function listInviteCodes(params?: { status?: string }) {
  const { data } = await api.get('/admin/invite-codes', { params })
  return data as InviteCodesResponse
}

export async function createInviteCode() {
  const { data } = await api.post('/auth/invite-code')
  return data as { invite_code: string }
}
