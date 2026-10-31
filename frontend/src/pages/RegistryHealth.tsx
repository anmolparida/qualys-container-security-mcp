import { useDashboard } from '../hooks/useDashboard'
import StatCard from '../components/StatCard'
import DataTable from '../components/DataTable'
import DashboardSkeleton from '../components/DashboardSkeleton'
import EmptyState from '../components/EmptyState'
import { RefreshCw, CheckCircle, XCircle, Clock, Database, HeartPulse, AlertCircle } from 'lucide-react'
import type { RegistryHealth as RegistryHealthType } from '../types/api'

function StatusIcon({ status }: { status: string }) {
  const s = (status ?? '').toUpperCase()
  if (s === 'SUCCESS' || s === 'ACTIVE' || s === 'COMPLETED') return <CheckCircle size={16} className="text-green-600" />
  if (s === 'FAILED' || s === 'ERROR') return <XCircle size={16} className="text-red-600" />
  return <Clock size={16} className="text-yellow-600" />
}

export default function RegistryHealth() {
  const { data, state, error, refresh } = useDashboard<RegistryHealthType>('registry/health')

  if (!data && state === 'loading') return <DashboardSkeleton statCount={3} />
  if (state === 'error') return <div className="text-red-400 p-6">Error: {error}</div>
  if (!data) return <DashboardSkeleton statCount={3} />

  const healthy = data.registries.filter((r: any) => ['SUCCESS', 'ACTIVE', 'COMPLETED'].includes((r.state ?? '').toUpperCase())).length

  const columns = [
    { key: 'name', header: 'Registry', accessor: (r: any) => r.name },
    { key: 'type', header: 'Type', accessor: (r: any) => r.type ?? '—' },
    {
      key: 'state',
      header: 'Status',
      accessor: (r: any) => r.state ?? 'Unknown',
      render: (r: any) => (
        <div className="flex items-center gap-2">
          <StatusIcon status={r.state ?? ''} />
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{r.state ?? 'Unknown'}</span>
        </div>
      ),
    },
    { key: 'total_images', header: 'Total Images', accessor: (r: any) => r.total_images ?? '—' },
    {
      key: 'last_scanned',
      header: 'Last Scanned',
      accessor: (r: any) => r.last_scanned ? new Date(r.last_scanned).toLocaleString() : '—',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Registry Health</h2>
        <button onClick={refresh} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard label="Total Registries" value={data.total} icon={Database} accent="from-blue-500 to-cyan-500" />
        <StatCard label="Healthy" value={healthy} color="text-green-400" icon={HeartPulse} accent="from-green-500 to-emerald-600" />
        <StatCard label="Unhealthy / Unknown" value={data.total - healthy} color="text-red-400" icon={AlertCircle} accent="from-red-500 to-red-600" />
      </div>

      {data.registries.length === 0 ? (
        <EmptyState icon={Database} title="No registries found" />
      ) : (
        <DataTable
          title="Registries"
          columns={columns}
          data={data.registries}
          filename="registries.csv"
          searchPlaceholder="Search registries..."
        />
      )}
    </div>
  )
}
