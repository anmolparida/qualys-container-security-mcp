import type { ChatRequest, ChatMessage, DashboardEndpoint } from '../types/api'
import { authHeaders, llmHeaders, signalAuthRequired } from './credentials'

const BASE = '/api'

export type AuthMode = 'service' | 'user'

async function authFailure(res: Response): Promise<never> {
  let message = 'Please sign in to Qualys'
  try {
    const body = await res.json()
    if (body?.message) message = body.message
  } catch { /* ignore */ }
  signalAuthRequired(message)
  throw new Error(message)
}

export type LlmBilling = 'host' | 'user'

export async function fetchConfig(): Promise<{ auth_mode: AuthMode; llm_billing?: LlmBilling }> {
  const res = await fetch(`${BASE}/config`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

/** Validate credentials with a tiny Qualys call. Throws with Qualys's reason on failure. */
export async function checkSession(headers: Record<string, string>): Promise<void> {
  const res = await fetch(`${BASE}/session`, { headers })
  if (res.ok) return
  let message = `Sign-in failed (${res.status})`
  try {
    const body = await res.json()
    message = body?.message ?? body?.detail ?? message
  } catch { /* ignore */ }
  throw new Error(message)
}

/** Validate the user's own AI key with a tiny request billed to them. */
export async function checkLlm(headers: Record<string, string>): Promise<void> {
  const res = await fetch(`${BASE}/llm/check`, { method: 'POST', headers })
  if (res.ok) return
  let message = `AI key check failed (${res.status})`
  try {
    const body = await res.json()
    message = body?.message ?? message
  } catch { /* ignore */ }
  throw new Error(message)
}

export async function fetchDashboard<T = any>(path: DashboardEndpoint): Promise<T> {
  const res = await fetch(`${BASE}/dashboard/${path}`, { headers: authHeaders() })
  if (res.status === 401) return authFailure(res)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

const MAX_HISTORY = 10

export async function* streamChat(message: string, history: ChatMessage[]) {
  const trimmed = history.slice(-MAX_HISTORY)
  const body: ChatRequest = { message, history: trimmed }
  const res = await fetch(`${BASE}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...llmHeaders() },
    body: JSON.stringify(body),
  })
  if (res.status === 401) return authFailure(res)
  if (!res.ok) throw new Error(`Chat error ${res.status}`)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
}
