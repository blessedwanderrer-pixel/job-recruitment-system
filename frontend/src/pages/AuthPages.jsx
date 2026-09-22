import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Field, Message, useForm } from '../ui'

function friendlySignInError(err) {
  const raw = String(err?.message || '')
  const msg = raw.toLowerCase()
  if (msg.includes('deactivat') || msg.includes('inactive')) {
    return 'Your recruiter account is inactive. Please contact an administrator.'
  }
  if (msg.includes('invalid login') || msg.includes('invalid email or password') || msg.includes('invalid credentials')) {
    return 'Invalid email or password.'
  }
  if (msg.includes('not set up') || msg.includes('account not found') || msg.includes('user not found')) {
    return 'Account not found.'
  }
  if (
    msg.includes('failed to fetch') ||
    msg.includes('network') ||
    msg.includes('unavailable') ||
    msg.includes('could not verify') ||
    msg.includes('the request failed')
  ) {
    return 'The sign-in service is unavailable. Try again in a moment.'
  }
  return raw || 'Sign in failed.'
}

export const LOGIN_PORTALS = {
  admin: {
    role: 'admin',
    eyebrow: 'Administration',
    title: 'Admin Sign In',
    subtitle: 'Sign in to manage jobs, recruiters, candidates, and hiring activity.',
    button: 'Sign In as Admin',
    successPath: '/admin',
    wrongRole: 'This account does not have admin access.',
  },
  recruiter: {
    role: 'recruiter',
    eyebrow: 'Recruitment',
    title: 'Recruiter Sign In',
    subtitle: 'Sign in to manage candidates and hiring applications.',
    button: 'Sign In as Recruiter',
    successPath: '/recruiter',
    wrongRole: 'This account does not have recruiter access.',
  },
  candidate: {
    role: 'candidate',
    eyebrow: 'Career Portal',
    title: 'Candidate Sign In',
    subtitle: 'Sign in to find jobs, apply, and track your applications.',
    button: 'Sign In as Candidate',
    successPath: '/jobs',
    wrongRole: 'This account does not have candidate access.',
    signup: true,
  },
}

function PasswordField({ value, onChange, id = 'password' }) {
  const [visible, setVisible] = useState(false)
  return (
    <Field label="Password">
      <div className="password-wrap">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="current-password"
          required
        />
        <button
          type="button"
          className="text-btn password-toggle"
          aria-pressed={visible}
          aria-label={visible ? 'Hide password' : 'Show password'}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
    </Field>
  )
}

export function LoginChooserPage() {
  return (
    <section className="auth-card glass-card">
      <p className="eyebrow">Nowshera Digital</p>
      <h1>Choose your account</h1>
      <p className="lede">Sign in with the portal that matches your role. Access is decided by your account, not by this page.</p>
      <div className="portal-grid">
        <Link className="portal-tile" to="/candidate/login">
          <span className="eyebrow">Career Portal</span>
          <strong>Candidate</strong>
        </Link>
        <Link className="portal-tile" to="/recruiter/login">
          <span className="eyebrow">Recruitment</span>
          <strong>Recruiter</strong>
        </Link>
        <Link className="portal-tile" to="/admin/login">
          <span className="eyebrow">Administration</span>
          <strong>Admin</strong>
        </Link>
      </div>
    </section>
  )
}

export function RoleLoginPage({ portal }) {
  const config = LOGIN_PORTALS[portal]
  const { signIn, signOut } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  return (
    <section className={`auth-card glass-card portal-${config.role}`}>
      <p className="eyebrow">{config.eyebrow}</p>
      <h1>{config.title}</h1>
      <p className="lede">{config.subtitle}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            let me
            try {
              me = await signIn(email, password)
            } catch (err) {
              throw new Error(friendlySignInError(err))
            }
            if (!me?.role || me.role !== config.role) {
              await signOut()
              throw new Error(config.wrongRole)
            }
            if (config.role === 'recruiter' && me.is_active === false) {
              await signOut()
              throw new Error('Your recruiter account is inactive. Please contact an administrator.')
            }
            navigate(config.successPath)
          })
        }}
      >
        <Message error={form.error} />
        <Field label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </Field>
        <PasswordField value={password} onChange={setPassword} />
        <button type="submit" disabled={form.busy}>
          {form.busy ? 'Signing in…' : config.button}
        </button>
      </form>
      {config.signup ? (
        <p>
          Don&apos;t have an account? <Link to="/signup">Create a candidate account</Link>
        </p>
      ) : (
        <p className="muted">
          Need a different portal? <Link to="/login">Choose your account</Link>
        </p>
      )}
    </section>
  )
}

export function LoginPage() {
  return <LoginChooserPage />
}

export function SignupPage() {
  const { signUp } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  return (
    <section className="auth-card glass-card portal-candidate">
      <p className="eyebrow">Career Portal</p>
      <h1>Create an account</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            await signUp({ full_name: fullName, phone, email, password })
            navigate('/jobs')
          })
        }}
      >
        <Message error={form.error} />
        <Field label="Full name">
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </Field>
        <Field label="Phone number">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </Field>
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Password">
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
        </Field>
        <button type="submit" disabled={form.busy}>
          {form.busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p>
        Already registered? <Link to="/candidate/login">Sign in</Link>
      </p>
    </section>
  )
}

export function SetPasswordPage() {
  const { updatePassword } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [password, setPassword] = useState('')
  const params = new URLSearchParams(window.location.search)
  const inviteEmail = params.get('email') || ''
  const inviteToken = params.get('token') || ''

  return (
    <section className="auth-card glass-card portal-recruiter">
      <p className="eyebrow">Recruitment</p>
      <h1>Set your password</h1>
      <p className="lede">Use the link from your invite email, then choose a password and sign in.</p>
      {inviteEmail ? <p className="muted">Account: {inviteEmail}</p> : <p className="muted">This page needs the email and token from your invite link.</p>}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            if (!inviteEmail || !inviteToken) {
              throw new Error('This set-password link is invalid.')
            }
            await updatePassword(password)
            navigate('/recruiter/jobs')
          })
        }}
      >
        <Message error={form.error} />
        <Field label="New password">
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
        </Field>
        <button type="submit" disabled={form.busy}>
          Save password
        </button>
      </form>
    </section>
  )
}
