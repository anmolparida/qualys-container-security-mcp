import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, ShieldAlert, Flame, Crosshair, Zap, Loader2, MessageSquare, ExternalLink } from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { fetchDashboard } from '../lib/api'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import type { ThreatIntelCategory, ThreatIntelDetail, ThreatIntelOverview } from '../types/api'

const GROUPS: { id: ThreatIntelCategory['group']; title: string; hint: string; icon: typeof Flame; accent: string }[] = [
  { id: 'exploited', title: 'Exploited in the wild', hint: 'Fix these first', icon: Flame, accent: 'from-red-500 to-rose-600' },
  { id: 'exploitability', title: 'Easy to exploit', hint: 'Likely to be attacked next', icon: Crosshair, accent: 'from-orange-500 to-amber-500' },
  { id: 'impact', title: 'High impact', hint: 'Damage if exploited', icon: Zap, accent: 'from-violet-500 to-indigo-500' },
]

const SEV_LABEL: Record<number, string> = { 5: 'Critical', 4: 'High', 3: 'Medium', 2: 'Low', 1: 'Info' }
const SEV_STYLE: Record<number, string> = {
  5: 'bg-red-500/20 text-red-600 border-red-500/40',
  4: 'bg-orange-500/20 text-orange-600 border-orange-500/40',
  3: 'bg-yellow-500/20 text-yellow-700 border-yellow-500/40',
  2: 'bg-blue-500/20 text-blue-600 border-blue-500/40',
  1: 'bg-slate-500/20 text-slate-500 border-slate-500/40',
}

function fmt(c: ThreatIntelCategory) {
  if (c.count === null) return '—'
  return `${c.count.toLocaleString()}${c.capped ? '+' : ''}`
}

interface Props {
  /** Open Sheldon chat with a prepared question. */
  onAsk?: (question: string) => void
}

