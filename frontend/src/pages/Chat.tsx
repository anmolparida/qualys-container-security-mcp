import { useState, useRef, useEffect, Component } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamChat } from '../lib/api'
import { Send, Bot, User } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
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
      <ReactMarkdown remarkPlugins={[remarkGfm as any]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </MarkdownErrorBoundary>
  )
}

const SUGGESTIONS = [
  'Show me all critical vulnerabilities across containers',
  'Which images have the most high severity CVEs?',
  'List all running containers with their vulnerability counts',
  'What is the current K8s posture score?',
  'Are there any secrets detected in my images?',
  'Show registry scan status for all registries',
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const streamBuffer = useRef('')
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  const send = async (text: string) => {
    if (!text.trim() || streaming) return
    const userMsg: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
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
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <h2 className="text-xl font-bold mb-4">AI Security Assistant</h2>

      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6">
          <div className="text-center">
            <Bot size={48} className="mx-auto text-blue-400 mb-3" />
            <p className="font-medium" style={{ color: 'var(--text-secondary)' }}>Ask anything about your container security</p>
            <p className="text-slate-500 text-sm mt-1">Powered by Claude via AWS Bedrock</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                onClick={() => send(s)}
                className="text-left text-sm p-3 rounded-lg border transition-all hover:border-blue-500"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-1">
                  <Bot size={16} />
                </div>
              )}
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${m.role === 'user' ? 'max-w-[75%]' : 'max-w-[90%]'}`}
                style={m.role === 'user'
                  ? { background: '#2563eb', color: '#ffffff', borderRadius: '1rem 1rem 0.25rem 1rem', whiteSpace: 'pre-wrap' }
                  : { background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '1rem 1rem 1rem 0.25rem' }
                }
              >
                {m.role === 'user' ? (
                  m.content
                ) : streaming && i === messages.length - 1 && m.role === 'assistant' ? (
                  <pre className="whitespace-pre-wrap font-sans text-sm">{m.content}</pre>
                ) : (
                  <SafeMarkdown content={m.content} />
                )}
                {streaming && i === messages.length - 1 && m.role === 'assistant' && m.content === '' && (
                  <span className="inline-flex gap-1 items-center">
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                )}
              </div>
              {m.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0 mt-1">
                  <User size={16} />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      <div className="mt-4 flex gap-3">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
          placeholder="Ask about containers, images, vulnerabilities..."
          disabled={streaming}
          className="flex-1 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-colors border"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
        />
        <button
          onClick={() => send(input)}
          disabled={streaming || !input.trim()}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 transition-colors"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
