import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, supabase } from './api'

const AuthContext = createContext(null)
const MEMORY = import.meta.env.VITE_USE_MEMORY === 'true'
const TOKEN_KEY = 'ats_token'

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadProfile(nextSession) {
    if (!nextSession?.access_token) {
      setProfile(null)
      return
    }
    const me = await api('/api/me', { token: nextSession.access_token })
    setProfile(me)
  }

  function remember(token) {
    const next = { access_token: token }
    localStorage.setItem(TOKEN_KEY, token)
    setSession(next)
    return next
  }

  useEffect(() => {
    let alive = true
    async function boot() {
      try {
        if (MEMORY) {
          const token = localStorage.getItem(TOKEN_KEY)
          if (token) {
            const next = { access_token: token }
            setSession(next)
            await loadProfile(next)
          }
          return
        }
        if (!supabase) return
        const { data } = await supabase.auth.getSession()
        if (!alive) return
        setSession(data.session)
        if (data.session) await loadProfile(data.session)
      } catch (err) {
        if (alive) {
          setError(err.message)
          localStorage.removeItem(TOKEN_KEY)
        }
      } finally {
        if (alive) setLoading(false)
      }
    }
    boot()
    if (MEMORY || !supabase) return () => { alive = false }
    const { data: sub } = supabase.auth.onAuthStateChange(async (_event, next) => {
      setSession(next)
      try {
        if (next) await loadProfile(next)
        else setProfile(null)
      } catch (err) {
        setError(err.message)
      }
    })
    return () => {
      alive = false
      sub.subscription.unsubscribe()
    }
  }, [])

  async function signIn(email, password) {
    if (MEMORY) {
      const data = await api('/api/auth/login', { method: 'POST', body: { email, password } })
      await loadProfile(remember(data.token))
      return
    }
    if (!supabase) throw new Error('Supabase is not configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.')
    const { data, error: authError } = await supabase.auth.signInWithPassword({ email, password })
    if (authError) throw new Error(authError.message)
    setSession(data.session)
    await loadProfile(data.session)
  }

  async function signUp(payload) {
    await api('/api/auth/register', { method: 'POST', body: payload })
    await signIn(payload.email, payload.password)
  }

  async function signOut() {
    localStorage.removeItem(TOKEN_KEY)
    if (supabase && !MEMORY) await supabase.auth.signOut()
    setSession(null)
    setProfile(null)
  }

  async function refresh() {
    if (session) await loadProfile(session)
  }

  async function updatePassword(password, extra = {}) {
    const params = new URLSearchParams(window.location.search)
    const email = extra.email || params.get('email')
    const token = extra.token || params.get('token')
    if (email && token) {
      await api('/api/auth/set-password', {
        method: 'POST',
        body: { email, token, password },
      })
      await signIn(email, password)
      return
    }
    if (MEMORY) {
      throw new Error('This set-password link is invalid.')
    }
    if (!supabase) throw new Error('Supabase is not configured.')
    const { error: authError } = await supabase.auth.updateUser({ password })
    if (authError) throw new Error(authError.message)
    const { data } = await supabase.auth.getSession()
    setSession(data.session)
    if (data.session) await loadProfile(data.session)
  }

  const value = useMemo(
    () => ({ session, profile, loading, error, token: session?.access_token, role: profile?.role, signIn, signUp, signOut, refresh, updatePassword }),
    [session, profile, loading, error],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