export default function ThreatIntel({ onAsk }: Props) {
  const { data, state, error, refresh } = useDashboard<ThreatIntelOverview>('threat-intel')
  const [selected, setSelected] = useState<string>('cisaKnownExploitedVulns')
  const [criticalOnly, setCriticalOnly] = useState(false)
  const [detail, setDetail] = useState<ThreatIntelDetail | null>(null)
  const [detailState, setDetailState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [detailError, setDetailError] = useState('')

  useEffect(() => {
    let cancelled = false
    setDetailState('loading')
    const path = `threat-intel/${selected}${criticalOnly ? '?severity_min=4' : ''}` as const
    fetchDashboard<ThreatIntelDetail>(path as any)
      .then(d => { if (!cancelled) { setDetail(d); setDetailState('idle') } })
      .catch(e => { if (!cancelled) { setDetailError(e.message); setDetailState('error') } })
    return () => { cancelled = true }
  }, [selected, criticalOnly])

  const byKey = useMemo(() => Object.fromEntries((data?.categories ?? []).map(c => [c.key, c])), [data])

  if (!data && state === 'loading') return <DashboardSkeleton statCount={4} />
  if (state === 'error') return <div className="text-red-400 p-6">Error: {error}</div>
  if (!data) return <DashboardSkeleton statCount={4} />

  const current = byKey[selected]
  const failed = data.categories.filter(c => c.error).length

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">Threat Intelligence</h2>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Vulnerabilities in your environment grouped by Qualys real-time threat indicators. Click a category to see the vulnerabilities.
          </p>
        </div>
        <button onClick={refresh} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors flex-shrink-0">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {failed > 0 && (
        <p className="text-xs text-amber-500">{failed} categor{failed === 1 ? 'y' : 'ies'} couldn't be loaded from Qualys.</p>
      )}

      {GROUPS.map(g => {
        const cats = data.categories.filter(c => c.group === g.id)
        return (
          <section key={g.id}>
            <div className="flex items-center gap-2 mb-3">
              <g.icon size={16} className="text-slate-400" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{g.title}</h3>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>· {g.hint}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
              {cats.map(c => {
                const active = c.key === selected
                const zero = c.count === 0
                return (
                  <button
                    key={c.key}
                    onClick={() => setSelected(c.key)}
                    title={`${c.description}\nthreatIntel.${c.key}:true`}
                    className={`relative overflow-hidden text-left rounded-xl p-4 border transition-all hover:-translate-y-0.5 ${active ? 'ring-2 ring-blue-500' : ''} ${zero ? 'opacity-60' : ''}`}
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
                  >
                    <div className={`absolute top-0 left-0 w-1 h-full bg-gradient-to-b ${g.accent}`} />
                    <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{c.label}</p>
                    <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{fmt(c)}</p>
                    <p className="text-[11px] mt-1 leading-snug" style={{ color: 'var(--text-muted)' }}>{c.description}</p>
                  </button>
                )
              })}
            </div>
          </section>
        )
      })}

      <section className="rounded-xl border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              {current?.label ?? selected} {detail && <span className="font-normal" style={{ color: 'var(--text-muted)' }}>· {detail.total.toLocaleString()}{detail.capped ? '+' : ''} vulnerabilities</span>}
            </h3>
            <code className="text-xs" style={{ color: 'var(--text-muted)' }}>{detail?.filter ?? `threatIntel.${selected}:true`}</code>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <input type="checkbox" checked={criticalOnly} onChange={e => setCriticalOnly(e.target.checked)} />
              High &amp; critical only
            </label>
            {onAsk && current && (
              <button
                onClick={() => onAsk(`Which images and containers are affected by ${current.label} vulnerabilities (threatIntel.${current.key}:true)? Prioritise what to fix first.`)}
                className="flex items-center gap-1.5 text-xs font-semibold rounded-lg px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white"
              >
                <MessageSquare size={13} /> Ask Sheldon
              </button>
            )}
          </div>
        </div>

        {detailState === 'loading' && (
          <div className="flex items-center gap-2 p-6 text-sm" style={{ color: 'var(--text-muted)' }}>
            <Loader2 size={16} className="animate-spin" /> Loading from Qualys…
          </div>
        )}
        {detailState === 'error' && <div className="p-6 text-sm text-red-400">Error: {detailError}</div>}
        {detailState === 'idle' && detail && detail.items.length === 0 && (
          <div className="p-6"><EmptyState icon={ShieldAlert} title="No vulnerabilities in this category" /></div>
        )}
        {detailState === 'idle' && detail && detail.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                  <th className="px-4 py-2">Severity</th>
                  <th className="px-4 py-2">QID</th>
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">CVEs</th>
                  <th className="px-4 py-2 text-right">Images</th>
                  <th className="px-4 py-2 text-right">Containers</th>
                </tr>
              </thead>
              <tbody>
                {detail.items.map((v, i) => (
                  <tr key={`${v.qid}-${i}`} className="border-t" style={{ borderColor: 'var(--border)' }}>
                    <td className="px-4 py-2">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-semibold border ${SEV_STYLE[v.severity] ?? SEV_STYLE[1]}`}>
                        {SEV_LABEL[v.severity] ?? v.severity}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{v.qid ?? '—'}</td>
                    <td className="px-4 py-2" style={{ color: 'var(--text-primary)' }}>{v.title || '—'}</td>
                    <td className="px-4 py-2 text-xs">
                      {v.cves.length === 0 ? '—' : v.cves.map(c => (
                        <a key={c} href={`https://nvd.nist.gov/vuln/detail/${c}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 mr-2 text-blue-500 hover:underline">
                          {c}<ExternalLink size={10} />
                        </a>
                      ))}
                    </td>
                    <td className="px-4 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{v.images ?? '—'}</td>
                    <td className="px-4 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>{v.containers ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-4 py-2 text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Showing the top {detail.items.length}. Counts refresh every {Math.round((data.cached_for_seconds ?? 300) / 60)} min.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
