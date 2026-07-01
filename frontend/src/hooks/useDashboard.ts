import { useEffect } from 'react'
import { fetchDashboard } from '../lib/api'
import { useDashboardStore } from '../store/dashboardStore'
import type { DashboardEndpoint } from '../types/api'

export function useDashboard<T = any>(key: DashboardEndpoint) {
  const setLoading = useDashboardStore(s => s.setLoading)
  const setData = useDashboardStore(s => s.setData)
  const setError = useDashboardStore(s => s.setError)
  const data = useDashboardStore(s => s.cache[key]) as T | undefined
  const state = useDashboardStore(s => s.states[key] ?? 'idle')
  const error = useDashboardStore(s => s.errors[key] ?? '')

  const load = async () => {
    setLoading(key)
    try {
      const result = await fetchDashboard<T>(key)
      setData(key, result)
    } catch (e: any) {
      setError(key, e.message)
    }
  }

  useEffect(() => {
    load()
  }, [key])

  return { data, state, error, refresh: load }
}
