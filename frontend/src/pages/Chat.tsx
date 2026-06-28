import { useState, useRef, useEffect, Component } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamChat } from '../lib/api'
import { Send, Bot, User } from 'lucide-react'
import ChartRenderer from '../components/ChartRenderer'

interface Message {
  role: 'user' | 'assistant'
  content: string
  fact?: string
}

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
  strong: ({ children }: any) => <strong className="font-semibold text-blue-400">{children}</strong>,
  p: ({ children }: any) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }: any) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
  code: ({ children }: any) => <code className="px-1 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-secondary)' }}>{children}</code>,
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
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [currentFact, setCurrentFact] = useState('')
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
    setMessages(prev => {
      const updated = [...prev]
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        content: updated[updated.length - 1].content + chunk,
      }
      return updated
    })
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
    const userMsg: Message = { role: 'user', content: text, fact }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setCurrentFact(fact)
    setStreaming(true)

    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      // Batch chunks to avoid re-rendering markdown on every token
      flushTimer.current = setInterval(flushStreamBuffer, 80)
      for await (const chunk of streamChat(text, history)) {
        streamBuffer.current += chunk
      }
    } catch (e: any) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: `Error: ${e.message}` }
        return updated
      })
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
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto shadow-lg shadow-blue-900/20">
                <Bot size={32} className="text-white" />
              </div>
              <div>
                <p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>AI Security Assistant</p>
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
          <div className="space-y-5 max-w-4xl mx-auto pt-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-1">
                    <Bot size={16} className="text-white" />
                  </div>
                )}
                <div className={`max-w-[85%] md:max-w-[75%] ${m.role === 'user' ? 'order-1' : 'order-2'}`}>
                  {m.role === 'user' && m.fact && (
                    <div className="mb-2 text-right">
                      <div className="inline-block rounded-lg border-l-4 border-blue-500 p-2.5 text-xs text-left max-w-full" style={{ background: 'var(--bg-secondary-alpha)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                        <span className="font-semibold not-italic" style={{ color: 'var(--text-secondary)' }}>Did you know?</span>{' '}
                        <span className="italic">{m.fact}</span>
                      </div>
                    </div>
                  )}
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-md'
                        : 'border rounded-bl-md'
                    }`}
                    style={m.role === 'user'
                      ? { whiteSpace: 'pre-wrap' }
                      : { background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' }
                    }
                  >
                    {m.role === 'user' ? (
                      m.content
                    ) : streaming && i === messages.length - 1 && m.role === 'assistant' ? (
                      <pre className="whitespace-pre-wrap font-sans text-sm">{m.content}</pre>
                    ) : (
                      renderAssistantContent(m.content)
                    )}
                    {streaming && i === messages.length - 1 && m.role === 'assistant' && (
                      <div className="flex items-center gap-3 mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                        <div className="relative w-5 h-5">
                          <span className="absolute inset-0 rounded-full border-2 border-slate-500/30" />
                          <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-400 animate-spin" />
                        </div>
                        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Analyzing your Qualys data...</span>
                      </div>
                    )}
                  </div>
                </div>
                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0 mt-1 order-2">
                    <User size={16} className="text-white" />
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
        <div className="max-w-4xl mx-auto flex gap-3">
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
