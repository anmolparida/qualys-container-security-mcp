const colors: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  HIGH: 'bg-orange-500 text-white',
  MEDIUM: 'bg-yellow-500 text-black',
  LOW: 'bg-blue-500 text-white',
  NONE: 'bg-slate-600 text-white',
}

export default function SeverityBadge({ severity, count }: { severity: string; count: number }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${colors[severity] ?? 'bg-slate-600 text-white'}`}>
      {severity} {count}
    </span>
  )
}
