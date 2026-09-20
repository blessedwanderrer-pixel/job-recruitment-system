import { useState } from 'react'
import { Navigate, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'

export function Message({ error, success }) {
  if (error) return <p className="banner error">{error}</p>
  if (success) return <p className="banner success">{success}</p>
  return null
}

export function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}

export function useForm() {
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  async function run(fn) {
    setError('')
    setSuccess('')
    setBusy(true)
    try {
      await fn()
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }
  return { error, success, busy, setSuccess, setError, run }
}

export function Shell({ children }) {
  const { profile, signOut, role } = useAuth()
  const navigate = useNavigate()
  const links =
    role === 'admin'
      ? [
          ['/admin/dashboard', 'Dashboard'],
          ['/admin/jobs', 'Jobs'],
          ['/admin/recruiters', 'Recruiters'],
        ]
      : role === 'recruiter'
        ? [['/recruiter/jobs', 'My jobs']]
        : [
            ['/jobs', 'Jobs'],
            ['/cv', 'My CV'],
            ['/applications', 'My applications'],
          ]

  async function onSignOut() {
    await signOut()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <strong>Nowshera Digital</strong>
          <span>Hiring</span>
        </div>
        {profile ? (
          <>
            <nav>
              {links.map(([to, label]) => (
                <NavLink key={to} to={to}>
                  {label}
                </NavLink>
              ))}
            </nav>
            <div className="session">
              <span>
                {profile.full_name} · {role}
              </span>
              <button type="button" className="text-btn" onClick={onSignOut}>
                Sign out
              </button>
            </div>
          </>
        ) : (
          <nav>
            <NavLink to="/login">Sign in</NavLink>
            <NavLink to="/signup">Create account</NavLink>
          </nav>
        )}
      </header>
      <main className="page">{children}</main>
    </div>
  )
}

export function RequireAuth({ role, children }) {
  const { loading, profile } = useAuth()
  const navigate = useNavigate()
  if (loading) return <p className="muted">Loading…</p>
  if (!profile) return <Navigate to="/login" replace />
  if (role && profile.role !== role) {
    const home = profile.role === 'admin' ? '/admin/dashboard' : profile.role === 'recruiter' ? '/recruiter/jobs' : '/jobs'
    return <Navigate to={home} replace />
  }
  return children
}
