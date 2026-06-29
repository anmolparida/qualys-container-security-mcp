import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { fetchDashboard } from '../lib/api'
import StatCard from '../components/StatCard'
import SeverityBadge from '../components/SeverityBadge'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import ChartExport from '../components/ChartExport'
import { RefreshCw, Image, AlertTriangle, Flame, ShieldAlert } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function ImageVulnerabilities() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { dark } = useTheme()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchDashboard('images/vulnerabilities'))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <DashboardSkeleton statCount={4} />
  if (error) return <div className="text-red-400 p-6">Error: {error}</div>

  const { severity_totals, top_vulnerable_images, total_images } = data

  const SEV_COLORS: Record<string, string> = {
    Critical: '#ef4444',
    High: '#f97316',
    Medium: '#eab308',
    Low: '#3b82f6',
  }

  const barData = [
    { name: 'Critical', value: severity_totals.critical, fill: SEV_COLORS.Critical },
    { name: 'High', value: severity_totals.high, fill: SEV_COLORS.High },
    { name: 'Medium', value: severity_totals.medium, fill: SEV_COLORS.Medium },
    { name: 'Low', value: severity_totals.low, fill: SEV_COLORS.Low },
  ]

  const tooltipStyle = {
    background: dark ? '#16213e' : '#ffffff',
    border: `1px solid ${dark ? '#0f3460' : '#e2e8f0'}`,
    borderRadius: 8,
    color: dark ? '#e2e8f0' : '#0f172a',
  }

  const tickColor = dark ? '#94a3b8' : '#64748b'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Image Vulnerabilities</h2>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Images" value={total_images} icon={Image} accent="from-blue-500 to-cyan-500" />
        <StatCard label="Critical" value={severity_totals.critical} color="text-red-400" icon={AlertTriangle} accent="from-red-500 to-red-600" />
        <StatCard label="High" value={severity_totals.high} color="text-orange-400" icon={Flame} accent="from-orange-500 to-orange-600" />
        <StatCard label="Medium" value={severity_totals.medium} color="text-yellow-400" icon={ShieldAlert} accent="from-yellow-500 to-yellow-600" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ChartExport title="Severity Distribution" filename="image-severity.svg">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fill: tickColor, fontSize: 12 }} />
              <YAxis tick={{ fill: tickColor, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {barData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartExport>

        <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>Top Vulnerable Images</h3>
          {top_vulnerable_images.length === 0 ? (
            <EmptyState icon={Image} title="No vulnerable images" />
          ) : (
            <div className="space-y-3 overflow-y-auto max-h-56">
              {top_vulnerable_images.map((img: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-sm border-b pb-2" style={{ borderColor: 'var(--border)' }}>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium truncate" style={{ color: 'var(--text-primary)' }}>{img.name || img.sha?.slice(0, 12)}</p>
                    <p className="text-xs text-slate-500">{img.tag}</p>
                  </div>
                  <div className="flex gap-1 ml-2 flex-shrink-0">
                    {img.critical > 0 && <SeverityBadge severity="CRITICAL" count={img.critical} />}
                    {img.high > 0 && <SeverityBadge severity="HIGH" count={img.high} />}
                    {img.medium > 0 && <SeverityBadge severity="MEDIUM" count={img.medium} />}
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
