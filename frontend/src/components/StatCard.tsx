import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  color?: string
  icon?: LucideIcon
  accent?: string
}

export default function StatCard({ label, value, sub, color, icon: Icon, accent = 'from-blue-500 to-blue-600' }: StatCardProps) {
  return (
    <div className="relative overflow-hidden rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className={`absolute top-0 left-0 w-1 h-full bg-gradient-to-b ${accent}`} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm mb-1" style={{ color: 'var(--text-muted)' }}>{label}</p>
          <p className={`text-3xl font-bold ${color ?? ''}`} style={!color ? { color: 'var(--text-primary)' } : {}}>{value ?? '—'}</p>
          {sub && <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{sub}</p>}
        </div>
        {Icon && (
          <div className={`p-2 rounded-lg bg-gradient-to-br ${accent} bg-opacity-10`} style={{ background: 'var(--bg-secondary-alpha)' }}>
            <Icon size={20} className={color} />
          </div>
        )}
      </div>
    </div>
  )
}
