import type { AnalysisSummary, HealthStatus, Role, SessionState, Snapshot } from './types'

const TOKEN_KEY = 'ghost-fabric.api-token'
const ROLE_KEY = 'ghost-fabric.role'
const SUBJECT_KEY = 'ghost-fabric.subject'
/** UI preference only; not an audited scenario mutation. */
export const ONBOARDING_KEY = 'ghost-fabric.onboarding-v1'
const API_PREFIX = '/api/v1'

const DEMO_SESSIONS: Record<string, SessionState> = {
  '': { token: '', role: 'operator', subject: 'DEMO-OPERATOR' },
  'operator-token': { token: 'operator-token', role: 'operator', subject: 'DEMO-OPERATOR' },
  'viewer-token': { token: 'viewer-token', role: 'viewer', subject: 'DEMO-VIEWER' },
}

export function loadSession(): SessionState {
  const envToken = import.meta.env.VITE_API_TOKEN as string | undefined
  const storedToken = localStorage.getItem(TOKEN_KEY)
  const token = storedToken ?? envToken ?? ''
  const known = DEMO_SESSIONS[token]
  if (known) {
    return known
  }
  return {
    token,
    role: (localStorage.getItem(ROLE_KEY) as Role | null) ?? 'operator',
    subject: localStorage.getItem(SUBJECT_KEY) ?? 'DEMO-OPERATOR',
  }
}

export function saveSession(session: SessionState): void {
  localStorage.setItem(TOKEN_KEY, session.token)
  localStorage.setItem(ROLE_KEY, session.role)
  localStorage.setItem(SUBJECT_KEY, session.subject)
}

export function hasSeenOnboarding(): boolean {
  return localStorage.getItem(ONBOARDING_KEY) === 'seen'
}

export function markOnboardingSeen(): void {
  localStorage.setItem(ONBOARDING_KEY, 'seen')
}

function authHeaders(token: string, extra?: HeadersInit): Headers {
  const headers = new Headers(extra)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}

function withApiPrefix(path: string): string {
  if (path.startsWith('/api/v1/') || path === '/api/v1') return path
  if (path.startsWith('/api/')) return `${API_PREFIX}${path.slice(4)}`
  if (path.startsWith('/')) return `${API_PREFIX}${path}`
  return `${API_PREFIX}/${path}`
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const response = await fetch(withApiPrefix(path), { headers: authHeaders(token) })
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function apiCommand<T>(
  path: string,
  token: string,
  options?: RequestInit,
): Promise<T> {
  const headers = authHeaders(token, options?.headers)
  headers.set('X-Command-ID', crypto.randomUUID())
  if (options?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let response: Response
  try {
    response = await fetch(withApiPrefix(path), { ...options, headers })
  } catch {
    response = await fetch(withApiPrefix(path), { ...options, headers })
  }
  if (!response.ok) {
    throw new Error(`Command failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function fetchSnapshot(token: string): Promise<Snapshot> {
  return apiGet<Snapshot>('/scenario', token)
}

export async function fetchHealth(token: string): Promise<HealthStatus> {
  return apiGet<HealthStatus>('/health', token)
}

export async function fetchAnalysis(token: string): Promise<AnalysisSummary> {
  return apiGet<AnalysisSummary>('/analysis/summary', token)
}

export async function fetchAuditExport(token: string): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>('/audit/export', token)
}

export function confirmDestructive(message: string): boolean {
  return window.confirm(message)
}

export function canMutate(role: Role): boolean {
  return role === 'operator'
}
