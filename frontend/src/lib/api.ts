import type { ChatRequest, ChatMessage, DashboardEndpoint } from '../types/api'

const BASE = '/api'

export async function fetchDashboard<T = any>(path: DashboardEndpoint): Promise<T> {
  const res = await fetch(`${BASE}/dashboard/${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

const MAX_HISTORY = 10

export async function* streamChat(message: string, history: ChatMessage[]) {
  const trimmed = history.slice(-MAX_HISTORY)
  const body: ChatRequest = { message, history: trimmed }
  const res = await fetch(`${BASE}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Chat error ${res.status}`)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
}
