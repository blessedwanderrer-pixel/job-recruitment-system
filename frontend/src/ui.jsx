import { useEffect, useState } from 'react'
import { Navigate, NavLink, useLocation, useNavigate } from 'react-router-dom'
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

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function StatCounter({ value, className = '' }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const target = Number(value) || 0
    if (prefersReducedMotion() || target <= 0) {
      setShown(target)
      return
    }
    const start = performance.now()
    const duration = 700
    let frame
    function tick(now) {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - t) * (1 - t)
      setShown(Math.round(target * eased))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value])
  return <span className={className}>{shown}</span>
}

export function ConfirmDialog({ title, message, error, confirmLabel = 'Confirm', busy, onCancel, onConfirm }) {
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title">{title}</h2>
        <p className="lede">{message}</p>
        <Message error={error} />
        <div className="actions">
          <button type="button" className="text-btn" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export function Shell({ children }) {
  const { profile, signOut, role } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
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

  const guestLinks = [
    ['/login', 'Sign in'],
    ['/signup', 'Create account'],
  ]

  return (
    <div className="app-shell">
      <div className="scene-bg" aria-hidden="true">
        <div className="scene-glow" />
        <div className="scene-grid" />
        <span className="scene-orb orb-a" />
        <span className="scene-orb orb-b" />
        <span className="scene-orb orb-c" />
      </div>
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
            {guestLinks.map(([to, label]) => (
              <NavLink key={to} to={to}>
                {label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="page page-stage" key={location.pathname}>
        {children}
      </main>
    </div>
  )
}

export function roleHome(role) {
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'recruiter') return '/recruiter/jobs'
  return '/jobs'
}

export function GuestOnly({ children }) {
  const { loading, profile } = useAuth()
  if (loading) return <p className="muted">Loading…</p>
  if (profile) return <Navigate to={roleHome(profile.role)} replace />
  return children
}

export function RequireAuth({ role, children }) {
  const { loading, profile } = useAuth()
  if (loading) return <p className="muted">Loading…</p>
  if (!profile) return <Navigate to="/login" replace />
  if (role && profile.role !== role) {
    return <Navigate to={roleHome(profile.role)} replace />
  }
  if (profile.role === 'recruiter' && profile.is_active === false) {
    return <Navigate to="/recruiter/login" replace />
  }
  return children
}
