import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, ShieldAlert, Flame, Crosshair, Zap, Loader2, MessageSquare, ExternalLink, AlertTriangle } from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { fetchDashboard } from '../lib/api'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import type { ThreatIntelCategory, ThreatIntelDetail, ThreatIntelOverview } from '../types/api'

const GROUPS: { id: ThreatIntelCategory['group']; title: string; hint: string; icon: typeof Flame; bar: string }[] = [
  { id: 'exploited', title: 'Exploited in the wild', hint: 'Fix first', icon: Flame, bar: '#e5484d' },
  { id: 'exploitability', title: 'Easy to exploit', hint: 'Likely next', icon: Crosshair, bar: '#f08c00' },
  { id: 'impact', title: 'High impact', hint: 'Damage if exploited', icon: Zap, bar: '#6e56cf' },
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
  const max = Math.max(1, ...data.categories.map(c => c.count ?? 0))

  return (
    <div className="flex flex-col gap-4 h-full min-h-0">
      {/* Title row */}
      <div className="flex items-center justify-between gap-4 flex-shrink-0">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Vulnerabilities by Qualys real-time threat indicator. Pick a category to see its vulnerabilities.

        </p>
        <button onClick={refresh} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors flex-shrink-0">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4 flex-1 min-h-0">
        {/* Left: compact category list */}
        <nav aria-label="Threat categories" className="rounded-lg border overflow-y-auto p-2 space-y-2"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', boxShadow: 'var(--card-shadow)' }}>
          {failed > 0 && (
            <div className="flex items-center justify-between gap-2 rounded-md px-3 py-1.5 text-xs"
              style={{ background: 'rgba(245, 158, 11, 0.08)', color: 'var(--text-secondary)' }}>
              <span className="flex items-center gap-1.5"><AlertTriangle size={12} className="text-amber-500" />
                {failed} {failed === 1 ? 'count' : 'counts'} didn't load
              </span>
              <button onClick={refresh} disabled={state === 'loading'} className="font-semibold text-[var(--brand)] hover:underline disabled:opacity-50">
                {state === 'loading' ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          )}
          {GROUPS.map(g => (
            <div key={g.id} className="rounded-md border overflow-hidden" style={{ borderColor: `${g.bar}66`, borderLeftWidth: 3, borderLeftColor: g.bar }}>
              <div className="flex items-center gap-1.5 px-3 py-1.5" style={{ background: `${g.bar}12` }}>
                <g.icon size={12} style={{ color: g.bar }} />
                <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>{g.title}</span>
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>· {g.hint}</span>
              </div>
              {data.categories.filter(c => c.group === g.id).map(c => {
                const active = c.key === selected
                const pct = c.count ? Math.max(2, (c.count / max) * 100) : 0
                return (
                  <button key={c.key} onClick={() => setSelected(c.key)}
                    title={c.error ? `Couldn't load from Qualys (${c.error}). Use Retry above.` : `${c.description}\nthreatIntel.${c.key}:true`}
                    aria-current={active ? 'true' : undefined}
                    className={`w-full text-left px-3 py-1.5 transition-colors ${active ? "" : "hover:bg-[var(--bg-hover)]"} ${c.count === 0 ? 'opacity-50' : ''}`}
                    style={active ? { background: 'var(--brand-soft)', boxShadow: 'inset 0 0 0 1px var(--brand)' } : undefined}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[13px] truncate" style={{ color: active ? 'var(--brand)' : 'var(--text-primary)', fontWeight: active ? 600 : 500 }}>{c.label}</span>
                      {c.error
                        ? <span className="flex items-center gap-1 text-[13px] tabular-nums" style={{ color: 'var(--text-muted)' }}>
                            <AlertTriangle size={11} className="text-amber-500" />—
                          </span>
                        : <span className="text-[13px] font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>{fmt(c)}</span>}
                    </div>
                    <div className="mt-1 h-[4.5px] rounded-full" style={{ background: "var(--bg-secondary)" }}>
                      <div className="h-[4.5px] rounded-full" style={{ width: `${pct}%`, background: g.bar }} />
                    </div>
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Right: vulnerabilities in the selected category */}
        <section className="rounded-lg border flex flex-col min-h-0"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', boxShadow: 'var(--card-shadow)' }}>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b flex-shrink-0" style={{ borderColor: 'var(--border)' }}>
            <div className="min-w-0">
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                {current?.label ?? selected}
                {detail && <span className="font-normal" style={{ color: 'var(--text-muted)' }}> · {detail.total.toLocaleString()}{detail.capped ? '+' : ''} vulnerabilities</span>}
              </h3>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                {current?.description} · <code>{detail?.filter ?? `threatIntel.${selected}:true`}</code>
              </p>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                <input type="checkbox" checked={criticalOnly} onChange={e => setCriticalOnly(e.target.checked)} />
                High &amp; critical only
              </label>
              {onAsk && current && (
                <button
                  onClick={() => onAsk(`Which images and containers are affected by ${current.label} vulnerabilities (threatIntel.${current.key}:true)? Prioritise what to fix first.`)}
                  className="flex items-center gap-1.5 text-xs font-semibold rounded-md px-3 py-1.5 bg-[var(--brand)] hover:bg-[var(--brand-hover)] text-white"
                >
                  <MessageSquare size={13} /> Ask Sheldon
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-auto min-h-0">
            {detailState === 'loading' && (
              <div className="flex items-center gap-2 p-6 text-sm" style={{ color: 'var(--text-muted)' }}>
                <Loader2 size={16} className="animate-spin" /> Loading from Qualys…
              </div>
            )}
            {detailState === 'error' && <div className="p-6 text-sm text-red-500">Error: {detailError}</div>}
            {detailState === 'idle' && detail && detail.items.length === 0 && (
              <div className="p-6"><EmptyState icon={ShieldAlert} title="No vulnerabilities in this category" /></div>
            )}
            {detailState === 'idle' && detail && detail.items.length > 0 && (
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10" style={{ background: 'var(--bg-card)' }}>
                  <tr className="text-left text-[11px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
                    <th className="px-4 py-2 font-semibold">Severity</th>
                    <th className="px-4 py-2 font-semibold">QID</th>
                    <th className="px-4 py-2 font-semibold">Title</th>
                    <th className="px-4 py-2 font-semibold">CVEs</th>
                    <th className="px-4 py-2 font-semibold text-right">Images</th>
                    <th className="px-4 py-2 font-semibold text-right">Containers</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((v, i) => (
                    <tr key={`${v.qid}-${i}`} className="border-t hover:bg-[var(--bg-hover)]" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-2">
                        <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${SEV_STYLE[v.severity] ?? SEV_STYLE[1]}`}>
                          {SEV_LABEL[v.severity] ?? v.severity}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{v.qid ?? '—'}</td>
                      <td className="px-4 py-2" style={{ color: 'var(--text-primary)' }}>{v.title || '—'}</td>
                      <td className="px-4 py-2 text-xs whitespace-nowrap">
                        {v.cves.length === 0 ? '—' : v.cves.slice(0, 2).map(c => (
                          <a key={c} href={`https://nvd.nist.gov/vuln/detail/${c}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 mr-2 text-[var(--brand)] hover:underline">
                            {c}<ExternalLink size={10} />
                          </a>
                        ))}
                        {v.cves.length > 2 && <span style={{ color: 'var(--text-muted)' }}>+{v.cves.length - 2}</span>}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums" style={{ color: 'var(--text-secondary)' }}>{v.images ?? '—'}</td>
                      <td className="px-4 py-2 text-right tabular-nums" style={{ color: 'var(--text-secondary)' }}>{v.containers ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {detail && detail.items.length > 0 && (
            <p className="px-4 py-2 border-t text-[11px] flex-shrink-0" style={{ color: 'var(--text-muted)', borderColor: 'var(--border)' }}>
              Top {detail.items.length} by severity · counts refresh every {Math.round((data.cached_for_seconds ?? 300) / 60)} min
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
