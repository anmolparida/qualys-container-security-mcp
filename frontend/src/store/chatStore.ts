import { create } from 'zustand'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  fact?: string
  isError?: boolean
}

interface ChatState {
  messages: Message[]
  input: string
  streaming: boolean
  setInput: (input: string) => void
  addMessage: (message: Message) => void
  appendAssistant: (chunk: string) => void
  setLastMessageError: (errorText: string) => void
  setStreaming: (streaming: boolean) => void
  reset: () => void
  /** A question queued from elsewhere in the app (e.g. Threat Intel → Ask Sheldon). */
  pending: string | null
  setPending: (q: string | null) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  input: '',
  streaming: false,
  setInput: (input) => set({ input }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  appendAssistant: (chunk) => set((state) => {
    const messages = [...state.messages]
    const last = messages[messages.length - 1]
    if (last && last.role === 'assistant') {
      last.content += chunk
    } else {
      messages.push({ role: 'assistant', content: chunk })
    }
    return { messages }
  }),
  setLastMessageError: (errorText) => set((state) => {
    const messages = [...state.messages]
    const last = messages[messages.length - 1]
    if (last && last.role === 'assistant') {
      last.content = errorText
      last.isError = true
    }
    return { messages }
  }),
  setStreaming: (streaming) => set({ streaming }),
  reset: () => set({ messages: [], input: '', streaming: false, pending: null }),
  pending: null,
  setPending: (q) => set({ pending: q }),
}))
