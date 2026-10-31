import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { useDashboard } from '../hooks/useDashboard'
import StatCard from '../components/StatCard'
import SeverityBadge from '../components/SeverityBadge'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import ChartExport from '../components/ChartExport'
import { RefreshCw, Box, Play, Square, AlertTriangle, Container } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import type { ContainerOverview as ContainerOverviewType } from '../types/api'

const SEV_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  NONE: '#64748b',
}

const SEV_TEXT_COLORS: Record<string, string> = {
  CRITICAL: '#b91c1c',
  HIGH: '#c2410c',
  MEDIUM: '#a16207',
  LOW: '#1d4ed8',
  NONE: '#475569',
}

export default function ContainerOverview() {
  const { data, state, error, refresh } = useDashboard<ContainerOverviewType>('containers/overview')
  const { dark } = useTheme()

  if (!data && state === 'loading') return <DashboardSkeleton statCount={4} />
  if (state === 'error') return <div className="text-red-400 p-6">Error: {error}</div>
  if (!data) return <DashboardSkeleton statCount={4} />

  const pieData = Object.entries(data.severity_breakdown)
    .filter(([, v]) => (v as number) > 0)
    .map(([k, v]) => ({ name: k, value: v as number }))

  const tooltipStyle = {
    background: dark ? '#16213e' : '#ffffff',
    border: `1px solid ${dark ? '#0f3460' : '#e2e8f0'}`,
    borderRadius: 8,
    color: dark ? '#e2e8f0' : '#0f172a',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Container Overview</h2>
        <button onClick={refresh} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Containers" value={data.total} icon={Box} accent="from-blue-500 to-cyan-500" />
        <StatCard label="Running" value={data.running} color="text-green-400" icon={Play} accent="from-green-500 to-emerald-600" />
        <StatCard label="Stopped" value={data.stopped} color="text-slate-400" icon={Square} accent="from-slate-500 to-slate-600" />
        <StatCard label="Critical Vulns" value={data.severity_breakdown.CRITICAL} color="text-red-400" icon={AlertTriangle} accent="from-red-500 to-red-600" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ChartExport title="Vulnerability Severity Breakdown" filename="container-severity.svg">
          {pieData.length > 0 ? (
            <div className="flex items-center gap-6">
              <div className="relative flex-shrink-0" style={{ width: 180, height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%" cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={3}
                      strokeWidth={0}
                    >
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={SEV_COLORS[entry.name] ?? '#64748b'} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value: number, name: string) => [value.toLocaleString(), name]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-2xl font-bold">{pieData.reduce((s, d) => s + d.value, 0).toLocaleString()}</span>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>total vulns</span>
                </div>
              </div>
              <div className="flex flex-col gap-3 flex-1 min-w-0">
                {(() => {
                  const total = Math.max(pieData.reduce((s, d) => s + d.value, 0), 1)
                  return pieData.map((entry) => {
                    const pct = Math.round((entry.value / total) * 100)
                    return (
                      <div key={entry.name}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: SEV_COLORS[entry.name] ?? '#64748b' }} />
                            <span className="text-xs font-bold" style={{ color: SEV_TEXT_COLORS[entry.name] ?? '#475569' }}>{entry.name}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{entry.value.toLocaleString()}</span>
                            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{pct}%</span>
                          </div>
                        </div>
                        <div className="w-full rounded-full h-1.5" style={{ background: 'var(--border)' }}>
                          <div className="h-1.5 rounded-full transition-all duration-500" style={{
                            width: `${pct}%`,
                            background: SEV_COLORS[entry.name] ?? '#64748b',
                            minWidth: entry.value > 0 ? 4 : 0,
                          }} />
                        </div>
                      </div>
                    )
                  })
                })()}
              </div>
            </div>
          ) : (
            <EmptyState icon={Container} title="No container vulnerability data" />
          )}
        </ChartExport>

        <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-bold mb-4" style={{ color: 'var(--text-primary)' }}>Top Risky Containers</h3>
          {data.top_risky_containers.length === 0 ? (
            <EmptyState icon={Container} title="No risky containers" />
          ) : (
            <div className="space-y-3 overflow-y-auto max-h-56">
              {data.top_risky_containers.map((c: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-sm border-b pb-2" style={{ borderColor: 'var(--border)' }}>
                  <div>
                    <p className="font-bold truncate max-w-[180px]" style={{ color: 'var(--text-primary)' }}>{c.name}</p>
                    <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{c.state}</p>
                  </div>
                  <div className="flex gap-1">
                    {c.critical > 0 && <SeverityBadge severity="CRITICAL" count={c.critical} />}
                    {c.high > 0 && <SeverityBadge severity="HIGH" count={c.high} />}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
