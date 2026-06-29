import { useEffect, useState } from 'react'
import { fetchDashboard } from '../lib/api'
import StatCard from '../components/StatCard'
import DataTable from '../components/DataTable'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import { RefreshCw, Server, CheckCircle, XCircle, ListChecks, Network } from 'lucide-react'

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

  if (loading) return <DashboardSkeleton statCount={4} />
  if (error) return <div className="text-red-400 p-6">Error: {error}</div>

  const posture = data.posture_summary ?? {}
  const passed = posture.passed ?? posture.PASS ?? 0
  const failed = posture.failed ?? posture.FAIL ?? 0
  const total = passed + failed

  const clusterColumns = [
    {
      key: 'name',
      header: 'Cluster',
      accessor: (c: any) => c.name ?? c.uid,
      render: (c: any) => (
        <div className="flex items-center gap-3">
          <Server size={16} className="text-blue-400 flex-shrink-0" />
          <div>
            <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{c.name ?? c.uid}</p>
            <p className="text-xs text-slate-500">v{c.version} · {c.node_count} nodes</p>
          </div>
        </div>
      ),
    },
    {
      key: 'sensor_status',
      header: 'Sensor Status',
      accessor: (c: any) => c.sensor_status ?? 'Unknown',
      render: (c: any) => (
        <span className={`text-xs font-semibold px-2 py-1 rounded ${
          (c.sensor_status ?? '').toUpperCase() === 'ACTIVE'
            ? 'bg-green-500/20 text-green-400'
            : 'bg-slate-600/40 text-slate-400'
        }`}>
          {c.sensor_status ?? 'Unknown'}
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">K8s Cluster Posture</h2>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-blue-400 transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Clusters" value={data.total_clusters} icon={Network} accent="from-blue-500 to-cyan-500" />
        <StatCard label="Posture Controls" value={total} icon={ListChecks} accent="from-purple-500 to-purple-600" />
        <StatCard label="Passed" value={passed} color="text-green-400" icon={CheckCircle} accent="from-green-500 to-emerald-600" />
        <StatCard label="Failed" value={failed} color="text-red-400" icon={XCircle} accent="from-red-500 to-red-600" />
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

      {data.clusters.length === 0 ? (
        <EmptyState icon={Server} title="No clusters found" />
      ) : (
        <DataTable
          title="Clusters"
          columns={clusterColumns}
          data={data.clusters}
          filename="clusters.csv"
          searchPlaceholder="Search clusters..."
        />
      )}
    </div>
  )
}
