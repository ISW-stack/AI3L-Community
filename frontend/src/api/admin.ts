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

export async function bulkChangeRole(userIds: string[], role: string) {
  const { data } = await api.put('/users/bulk-role', { user_ids: userIds, role })
  return data as { updated_count: number }
}

export async function changeRole(userId: string, role: string) {
  const { data } = await api.put(`/users/${userId}/role`, { role })
  return data as AdminUser
}

export async function banUser(userId: string, reason: string) {
  await api.post(`/users/${userId}/ban`, { reason })
}

export async function unbanUser(userId: string) {
  await api.post(`/users/${userId}/unban`)
}

export async function deleteUser(userId: string, reason: string = '') {
  await api.delete(`/users/${userId}`, { data: { reason } })
}

/* ── IP Bans ──────────────────────────────────────────────── */

export interface IpBan {
  id: string
  ip_address: string
  reason: string
  banned_by: string | null
  expires_at: string | null
  created_at: string
}

export interface IpBansResponse {
  bans: IpBan[]
  total: number
}

export async function listIpBans(params?: { page?: number; page_size?: number }) {
  const { data } = await api.get('/admin/ip-bans', { params })
  return data as IpBansResponse
}

export async function createIpBan(payload: {
  ip_address: string
  reason?: string
  expires_at?: string
}) {
  const { data } = await api.post('/admin/ip-bans', payload)
  return data as IpBan
}

export async function deleteIpBan(banId: string) {
  await api.delete(`/admin/ip-bans/${banId}`)
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

export async function listApplications(params?: {
  status?: string
  page?: number
  page_size?: number
}) {
  const query: Record<string, string | number> = {}
  if (params?.status) query.status = params.status
  if (params?.page != null && params?.page_size != null) {
    query.offset = (params.page - 1) * params.page_size
    query.limit = params.page_size
  }
  const { data } = await api.get('/admin/applications', { params: query })
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

export async function listInviteCodes(params?: {
  status?: string
  page?: number
  page_size?: number
}) {
  const query: Record<string, string | number | undefined> = {}
  if (params?.status) query.status = params.status
  if (params?.page != null && params?.page_size != null) {
    query.offset = (params.page - 1) * params.page_size
    query.limit = params.page_size
  }
  const { data } = await api.get('/admin/invite-codes', { params: query })
  return data as InviteCodesResponse
}

export async function createInviteCode() {
  const { data } = await api.post('/auth/invite-code')
  return data as { invite_code: string }
}

export async function revokeInviteCode(codeId: string) {
  const { data } = await api.patch(`/admin/invite-codes/${codeId}/revoke`)
  return data as { message: string }
}

export async function deleteInviteCode(codeId: string) {
  await api.delete(`/admin/invite-codes/${codeId}`)
}
