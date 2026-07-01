import { useRef, useEffect, Component } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamChat } from '../lib/api'
import { useChatStore, type Message } from '../store/chatStore'
import { Send, User, AlertTriangle, Zap } from 'lucide-react'
import ChartRenderer from '../components/ChartRenderer'

// Error boundary that falls back to plain text if react-markdown crashes.
// This prevents the whole chat page from going blank/black on malformed output.
class MarkdownErrorBoundary extends Component<{ children: React.ReactNode; fallback: React.ReactNode }> {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  render() {
    if (this.state.hasError) return this.props.fallback
    return this.props.children
  }
}

const markdownComponents: any = {
  table: ({ children }: any) => (
    <div className="overflow-x-auto my-2">
      <table className="w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => (
    <thead style={{ background: 'var(--bg-secondary-alpha)' }}>{children}</thead>
  ),
  th: ({ children }: any) => (
    <th className="text-left px-3 py-2 font-semibold border-b" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>{children}</th>
  ),
  td: ({ children }: any) => (
    <td className="px-3 py-1.5 border-b" style={{ borderColor: 'var(--border)' }}>{children}</td>
  ),
  tr: ({ children }: any) => (
    <tr className="hover:opacity-80 transition-opacity">{children}</tr>
  ),
  h1: ({ children }: any) => <h1 className="text-lg font-bold text-blue-400 mb-2 mt-3">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-base font-bold text-blue-400 mb-2 mt-3">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-sm font-bold text-blue-400 mb-1 mt-2">{children}</h3>,
  strong: ({ children }: any) => <strong className="font-semibold text-blue-400">{children}</strong>,
  a: ({ href, children }: any) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline hover:text-blue-400 transition-colors">
      {children}
    </a>
  ),
  p: ({ children }: any) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }: any) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
  li: ({ children }: any) => <li className="leading-relaxed pl-1">{children}</li>,
  code: ({ children, className }: any) => {
    const isBlock = className?.startsWith('language-')
    if (isBlock) {
      const lang = className?.replace('language-', '') ?? ''
      return (
        <div className="my-2 rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
          {lang && (
            <div className="px-3 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider" style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)' }}>
              {lang}
            </div>
          )}
          <pre className="overflow-x-auto p-3 text-xs font-mono leading-relaxed" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
            <code>{children}</code>
          </pre>
        </div>
      )
    }
    return <code className="px-1 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>{children}</code>
  },
}

function SafeMarkdown({ content }: { content: string }) {
  return (
    <MarkdownErrorBoundary fallback={<pre className="whitespace-pre-wrap font-sans text-sm">{content}</pre>}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </MarkdownErrorBoundary>
  )
}

const CHART_BLOCK_RE = /```chart\n?([\s\S]*?)```/g

function renderAssistantContent(content: string) {
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match

  while ((match = CHART_BLOCK_RE.exec(content)) !== null) {
    const [fullMatch, jsonText] = match
    if (match.index > lastIndex) {
      parts.push(<SafeMarkdown key={`md-${lastIndex}`} content={content.slice(lastIndex, match.index)} />)
    }
    try {
      const config = JSON.parse(jsonText.trim())
      parts.push(<ChartRenderer key={`chart-${match.index}`} config={config} />)
    } catch (e) {
      parts.push(<pre key={`chart-err-${match.index}`} className="whitespace-pre-wrap text-xs text-red-400">{jsonText}</pre>)
    }
    lastIndex = match.index + fullMatch.length
  }

  if (lastIndex < content.length) {
    parts.push(<SafeMarkdown key={`md-end`} content={content.slice(lastIndex)} />)
  }

  return parts.length ? parts : <SafeMarkdown content={content} />
}

const SUGGESTIONS = [
  'Show all critical vulnerabilities across containers',
  'Which images have the most high severity CVEs?',
  'List running containers with vulnerability counts',
  'What is the current K8s posture score?',
  'Are there any secrets detected in my images?',
  'Show registry scan status',
  'Show a pie chart of vulnerability severity',
  'Chart image vulnerabilities by severity',
]

