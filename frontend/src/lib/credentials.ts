// Per-user Qualys credentials for "user" auth mode.
// Kept in sessionStorage (cleared when the tab closes) unless the user ticks
// "Remember on this device", which uses localStorage. Never sent anywhere except
// this app's own /api, as X-Qualys-* headers.

export interface QualysCredentials {
  url: string
  token: string
}

const KEY = 'qualys-credentials'
const EVENT = 'qualys-credentials-changed'

function read(store: Storage): QualysCredentials | null {
  try {
    const raw = store.getItem(KEY)
    if (!raw) return null
    const v = JSON.parse(raw)
    return v && typeof v.url === 'string' && typeof v.token === 'string' ? v : null
  } catch {
    return null
  }
}

export function getCredentials(): QualysCredentials | null {
  try {
    return read(sessionStorage) ?? read(localStorage)
  } catch {
    return null
  }
}

export function setCredentials(creds: QualysCredentials, remember: boolean) {
  clearCredentials(false)
  try {
    ;(remember ? localStorage : sessionStorage).setItem(KEY, JSON.stringify(creds))
  } catch {
    /* storage unavailable: credentials live only for this page load */
    memory = creds
  }
  window.dispatchEvent(new Event(EVENT))
}

export function clearCredentials(notify = true) {
  memory = null
  try { sessionStorage.removeItem(KEY) } catch { /* ignore */ }
  try { localStorage.removeItem(KEY) } catch { /* ignore */ }
  if (notify) window.dispatchEvent(new Event(EVENT))
}

let memory: QualysCredentials | null = null

export function currentCredentials(): QualysCredentials | null {
  return getCredentials() ?? memory
}

export function onCredentialsChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn)
  return () => window.removeEventListener(EVENT, fn)
}

/** Headers that carry the signed-in user's Qualys credentials to the backend. */
export function authHeaders(): Record<string, string> {
  const c = currentCredentials()
  return c ? { 'X-Qualys-Url': c.url, 'X-Qualys-Token': c.token } : {}
}

/** Short label for the signed-in account, e.g. "qg2". */
export function accountLabel(c: QualysCredentials | null): string {
  if (!c) return ''
  try {
    const host = new URL(c.url).hostname
    const pod = host.split('.').find(p => /^qg\d+$/i.test(p))
    return pod ?? host
  } catch {
    return c.url
  }
}

// ---- auth-required signal from the API layer to the UI ----
const REQUIRED = 'qualys-auth-required'
export function signalAuthRequired(message: string) {
  window.dispatchEvent(new CustomEvent(REQUIRED, { detail: message }))
}
export function onAuthRequired(fn: (message: string) => void): () => void {
  const h = (e: Event) => fn((e as CustomEvent).detail ?? '')
  window.addEventListener(REQUIRED, h)
  return () => window.removeEventListener(REQUIRED, h)
}

// ---- the user's own AI key (deployments with LLM_BILLING=user) ----

export interface LlmCredentials {
  provider: 'anthropic' | 'bedrock'
  apiKey: string
  region?: string   // bedrock only
  model?: string    // optional override
}

const LLM_KEY = 'llm-credentials'
let llmMemory: LlmCredentials | null = null

function readLlm(store: Storage): LlmCredentials | null {
  try {
    const raw = store.getItem(LLM_KEY)
    if (!raw) return null
    const v = JSON.parse(raw)
    return v && (v.provider === 'anthropic' || v.provider === 'bedrock') && typeof v.apiKey === 'string' ? v : null
  } catch {
    return null
  }
}

export function currentLlm(): LlmCredentials | null {
  try {
    return readLlm(sessionStorage) ?? readLlm(localStorage) ?? llmMemory
  } catch {
    return llmMemory
  }
}

export function setLlm(creds: LlmCredentials, remember: boolean) {
  clearLlm(false)
  try {
    ;(remember ? localStorage : sessionStorage).setItem(LLM_KEY, JSON.stringify(creds))
  } catch {
    llmMemory = creds
  }
  window.dispatchEvent(new Event(EVENT))
}

export function clearLlm(notify = true) {
  llmMemory = null
  try { sessionStorage.removeItem(LLM_KEY) } catch { /* ignore */ }
  try { localStorage.removeItem(LLM_KEY) } catch { /* ignore */ }
  if (notify) window.dispatchEvent(new Event(EVENT))
}

/** Headers that carry the user's own AI key; sent only on chat requests. */
export function llmHeaders(c: LlmCredentials | null = currentLlm()): Record<string, string> {
  if (!c) return {}
  const h: Record<string, string> = { 'X-LLM-Provider': c.provider, 'X-LLM-Api-Key': c.apiKey }
  if (c.provider === 'bedrock' && c.region) h['X-LLM-Region'] = c.region
  if (c.model) h['X-LLM-Model'] = c.model
  return h
}
