const styles: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-700 border-red-500/40',
  HIGH: 'bg-orange-500/20 text-orange-700 border-orange-500/40',
  MEDIUM: 'bg-yellow-500/20 text-yellow-700 border-yellow-500/40',
  LOW: 'bg-blue-500/20 text-blue-700 border-blue-500/40',
  NONE: 'bg-slate-500/20 text-slate-600 border-slate-500/40',
}

export default function SeverityBadge({ severity, count }: { severity: string; count: number }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold border ${styles[severity] ?? styles.NONE}`}>
      {severity} <span className="opacity-90">{count}</span>
    </span>
  )
}
