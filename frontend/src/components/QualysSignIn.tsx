import { useState } from 'react'
import { KeyRound, Loader2, X } from 'lucide-react'
import { checkLlm, checkSession } from '../lib/api'
import {
  llmHeaders,
  setCredentials,
  setLlm,
  type LlmCredentials,
  type QualysCredentials,
} from '../lib/credentials'

// Common Qualys platform gateways; users on another platform pick "Other".
const GATEWAYS = [
  'https://gateway.qg1.apps.qualys.com',
  'https://gateway.qg2.apps.qualys.com',
  'https://gateway.qg3.apps.qualys.com',
  'https://gateway.qg4.apps.qualys.com',
  'https://gateway.qg1.apps.qualys.eu',
  'https://gateway.qg2.apps.qualys.eu',
  'https://gateway.qg1.apps.qualys.in',
  'https://gateway.qg1.apps.qualys.ca',
  'https://gateway.qg1.apps.qualys.ae',
  'https://gateway.qg1.apps.qualys.co.uk',
  'https://gateway.qg1.apps.qualys.com.au',
]

const REGIONS = ['us-east-1', 'us-east-2', 'us-west-2', 'eu-west-1', 'eu-central-1', 'ap-south-1', 'ap-southeast-2', 'ap-northeast-1', 'ca-central-1']

interface Props {
  /** Ask for the user's Qualys URL + token (QUALYS_AUTH_MODE=user). */
  needQualys: boolean
  /** Ask for the user's own AI key (LLM_BILLING=user). */
  needLlm: boolean
  initial?: QualysCredentials | null
  initialLlm?: LlmCredentials | null
  message?: string
  onDone: () => void
  onCancel?: () => void
}

