import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Field, Message, useForm } from '../ui'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  return (
    <section className="auth-card">
      <p className="eyebrow">Nowshera Digital</p>
      <h1>Sign in</h1>
      <p className="lede">Candidates, recruiters, and the hiring manager use the same sign-in page.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            await signIn(email, password)
            navigate('/')
          })
        }}
      >
        <Message error={form.error} />
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Password">
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <button type="submit" disabled={form.busy}>
          {form.busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p>
        Looking for a job? <Link to="/signup">Create a candidate account</Link>
      </p>
    </section>
  )
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
    <section className="auth-card">
      <p className="eyebrow">Candidates</p>
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
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </section>
  )
}

export function SetPasswordPage() {
  const { updatePassword } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [password, setPassword] = useState('')

  return (
    <section className="auth-card">
      <p className="eyebrow">Recruiters</p>
      <h1>Set your password</h1>
      <p className="lede">Use the link from your invite email, then choose a password and sign in.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
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
