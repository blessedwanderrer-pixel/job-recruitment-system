import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, jobTypeLabel, stageLabel } from '../api'
import { useAuth } from '../auth'
import { Field, Message, useForm } from '../ui'

const STAGES = ['applied', 'shortlisted', 'interview', 'offer', 'hired', 'rejected', 'withdrawn']

export function AdminDashboardPage() {
  const { token } = useAuth()
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api('/api/admin/dashboard', { token }).then(setRows).catch((err) => setError(err.message))
  }, [token])
  return (
    <section>
      <h1>Hiring dashboard</h1>
      <p className="lede">Application counts per job and stage, including withdrawn.</p>
      <Message error={error} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Total</th>
              {STAGES.map((s) => (
                <th key={s}>{stageLabel(s)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.job.id}>
                <td>
                  <Link to={`/admin/jobs/${row.job.id}`}>{row.job.title}</Link>
                </td>
                <td>{row.job.status}</td>
                <td>{row.total_applied}</td>
                {STAGES.map((s) => (
                  <td key={s}>{row.stages[s]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function AdminRecruitersPage() {
  const { token } = useAuth()
  const [rows, setRows] = useState([])
  const form = useForm()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  function load() {
    return api('/api/admin/recruiters', { token }).then(setRows)
  }
  useEffect(() => {
    load().catch((err) => form.setError(err.message))
  }, [token])
  return (
    <section className="stack">
      <h1>Recruiters</h1>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            await api('/api/admin/recruiters', { method: 'POST', token, body: { full_name: fullName, email } })
            setFullName('')
            setEmail('')
            form.setSuccess('Recruiter created. They will receive a set-password email.')
            await load()
          })
        }}
      >
        <h2>Add recruiter</h2>
        <Message error={form.error} success={form.success} />
        <Field label="Name">
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </Field>
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <button type="submit" disabled={form.busy}>
          Add recruiter
        </button>
      </form>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.full_name}</td>
                <td>{row.email}</td>
                <td>{row.is_active ? 'Active' : 'Deactivated'}</td>
                <td>
                  {row.is_active ? (
                    <button
                      type="button"
                      className="text-btn"
                      onClick={() =>
                        form.run(async () => {
                          await api(`/api/admin/recruiters/${row.id}/deactivate`, { method: 'POST', token })
                          await load()
                        })
                      }
                    >
                      Deactivate
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function AdminJobsPage() {
  const { token } = useAuth()
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api('/api/jobs', { token }).then(setJobs).catch((err) => setError(err.message))
  }, [token])
  return (
    <section>
      <div className="heading-row">
        <h1>Jobs</h1>
        <Link className="btn-link" to="/admin/jobs/new">
          Create job
        </Link>
      </div>
      <Message error={error} />
      <div className="card-grid">
        {jobs.map((job) => (
          <article className="card" key={job.id}>
            <p className="eyebrow">{job.status}</p>
            <h2>{job.title}</h2>
            <p>
              {job.department} · {jobTypeLabel(job.job_type)} · {job.openings} opening(s)
            </p>
            <Link to={`/admin/jobs/${job.id}`}>Manage</Link>
          </article>
        ))}
      </div>
    </section>
  )
}

export function AdminJobNewPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const form = useForm()
  const [payload, setPayload] = useState({
    title: '',
    department: '',
    location: '',
    job_type: 'full_time',
    description: '',
    requirements: '',
    last_date_to_apply: '',
    openings: 1,
  })
  function set(key, value) {
    setPayload((p) => ({ ...p, [key]: value }))
  }
  return (
    <section className="stack">
      <h1>Create job</h1>
      <p className="lede">Saved as a Draft. Candidates cannot see it until you open it.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            const job = await api('/api/admin/jobs', { method: 'POST', token, body: { ...payload, openings: Number(payload.openings) } })
            navigate(`/admin/jobs/${job.id}`)
          })
        }}
      >
        <Message error={form.error} />
        <Field label="Title">
          <input value={payload.title} onChange={(e) => set('title', e.target.value)} required />
        </Field>
        <Field label="Department">
          <input value={payload.department} onChange={(e) => set('department', e.target.value)} required />
        </Field>
        <Field label="Location">
          <input value={payload.location} onChange={(e) => set('location', e.target.value)} required />
        </Field>
        <Field label="Job type">
          <select value={payload.job_type} onChange={(e) => set('job_type', e.target.value)}>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="internship">Internship</option>
          </select>
        </Field>
        <Field label="Description">
          <textarea value={payload.description} onChange={(e) => set('description', e.target.value)} required />
        </Field>
        <Field label="Requirements">
          <textarea value={payload.requirements} onChange={(e) => set('requirements', e.target.value)} required />
        </Field>
        <Field label="Last date to apply">
          <input type="date" value={payload.last_date_to_apply} onChange={(e) => set('last_date_to_apply', e.target.value)} required />
        </Field>
        <Field label="Openings">
          <input type="number" min="1" value={payload.openings} onChange={(e) => set('openings', e.target.value)} required />
        </Field>
        <button type="submit" disabled={form.busy}>
          Save draft
        </button>
      </form>
    </section>
  )
}