export default function QualysSignIn({ needQualys, needLlm, initial, initialLlm, message, onDone, onCancel }: Props) {
  const initialPreset = initial?.url && GATEWAYS.includes(initial.url) ? initial.url : initial?.url ? 'other' : GATEWAYS[1]
  const [preset, setPreset] = useState(initialPreset)
  const [customUrl, setCustomUrl] = useState(initialPreset === 'other' ? initial?.url ?? '' : '')
  const [token, setToken] = useState('')

  const [provider, setProvider] = useState<LlmCredentials['provider']>(initialLlm?.provider ?? 'anthropic')
  const [apiKey, setApiKey] = useState('')
  const [region, setRegion] = useState(initialLlm?.region ?? 'us-east-1')
  const [model, setModel] = useState(initialLlm?.model ?? '')

  const [remember, setRemember] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(message ?? '')

  const url = (preset === 'other' ? customUrl : preset).trim().replace(/\/+$/, '')
  const qualysOk = !needQualys || (!!url && !!token.trim())
  const llmOk = !needLlm || !!apiKey.trim()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!qualysOk || !llmOk) return
    setBusy(true)
    setError('')
    try {
      let llm: LlmCredentials | null = null
      if (needLlm) {
        llm = { provider, apiKey: apiKey.trim(), ...(provider === 'bedrock' ? { region } : {}), ...(model.trim() ? { model: model.trim() } : {}) }
        await checkLlm(llmHeaders(llm))
      }
      if (needQualys) {
        await checkSession({ 'X-Qualys-Url': url, 'X-Qualys-Token': token.trim() })
      }
      if (llm) setLlm(llm, remember)
      if (needQualys) setCredentials({ url, token: token.trim() }, remember)
      onDone()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const field = 'w-full rounded-lg px-3 py-2 text-sm outline-none border focus:ring-2 focus:ring-[var(--brand)]'
  const fieldStyle = { background: 'var(--bg-base)', borderColor: 'var(--border)', color: 'var(--text-primary)' }
  const label = 'block text-xs font-semibold mb-1'
  const section = 'text-[11px] font-semibold uppercase tracking-widest mb-2'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto py-6" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}>
      <form onSubmit={submit} className="relative w-full max-w-md mx-4 rounded-2xl p-6 shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        {onCancel && (
          <button type="button" onClick={onCancel} className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-full hover:bg-[var(--bg-secondary-alpha)]" style={{ color: 'var(--text-muted)' }} aria-label="Close">
            <X size={16} />
          </button>
        )}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-full bg-[var(--brand)] flex items-center justify-center"><KeyRound size={18} className="text-white" /></div>
          <div>
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Sign in</h2>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {needQualys && 'You see only the data your Qualys account can access. '}
              {needLlm && 'Sheldon chat is billed to your own AI account.'}
            </p>
          </div>
        </div>

        {needQualys && (
          <div className="mb-5">
            <p className={section} style={{ color: 'var(--text-muted)' }}>Qualys</p>
            <label className={label} style={{ color: 'var(--text-secondary)' }}>Platform (API gateway URL)</label>
            <select value={preset} onChange={e => setPreset(e.target.value)} className={field} style={fieldStyle}>
              {GATEWAYS.map(g => <option key={g} value={g}>{g}</option>)}
              <option value="other">Other…</option>
            </select>
            {preset === 'other' && (
              <input value={customUrl} onChange={e => setCustomUrl(e.target.value)} placeholder="https://gateway.qgN.apps.qualys.com" className={`${field} mt-2`} style={fieldStyle} autoComplete="url" />
            )}
            <label className={`${label} mt-3`} style={{ color: 'var(--text-secondary)' }}>API token</label>
            <textarea value={token} onChange={e => setToken(e.target.value)} rows={3} placeholder="Paste your Qualys API token" className={`${field} font-mono text-xs resize-none`} style={fieldStyle} autoComplete="off" spellCheck={false} />
          </div>
        )}

        {needLlm && (
          <div className="mb-4">
            <p className={section} style={{ color: 'var(--text-muted)' }}>AI model (billed to you)</p>
            <div className="flex gap-2 mb-3" role="radiogroup" aria-label="AI provider">
              {([['anthropic', 'Anthropic API key'], ['bedrock', 'Amazon Bedrock API key']] as const).map(([v, text]) => (
                <button key={v} type="button" role="radio" aria-checked={provider === v} onClick={() => setProvider(v)}
                  className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold border ${provider === v ? 'bg-[var(--brand)] text-white border-[var(--brand)]' : ''}`}
                  style={provider === v ? undefined : fieldStyle}>
                  {text}
                </button>
              ))}
            </div>
            <label className={label} style={{ color: 'var(--text-secondary)' }}>{provider === 'anthropic' ? 'Anthropic API key' : 'Amazon Bedrock API key'}</label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder={provider === 'anthropic' ? 'sk-ant-…' : 'Bedrock API key'} className={`${field} font-mono text-xs`} style={fieldStyle} autoComplete="off" />
            {provider === 'bedrock' && (
              <>
                <label className={`${label} mt-3`} style={{ color: 'var(--text-secondary)' }}>AWS region of the key</label>
                <select value={region} onChange={e => setRegion(e.target.value)} className={field} style={fieldStyle}>
                  {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </>
            )}
            <label className={`${label} mt-3`} style={{ color: 'var(--text-secondary)' }}>Model ID (optional)</label>
            <input value={model} onChange={e => setModel(e.target.value)} placeholder={provider === 'anthropic' ? 'claude-haiku-5-5' : 'global.anthropic.claude-haiku-5-5'} className={`${field} font-mono text-xs`} style={fieldStyle} autoComplete="off" />
          </div>
        )}

        <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
          <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />
          Remember on this device (otherwise cleared when you close the tab)
        </label>

        {error && <p className="mt-3 text-xs text-red-500" role="alert">{error}</p>}

        <button type="submit" disabled={busy || !qualysOk || !llmOk} className="mt-5 w-full flex items-center justify-center gap-2 rounded-lg bg-[var(--brand)] hover:bg-[var(--brand-hover)] disabled:opacity-50 text-white text-sm font-semibold py-2.5">
          {busy && <Loader2 size={15} className="animate-spin" />}
          {busy ? 'Checking…' : 'Sign in'}
        </button>
        <p className="mt-3 text-[11px] leading-snug" style={{ color: 'var(--text-muted)' }}>
          Your keys are sent only to this app, which uses them for your own requests. They aren't stored on the server.
          {needLlm && ' Checking your AI key uses a few tokens on your account.'}
        </p>
      </form>
    </div>
  )
}
