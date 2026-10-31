import { useState, useMemo } from 'react'
import { Download, Search, ChevronUp, ChevronDown } from 'lucide-react'

export interface Column<T> {
  key: string
  header: string
  render?: (row: T) => React.ReactNode
  accessor?: (row: T) => string | number
  sortable?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  title?: string
  filename?: string
  searchPlaceholder?: string
}

export default function DataTable<T extends Record<string, any>>({
  columns,
  data,
  title,
  filename = 'export.csv',
  searchPlaceholder = 'Search...',
}: DataTableProps<T>) {
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return data.filter(row =>
      columns.some(col => {
        const value = col.accessor ? col.accessor(row) : row[col.key]
        return String(value ?? '').toLowerCase().includes(q)
      })
    )
  }, [data, query, columns])

  const sorted = useMemo(() => {
    if (!sortKey) return filtered
    const col = columns.find(c => c.key === sortKey)
    if (!col || col.sortable === false) return filtered

    return [...filtered].sort((a, b) => {
      const aVal = col.accessor ? col.accessor(a) : a[col.key]
      const bVal = col.accessor ? col.accessor(b) : b[col.key]
      if (aVal == null) return sortDir === 'asc' ? -1 : 1
      if (bVal == null) return sortDir === 'asc' ? 1 : -1
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal
      }
      return sortDir === 'asc'
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal))
    })
  }, [filtered, sortKey, sortDir, columns])

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const exportCSV = () => {
    const headers = columns.map(c => c.header).join(',')
    const rows = sorted.map(row =>
      columns
        .map(col => {
          const value = col.accessor ? col.accessor(row) : row[col.key]
          const text = String(value ?? '').replace(/"/g, '""')
          return `"${text}"`
        })
        .join(',')
    )
    const csv = [headers, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      {(title || data.length > 0) && (
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary-alpha)' }}>
          {title && <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{title}</h3>}
          <div className="flex items-center gap-2 ml-auto">
            <div className="relative">
              <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="pl-7 pr-3 py-1.5 rounded-lg text-xs border focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
              />
            </div>
            <button
              onClick={exportCSV}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border hover:border-[var(--brand)] transition-colors"
              style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
              title="Download CSV"
            >
              <Download size={14} /> CSV
            </button>
          </div>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary-alpha)' }}>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                  className={`text-left px-4 py-3 font-semibold ${col.sortable !== false ? 'cursor-pointer hover:opacity-80' : ''}`}
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <div className="flex items-center gap-1">
                    {col.header}
                    {col.sortable !== false && sortKey === col.key && (
                      sortDir === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-6 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                  No matching records
                </td>
              </tr>
            )}
            {sorted.map((row, i) => (
              <tr key={i} className="border-b transition-colors hover:opacity-80" style={{ borderColor: 'var(--border)' }}>
                {columns.map(col => (
                  <td key={col.key} className="px-4 py-3">
                    {col.render ? col.render(row) : <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{String(row[col.key] ?? '—')}</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
