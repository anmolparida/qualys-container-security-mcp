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

const DEFAULT_COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#6366f1']

export default function ChartRenderer({ config }: { config: ChartConfig }) {
  const colors = config.colors?.length ? config.colors : DEFAULT_COLORS

  return (
    <div className="my-4 p-4 rounded-lg border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
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
                outerRadius={80}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {config.data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          ) : config.type === 'bar' ? (
            <BarChart data={config.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip />
              <Bar dataKey="value" fill={colors[0]} />
            </BarChart>
          ) : (
            <LineChart data={config.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke={colors[0]} strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
