import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { fetchDashboard } from '../lib/api'
import StatCard from '../components/StatCard'
import SeverityBadge from '../components/SeverityBadge'
import { RefreshCw, Box, Play, Square, AlertTriangle } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

const SEV_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  NONE: '#64748b',
}

export default function ContainerOverview() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { dark } = useTheme()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchDashboard('containers/overview'))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-400">Loading containers...</div>
  if (error) return <div className="text-red-400 p-6">Error: {error}</div>

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
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors">
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
        <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>Vulnerability Severity Breakdown</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={SEV_COLORS[entry.name] ?? '#64748b'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-500 text-sm">No vulnerability data</p>
          )}
        </div>

        <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>Top Risky Containers</h3>
          <div className="space-y-3 overflow-y-auto max-h-56">
            {data.top_risky_containers.length === 0 && <p className="text-slate-500 text-sm">No data</p>}
            {data.top_risky_containers.map((c: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-sm border-b pb-2" style={{ borderColor: 'var(--border)' }}>
                <div>
                  <p className="font-medium truncate max-w-[180px]" style={{ color: 'var(--text-primary)' }}>{c.name}</p>
                  <p className="text-xs text-slate-500">{c.state}</p>
                </div>
                <div className="flex gap-1">
                  {c.critical > 0 && <SeverityBadge severity="CRITICAL" count={c.critical} />}
                  {c.high > 0 && <SeverityBadge severity="HIGH" count={c.high} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