export function AdminJobDetailPage() {
  const { id } = useParams()
  const { token } = useAuth()
  const form = useForm()
  const [job, setJob] = useState(null)
  const [recruiters, setRecruiters] = useState([])
  const [selected, setSelected] = useState([])
  const [apps, setApps] = useState([])

  async function load() {
    const [j, recs] = await Promise.all([api(`/api/jobs/${id}`, { token }), api('/api/admin/recruiters', { token })])
    setJob(j)
    setRecruiters(recs.filter((r) => r.is_active))
    setSelected(j.recruiter_ids || [])
    if (j.status !== 'draft') {
      const rows = await api(`/api/jobs/${id}/applications`, { token })
      setApps(rows)
    } else {
      setApps([])
    }
  }
  useEffect(() => {
    load().catch((err) => form.setError(err.message))
  }, [id, token])

  if (!job && !form.error) return <p className="muted">Loading…</p>
  if (!job) return <Message error={form.error} />

  return (
    <section className="stack">
      <p className="eyebrow">{job.status}</p>
      <h1>{job.title}</h1>
      <p>
        {job.department} · {job.location} · {jobTypeLabel(job.job_type)} · {job.openings} opening(s) · Apply by {job.last_date_to_apply}
      </p>
      <Message error={form.error} success={form.success} />
      <div className="panel">
        <h2>Recruiters</h2>
        {recruiters.map((r) => (
          <label key={r.id} className="check">
            <input
              type="checkbox"
              checked={selected.includes(r.id)}
              onChange={(e) => setSelected((cur) => (e.target.checked ? [...cur, r.id] : cur.filter((x) => x !== r.id)))}
            />
            {r.full_name} ({r.email})
          </label>
        ))}
        <div className="actions">
          <button
            type="button"
            onClick={() =>
              form.run(async () => {
                await api(`/api/admin/jobs/${id}/recruiters`, { method: 'POST', token, body: { recruiter_ids: selected } })
                form.setSuccess('Recruiters updated.')
                await load()
              })
            }
          >
            Save recruiters
          </button>
          {job.status === 'draft' ? (
            <button
              type="button"
              onClick={() =>
                form.run(async () => {
                  await api(`/api/admin/jobs/${id}/open`, { method: 'POST', token, body: { recruiter_ids: selected } })
                  form.setSuccess('Job is open. Candidates can now apply.')
                  await load()
                })
              }
            >
              Open job
            </button>
          ) : null}
          {job.status !== 'closed' ? (
            <button
              type="button"
              className="danger"
              onClick={() =>
                form.run(async () => {
                  await api(`/api/admin/jobs/${id}/close`, { method: 'POST', token })
                  form.setSuccess('Job closed.')
                  await load()
                })
              }
            >
              Close job
            </button>
          ) : null}
        </div>
      </div>
      <div className="table-wrap">
        <h2>Applications</h2>
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Stage</th>
            </tr>
          </thead>
          <tbody>
            {apps.map((row) => (
              <tr key={row.id}>
                <td>{row.candidate?.full_name}</td>
                <td>
                  <span className={`pill ${row.stage}`}>{stageLabel(row.stage)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
