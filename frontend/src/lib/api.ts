const BASE = '/api'

export async function fetchDashboard(path: string) {
  const res = await fetch(`${BASE}/dashboard/${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

const MAX_HISTORY = 10

export async function* streamChat(message: string, history: { role: string; content: string }[]) {
  const trimmed = history.slice(-MAX_HISTORY)
  const res = await fetch(`${BASE}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history: trimmed }),
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
