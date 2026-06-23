import { useState } from 'react'
import { Container, ImageIcon, Database, Network, MessageSquare, Shield, Sun, Moon } from 'lucide-react'
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
  { id: 'chat' as Tab, label: 'AI Assistant', icon: MessageSquare },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('containers')
  const { dark, toggle } = useTheme()

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 border-r flex flex-col flex-shrink-0" style={{ background: 'var(--sidebar-bg)', borderColor: 'var(--border)' }}>
        <div className="p-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <Shield size={22} className="text-red-500" />
            <div>
              <p className="text-sm font-bold text-white">Qualys CS</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Intelligence Platform</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                tab === id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
              style={tab !== id ? { '--hover-bg': 'var(--bg-hover)' } as React.CSSProperties : {}}
              onMouseEnter={e => tab !== id && ((e.currentTarget as HTMLElement).style.background = 'var(--bg-secondary-alpha)')}
              onMouseLeave={e => tab !== id && ((e.currentTarget as HTMLElement).style.background = '')}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t space-y-3" style={{ borderColor: 'var(--border)' }}>
          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white transition-all"
            style={{ background: 'var(--bg-secondary-alpha)' }}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun size={15} /> : <Moon size={15} />}
            {dark ? 'Light mode' : 'Dark mode'}
          </button>
          <p className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>qg1.apps.qualys.ca</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6" style={{ color: 'var(--text-primary)' }}>
        {tab === 'containers' && <ContainerOverview />}
        {tab === 'images' && <ImageVulnerabilities />}
        {tab === 'registry' && <RegistryHealth />}
        {tab === 'k8s' && <K8sPosture />}
        {tab === 'chat' && <Chat />}
      </main>
    </div>
  )
}
