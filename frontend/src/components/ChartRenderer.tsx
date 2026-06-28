import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LineChart,
  Line,
  ResponsiveContainer,
} from 'recharts'

interface ChartDataPoint {
  name: string
  value: number
}

interface ChartConfig {
  type: 'pie' | 'bar' | 'line'
  title: string
  data: ChartDataPoint[]
  colors?: string[]
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  NONE: '#64748b',
}

const DISTINCT_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f43f5e', '#84cc16', '#fbbf24',
]

function getColor(name: string, index: number, palette: string[]) {
  const upper = name.toUpperCase()
  if (SEVERITY_COLORS[upper]) return SEVERITY_COLORS[upper]
  return palette[index % palette.length]
}

export default function ChartRenderer({ config }: { config: ChartConfig }) {
  const palette = config.colors?.length ? config.colors : DISTINCT_COLORS

  return (
    <div className="my-4 p-4 rounded-xl border shadow-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{config.title}</h4>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {config.type === 'pie' ? (
            <PieChart>
              <Pie
                data={config.data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={85}
                innerRadius={40}
                paddingAngle={2}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {config.data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getColor(entry.name, index, palette)} stroke="var(--bg-card)" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip />
              <Legend verticalAlign="bottom" height={36} />
            </PieChart>
          ) : config.type === 'bar' ? (
            <BarChart data={config.data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: 'var(--bg-secondary-alpha)' }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {config.data.map((entry, index) => (
                  <Cell key={`bar-${index}`} fill={getColor(entry.name, index, palette)} />
                ))}
              </Bar>
            </BarChart>
          ) : (
            <LineChart data={config.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke={palette[0]} strokeWidth={3} dot={{ r: 5, fill: palette[0], strokeWidth: 2, stroke: 'var(--bg-card)' }} activeDot={{ r: 7 }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
