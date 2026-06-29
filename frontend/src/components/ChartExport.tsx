import { useRef } from 'react'
import { Download } from 'lucide-react'

interface ChartExportProps {
  title?: string
  filename?: string
  children: React.ReactNode
}

export default function ChartExport({ title, filename = 'chart.svg', children }: ChartExportProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)

  const exportSVG = () => {
    const svg = wrapperRef.current?.querySelector('svg')
    if (!svg) return
    const serializer = new XMLSerializer()
    const source = serializer.serializeToString(svg)
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className="rounded-xl p-5 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-4">
        {title && <h3 className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>{title}</h3>}
        <button
          onClick={exportSVG}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border hover:border-blue-500 transition-colors ml-auto"
          style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
          title="Download SVG"
        >
          <Download size={14} /> SVG
        </button>
      </div>
      <div ref={wrapperRef}>{children}</div>
    </div>
  )
}
