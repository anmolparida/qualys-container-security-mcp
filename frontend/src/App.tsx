import { useState } from 'react'
import { Container, ImageIcon, Database, Network, Zap, Shield, Sun, Moon, ExternalLink } from 'lucide-react'
import ContainerOverview from './pages/ContainerOverview'
import ImageVulnerabilities from './pages/ImageVulnerabilities'
import RegistryHealth from './pages/RegistryHealth'
import K8sPosture from './pages/K8sPosture'
import Chat from './pages/Chat'
import { useTheme } from './context/ThemeContext'

type Tab = 'containers' | 'images' | 'registry' | 'k8s' | 'chat'

const NAV = [
  { id: 'containers' as Tab, label: 'Containers', icon: Container },
  { id: 'images' as Tab, label: 'Image Vulns', icon: ImageIcon },
  { id: 'registry' as Tab, label: 'Registry Health', icon: Database },
  { id: 'k8s' as Tab, label: 'K8s Posture', icon: Network },
  { id: 'chat' as Tab, label: 'Agent Sheldon', icon: Zap },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const { dark, toggle } = useTheme()
  const active = NAV.find(n => n.id === tab)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      {/* Sidebar */}
      <aside className="w-60 flex flex-col flex-shrink-0" style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}>
        <div className="p-5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-red-500 flex items-center justify-center shadow-lg">
              <Shield size={20} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">Qualys CS</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Intelligence Platform</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-2 space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                tab === id
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
                  : 'text-slate-400 hover:text-white hover:bg-[var(--bg-secondary-alpha)]'
              }`}
            >
              <Icon size={17} />
              {label}
            </button>
          ))}
        </nav>

        <div className="px-3 pb-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
          <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Resources</p>
          {[
            { label: 'Sensor Helm Chart', href: 'https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc' },
            { label: 'CS API Docs', href: 'https://docs.qualys.com/en/cs/api/' },
            { label: 'CS User Guide', href: 'https://docs.qualys.com/en/cs/' },
            { label: 'QScanner Commands', href: 'https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm' },
          ].map(({ label, href }) => (
            <a
              key={href}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-[var(--bg-secondary-alpha)] transition-all"
            >
              <span>{label}</span>
              <ExternalLink size={12} className="flex-shrink-0 opacity-60" />
            </a>
          ))}
        </div>

        <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={toggle}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-[var(--bg-secondary-alpha)] transition-all"
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
            {dark ? 'Light mode' : 'Dark mode'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden" style={{ color: 'var(--text-primary)' }}>
        <header className="h-16 flex items-center justify-between px-6 border-b flex-shrink-0" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            {tab === 'chat' && (
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-md shadow-orange-900/20 flex-shrink-0">
                <Zap size={16} className="text-white" fill="white" />
              </div>
            )}
            <div>
              <h1 className="text-lg font-semibold leading-tight">{active?.label}</h1>
              <p className="text-xs leading-tight" style={{ color: 'var(--text-muted)' }}>
                {tab === 'chat' ? 'Qualys | Kubernetes & Container Security' : 'Qualys Container Security API'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
            <span className="w-2 h-2 rounded-full bg-green-500" />
            Live
          </div>
        </header>
        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'containers' && <ContainerOverview />}
          {tab === 'images' && <ImageVulnerabilities />}
          {tab === 'registry' && <RegistryHealth />}
          {tab === 'k8s' && <K8sPosture />}
          {tab === 'chat' && <Chat />}
        </div>
      </main>
    </div>
  )
}
