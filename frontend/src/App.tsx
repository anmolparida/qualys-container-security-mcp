import { useState } from 'react'
import { Container, ImageIcon, Database, Network, Zap, Sun, Moon, ExternalLink, Info, X } from 'lucide-react'
import ContainerOverview from './pages/ContainerOverview'
import ImageVulnerabilities from './pages/ImageVulnerabilities'
import RegistryHealth from './pages/RegistryHealth'
import K8sPosture from './pages/K8sPosture'
import Chat from './pages/Chat'
import { useTheme } from './context/ThemeContext'

type Tab = 'containers' | 'images' | 'registry' | 'k8s' | 'chat'

const NAV = [
  { id: 'containers' as Tab, label: 'Containers', icon: Container },
  { id: 'images' as Tab, label: 'Images', icon: ImageIcon },
  { id: 'registry' as Tab, label: 'Registry', icon: Database },
  { id: 'k8s' as Tab, label: 'K8s Posture', icon: Network },
  { id: 'chat' as Tab, label: 'Sheldon', icon: Zap },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const { dark, toggle } = useTheme()
  const active = NAV.find(n => n.id === tab)
  const [showInfo, setShowInfo] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      {/* Sidebar */}
      <aside className="w-60 flex flex-col flex-shrink-0" style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}>
        <div className="p-5">
          <button onClick={() => setTab('chat')} className="flex items-center gap-3 w-full text-left hover:opacity-80 transition-opacity">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-lg shadow-orange-900/30">
              <Zap size={18} className="text-white" fill="white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">Qualys KCS</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Intelligence Platform</p>
            </div>
          </button>
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
            { label: 'Release Notes', href: 'https://www.qualys.com/documentation/release-notes' },
            { label: 'CS Search Tokens', href: 'https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm' },
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
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-md shadow-orange-900/20 flex-shrink-0">
                <Zap size={15} className="text-white" fill="white" />
              </div>
            )}
            <div>
              <h1 className="text-lg font-bold leading-tight">{active?.label}</h1>
              <p className="text-xs font-bold leading-tight" style={{ color: 'var(--text-muted)' }}>
                {tab === 'chat' ? 'AI Assistant | Kubernetes & Container Security' : 'Qualys Container Security API'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              <span className="w-2 h-2 rounded-full bg-green-500" />
              Live
            </div>
            <button
              onClick={() => setShowInfo(true)}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-[var(--bg-secondary-alpha)] transition-all"
              style={{ color: 'var(--text-muted)' }}
              title="About Sheldon"
            >
              <Info size={16} />
            </button>
          </div>

          {showInfo && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={() => setShowInfo(false)}>
              <div className="relative w-full max-w-md mx-4 rounded-2xl p-6 shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={e => e.stopPropagation()}>
                <button onClick={() => setShowInfo(false)} className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-full hover:bg-[var(--bg-secondary-alpha)] transition-all" style={{ color: 'var(--text-muted)' }}>
                  <X size={16} />
                </button>
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-lg shadow-orange-900/30">
                    <Zap size={18} className="text-white" fill="white" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Sheldon</h2>
                    <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Intelligence Platform</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Kubernetes &amp; Container Security</p>
                  </div>
                </div>
                <div className="space-y-3 text-sm">
                  {[
                    { label: 'LLM', value: 'Claude 3 Haiku via Amazon Bedrock' },
                    { label: 'Protocol', value: 'Model Context Protocol (MCP)' },
                    { label: 'Backend', value: 'FastAPI + async Python' },
                    { label: 'Frontend', value: 'React + Tailwind CSS' },
                    { label: 'Data source', value: 'Qualys Container Security API' },
                    { label: 'Tool registry', value: 'Shared MCP tool definitions (30+ tools)' },
                    { label: 'Concurrency', value: 'asyncio.gather — parallel tool calls' },
                    { label: 'Data privacy', value: 'All data stays in your AWS VPC' },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between gap-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                      <span className="font-medium flex-shrink-0" style={{ color: 'var(--text-muted)' }}>{label}</span>
                      <span className="text-right" style={{ color: 'var(--text-secondary)' }}>{value}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-3 border-t text-sm text-center" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                  <p>Developed by</p>
                  <p className="font-bold mt-0.5" style={{ color: 'var(--text-primary)' }}>Anmol Parida</p>
                  <p className="mt-0.5">Lead Subject Matter Expert</p>
                  <p>Container Security &amp; TotalAI</p>
                </div>
              </div>
            </div>
          )}
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
