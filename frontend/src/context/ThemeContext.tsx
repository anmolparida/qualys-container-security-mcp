import { createContext, useContext, useState, useEffect } from 'react'

interface ThemeCtx { dark: boolean; toggle: () => void }

const Ctx = createContext<ThemeCtx>({ dark: false, toggle: () => {} })

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Light (Qualys console look) is the default; dark is opt-in.
  const [dark, setDark] = useState(() => {
    try { return localStorage.getItem('theme') === 'dark' } catch { return false }
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    document.documentElement.classList.remove('light')
    try { localStorage.setItem('theme', dark ? 'dark' : 'light') } catch { /* ignore */ }
  }, [dark])

  return (
    <Ctx.Provider value={{ dark, toggle: () => setDark(d => !d) }}>
      {children}
    </Ctx.Provider>
  )
}

export const useTheme = () => useContext(Ctx)
