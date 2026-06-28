const styles: Record<string, string> = {
  CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/30',
  HIGH: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  LOW: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  NONE: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
}

export default function SeverityBadge({ severity, count }: { severity: string; count: number }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold border ${styles[severity] ?? styles.NONE}`}>
      {severity} <span className="opacity-90">{count}</span>
    </span>
  )
}
