import { create } from 'zustand'

type LoadingState = 'idle' | 'loading' | 'error' | 'success'

interface DashboardState {
  // Cache for each endpoint
  cache: Record<string, any>
  states: Record<string, LoadingState>
  errors: Record<string, string>
  setData: (key: string, data: any) => void
  setLoading: (key: string) => void
  setError: (key: string, error: string) => void
  getData: (key: string) => any
  getState: (key: string) => LoadingState
  getError: (key: string) => string
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  cache: {},
  states: {},
  errors: {},
  setData: (key, data) => set((state) => ({
    cache: { ...state.cache, [key]: data },
    states: { ...state.states, [key]: 'success' },
    errors: { ...state.errors, [key]: '' },
  })),
  setLoading: (key) => set((state) => ({
    states: { ...state.states, [key]: 'loading' },
  })),
  setError: (key, error) => set((state) => ({
    states: { ...state.states, [key]: 'error' },
    errors: { ...state.errors, [key]: error },
  })),
  getData: (key) => get().cache[key],
  getState: (key) => get().states[key] ?? 'idle',
  getError: (key) => get().errors[key] ?? '',
}))
