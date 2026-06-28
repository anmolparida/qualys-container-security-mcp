import { useEffect, useState } from 'react'
import { fetchDashboard } from '../lib/api'
import StatCard from '../components/StatCard'
import { RefreshCw, CheckCircle, XCircle, Clock, Database, HeartPulse, AlertCircle } from 'lucide-react'

function StatusIcon({ status }: { status: string }) {
  const s = (status ?? '').toUpperCase()
  if (s === 'SUCCESS' || s === 'ACTIVE' || s === 'COMPLETED') return <CheckCircle size={16} className="text-green-400" />
  if (s === 'FAILED' || s === 'ERROR') return <XCircle size={16} className="text-red-400" />
  return <Clock size={16} className="text-yellow-400" />
}

export default function RegistryHealth() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchDashboard('registry/health'))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-400">Loading registry data...</div>
  if (error) return <div className="text-red-400 p-6">Error: {error}</div>

  const healthy = data.registries.filter((r: any) => ['SUCCESS', 'ACTIVE', 'COMPLETED'].includes((r.state ?? '').toUpperCase())).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Registry Health</h2>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard label="Total Registries" value={data.total} icon={Database} accent="from-blue-500 to-cyan-500" />
        <StatCard label="Healthy" value={healthy} color="text-green-400" icon={HeartPulse} accent="from-green-500 to-emerald-600" />
        <StatCard label="Unhealthy / Unknown" value={data.total - healthy} color="text-red-400" icon={AlertCircle} accent="from-red-500 to-red-600" />
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ color: 'var(--text-muted)', borderColor: 'var(--border)', background: 'var(--bg-secondary-alpha)' }}>
              <th className="text-left px-4 py-3">Registry</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Total Images</th>
              <th className="text-left px-4 py-3">Last Scanned</th>
            </tr>
          </thead>
          <tbody>
            {data.registries.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-slate-500 text-center">No registries found</td></tr>
            )}
            {data.registries.map((r: any, i: number) => (
              <tr key={i} className="border-b transition-colors hover:opacity-80" style={{ borderColor: 'var(--border)' }}>
                <td className="px-4 py-3 font-medium truncate max-w-[200px]" style={{ color: 'var(--text-primary)' }}>{r.name}</td>
                <td className="px-4 py-3 text-slate-400">{r.type ?? '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <StatusIcon status={r.state ?? ''} />
                    <span style={{ color: 'var(--text-secondary)' }}>{r.state ?? 'Unknown'}</span>
                  </div>
                </td>
                <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{r.total_images ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {r.last_scanned ? new Date(r.last_scanned).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
