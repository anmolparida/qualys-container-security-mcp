import { useEffect } from 'react'
import { fetchDashboard } from '../lib/api'
import { useDashboardStore } from '../store/dashboardStore'
import type { DashboardEndpoint } from '../types/api'

export function useDashboard<T = any>(key: DashboardEndpoint) {
  const store = useDashboardStore()
  const data = store.getData(key) as T
  const state = store.getState(key)
  const error = store.getError(key)

  const load = async () => {
    store.setLoading(key)
    try {
      const result = await fetchDashboard<T>(key)
      store.setData(key, result)
    } catch (e: any) {
      store.setError(key, e.message)
    }
  }

  useEffect(() => {
    if (state === 'idle') {
      load()
    }
  }, [key, state])

  return { data, state, error, refresh: load }
}
