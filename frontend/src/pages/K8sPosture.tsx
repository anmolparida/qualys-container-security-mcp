import { useEffect, useState } from 'react'
import { fetchDashboard } from '../lib/api'
import StatCard from '../components/StatCard'
import { RefreshCw, Server } from 'lucide-react'

export default function K8sPosture() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await fetchDashboard('k8s/posture'))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-400">Loading K8s data...</div>
  if (error) return <div className="text-red-400 p-6">Error: {error}</div>

  const posture = data.posture_summary ?? {}
  const passed = posture.passed ?? posture.PASS ?? 0
  const failed = posture.failed ?? posture.FAIL ?? 0
  const total = passed + failed

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">K8s Cluster Posture</h2>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Clusters" value={data.total_clusters} />
        <StatCard label="Posture Controls" value={total} />
        <StatCard label="Passed" value={passed} color="text-green-400" />
        <StatCard label="Failed" value={failed} color="text-red-400" />
      </div>

      {total > 0 && (
        <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>Posture Pass Rate</h3>
          <div className="flex items-center gap-3">
            <div className="flex-1 rounded-full h-4 overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${total > 0 ? Math.round((passed / total) * 100) : 0}%` }}
              />
            </div>
            <span className="text-green-400 font-bold text-sm w-12 text-right">
              {total > 0 ? Math.round((passed / total) * 100) : 0}%
            </span>
          </div>
        </div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary-alpha)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Clusters</h3>
        </div>
        {data.clusters.length === 0 && (
          <p className="px-4 py-6 text-slate-500 text-center text-sm">No clusters found</p>
        )}
        <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
          {data.clusters.map((c: any, i: number) => (
            <div key={i} className="px-4 py-3 flex items-center justify-between hover:opacity-80 transition-colors" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-3">
                <Server size={16} className="text-blue-400 flex-shrink-0" />
                <div>
                  <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{c.name ?? c.uid}</p>
                  <p className="text-xs text-slate-500">v{c.version} · {c.node_count} nodes</p>
                </div>
              </div>
              <span className={`text-xs font-semibold px-2 py-1 rounded ${
                (c.sensor_status ?? '').toUpperCase() === 'ACTIVE'
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-slate-600/40 text-slate-400'
              }`}>
                {c.sensor_status ?? 'Unknown'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