const QUALYS_FACTS = [
  'Qualys CS can detect secrets and sensitive data accidentally baked into container images.',
  'The unified Helm chart qualys-tc deploys all Qualys sensors — CS, PC, and VM — in a single release.',
  'Qualys assigns a Risk Score (0–1000) to each container based on vulnerability severity and exploitability.',
  'Static image scanning runs without ever executing the container, making it safe for CI pipelines.',
  'Qualys CS maps findings to the MITRE ATT&CK framework to help prioritize remediation.',
  'The QDS (Qualys Detection Score) factors in CVSS, exploit availability, and threat intelligence for more accurate prioritization than CVSS alone.',
  'Qualys CS supports air-gapped environments by allowing the sensor to operate without direct internet access.',
  'Container Security sensors stream real-time telemetry so new vulnerabilities are reflected within minutes of a scan.',
  'Qualys CS can enforce policy gates in GitHub Actions and Jenkins to block vulnerable images from being pushed.',
  'The platform tracks vulnerability drift — showing new CVEs introduced between two image builds.',
  'OpenShift deployments require isOpenShift=true in the Helm chart values to configure the correct Security Context Constraints (SCC).',
  'Qualys CS correlates container findings with host-level VM data, giving a unified risk view across the stack.',
  'Image layers are scanned individually, so you can pinpoint exactly which Dockerfile instruction introduced a vulnerability.',
  'Qualys supports scanning Helm-deployed workloads and can tag findings with the originating Helm release name.',
  'The Qualys Container Security API is RESTful and returns JSON, making it easy to integrate with SIEM and SOAR platforms.',
  'Qualys CS tracks end-of-life (EOL) base images and alerts when a container runs on an unsupported OS version.',
  'Sensor resource usage is tunable via Helm values — CPU and memory limits can be adjusted for constrained nodes.',
  'Qualys CS supports multi-cluster management, letting you view posture across dev, staging, and prod from a single pane.',
  'The platform can scan images stored in private registries without requiring the registry to be internet-accessible.',
  'Qualys Container Security risk scores feed directly into the Qualys CyberSecurity Asset Management (CSAM) platform for unified asset risk.',
  'Qualys Container Security provides agentless vulnerability scanning for containers and images.',
  'The Container Security sensor can be deployed as a DaemonSet on Kubernetes clusters.',
  'Qualys CS supports scanning images in Docker, containerd, and CRI-O runtimes.',
  'Vulnerability data is correlated with the Qualys KnowledgeBase for accurate CVE detection.',
  'Registry scanning helps identify vulnerabilities before images reach production.',
  'Runtime container scanning detects threats in running workloads without affecting performance.',
  'Qualys Container Security integrates with CI/CD pipelines for shift-left security.',
  'The platform supports AWS, Azure, and GCP container registries.',
  'Container posture assessments help enforce CIS benchmarks and security policies.',
  'Software bill of materials (SBOM) is available for scanned containers and images.',
]

export default function Chat() {
  const messages = useChatStore(state => state.messages)
  const input = useChatStore(state => state.input)
  const streaming = useChatStore(state => state.streaming)
  const setInput = useChatStore(state => state.setInput)
  const addMessage = useChatStore(state => state.addMessage)
  const appendAssistant = useChatStore(state => state.appendAssistant)
  const setLastMessageError = useChatStore(state => state.setLastMessageError)
  const setStreaming = useChatStore(state => state.setStreaming)

  const bottomRef = useRef<HTMLDivElement>(null)
  const streamBuffer = useRef('')
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastFactIndex = useRef(-1)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => {
      if (flushTimer.current) clearInterval(flushTimer.current)
    }
  }, [])

  const flushStreamBuffer = () => {
    if (!streamBuffer.current) return
    const chunk = streamBuffer.current
    streamBuffer.current = ''
    appendAssistant(chunk)
  }

  const pickFact = () => {
    let idx = Math.floor(Math.random() * QUALYS_FACTS.length)
    // Avoid repeating the same fact twice in a row
    if (idx === lastFactIndex.current && QUALYS_FACTS.length > 1) {
      idx = (idx + 1) % QUALYS_FACTS.length
    }
    lastFactIndex.current = idx
    return QUALYS_FACTS[idx]
  }

  const send = async (text: string) => {
    if (!text.trim() || streaming) return
    const fact = pickFact()
    addMessage({ role: 'user', content: text, fact })
    setInput('')
    addMessage({ role: 'assistant', content: '' })
    setStreaming(true)

    try {
      const history = messages.filter(m => m.content.trim()).map(m => ({ role: m.role, content: m.content }))
      // Batch chunks to avoid re-rendering markdown on every token
      flushTimer.current = setInterval(flushStreamBuffer, 80)
      for await (const chunk of streamChat(text, history)) {
        streamBuffer.current += chunk
      }
      // Check if the buffered content contains an error sentinel from the backend
      if (streamBuffer.current.includes('__ERROR__:')) {
        const errText = streamBuffer.current.split('__ERROR__:')[1]?.trim() ?? 'Unknown error'
        streamBuffer.current = ''
        setLastMessageError(errText)
      }
    } catch (e: any) {
      setLastMessageError(e.message)
    } finally {
      if (flushTimer.current) {
        clearInterval(flushTimer.current)
        flushTimer.current = null
      }
      flushStreamBuffer()
      setStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-8">
            <div className="text-center space-y-3">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center mx-auto shadow-lg shadow-orange-900/30">
                <Zap size={28} className="text-white" fill="white" />
              </div>
              <div>
                <p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Sheldon</p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Ask anything about your container security posture</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => send(s)}
                  disabled={streaming}
                  className="text-left text-sm p-3 rounded-xl border transition-all hover:border-blue-500 hover:bg-[var(--bg-secondary-alpha)] disabled:opacity-50"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-5 mx-auto pt-4" style={{ maxWidth: '52rem' }}>
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center flex-shrink-0 mt-1 shadow-sm shadow-orange-900/20">
                    <Zap size={15} className="text-white" fill="white" />
                  </div>
                )}
                <div className={`max-w-[95%] md:max-w-[95%] ${m.role === 'user' ? 'order-1' : 'order-2'}`}>
                  {m.role === 'user' && m.fact && (
                    <div className="mb-2 text-right">
                      <div className="inline-flex items-center gap-2 rounded-lg border-l-4 border-orange-600/60 p-2.5 text-xs text-left max-w-full" style={{ background: 'var(--bg-secondary-alpha)', color: 'var(--text-muted)' }}>
                        <span className="relative flex-shrink-0 flex items-center justify-center w-4 h-4" style={{ overflow: 'visible' }}>
                          <span className="absolute inline-flex w-4 h-4 rounded-full bg-orange-400" style={{ animation: 'zap-ripple 3s ease-out infinite' }} />
                          <span className="absolute inline-flex w-4 h-4 rounded-full bg-orange-400" style={{ animation: 'zap-ripple 3s ease-out 1s infinite' }} />
                          <span className="absolute inline-flex w-4 h-4 rounded-full bg-orange-400" style={{ animation: 'zap-ripple 3s ease-out 2s infinite' }} />
                          <span className="relative flex items-center justify-center w-4 h-4 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 shadow-sm shadow-orange-900/20">
                            <Zap size={9} fill="white" className="text-white" />
                          </span>
                        </span>
                        <span>
                          <span className="text-orange-600">Did you know?</span>{' '}
                          <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{m.fact}</span>
                        </span>
                      </div>
                    </div>
                  )}
                  {m.isError ? (
                    <div className="rounded-2xl px-4 py-3 text-sm rounded-bl-md" style={{ border: '1px solid #f87171', background: 'rgba(254,226,226,0.15)' }}>
                      <div className="flex items-start gap-2" style={{ color: '#dc2626' }}>
                        <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="font-semibold mb-1">Something went wrong</p>
                          <p className="text-xs font-mono break-all" style={{ color: '#b91c1c' }}>{m.content}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                  <div
                    className={`rounded-2xl px-4 py-3.5 text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'text-white rounded-br-sm shadow-md'
                        : 'rounded-bl-sm shadow-sm border'
                    }`}
                    style={m.role === 'user'
                      ? { background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)', whiteSpace: 'pre-wrap' }
                      : { background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)', boxShadow: '0 1px 8px 0 rgba(0,0,0,0.07)' }
                    }
                  >
                    {m.role === 'user' ? (
                      m.content
                    ) : (
                      renderAssistantContent(m.content)
                    )}
                    {streaming && i === messages.length - 1 && m.role === 'assistant' && (
                      <div className="flex items-center gap-2 mt-3 pt-2.5 border-t" style={{ borderColor: 'var(--border)' }}>
                        <span className="flex gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </span>
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Sheldon is thinking...</span>
                      </div>
                    )}
                  </div>
                  )}
                </div>
                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 order-2 shadow-sm" style={{ background: 'linear-gradient(135deg, #64748b 0%, #475569 100%)' }}>
                    <User size={15} className="text-white" />
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t flex-shrink-0 p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="mx-auto flex gap-3" style={{ maxWidth: '52rem' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
            placeholder="Ask about containers, images, vulnerabilities, or charts..."
            disabled={streaming}
            className="flex-1 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-colors border"
            style={{ background: 'var(--bg-base)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
          />
          <button
            onClick={() => send(input)}
            disabled={streaming || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 transition-colors flex items-center gap-2"
          >
            <Send size={18} />
            <span className="hidden sm:inline text-sm font-medium">Send</span>
          </button>
        </div>
        <p className="text-center text-xs mt-2" style={{ color: 'var(--text-muted)' }}>Powered by Claude on Amazon Bedrock</p>
      </div>
    </div>
  )
}
