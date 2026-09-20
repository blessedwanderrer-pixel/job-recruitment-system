import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, jobTypeLabel, stageLabel } from '../api'
import { useAuth } from '../auth'
import { Field, Message, useForm } from '../ui'

export function RecruiterJobsPage() {
  const { token } = useAuth()
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api('/api/jobs', { token }).then(setJobs).catch((err) => setError(err.message))
  }, [token])
  return (
    <section>
      <h1>Assigned jobs</h1>
      <Message error={error} />
      <div className="card-grid">
        {jobs.map((job) => (
          <article className="card" key={job.id}>
            <p className="eyebrow">{job.status}</p>
            <h2>{job.title}</h2>
            <p>
              {job.department} · {job.location} · {jobTypeLabel(job.job_type)}
            </p>
            <Link className="btn-link" to={`/recruiter/jobs/${job.id}`}>
              Review applicants
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}

export function RecruiterJobPage() {
  const { id } = useParams()
  const { token } = useAuth()
  const [job, setJob] = useState(null)
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([api(`/api/jobs/${id}`, { token }), api(`/api/jobs/${id}/applications`, { token })])
      .then(([j, a]) => {
        setJob(j)
        setRows(a)
      })
      .catch((err) => setError(err.message))
  }, [id, token])
  if (!job && !error) return <p className="muted">Loading…</p>
  return (
    <section>
      <h1>{job?.title}</h1>
      <Message error={error} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Stage</th>
              <th>Applied</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {row.candidate?.full_name}
                  <div className="muted">{row.candidate?.email}</div>
                </td>
                <td>
                  <span className={`pill ${row.stage}`}>{stageLabel(row.stage)}</span>
                </td>
                <td>{formatDate(row.created_at)}</td>
                <td>
                  <Link to={`/recruiter/applications/${row.id}`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function RecruiterApplicationPage() {
  const { id } = useParams()
  const { token } = useAuth()
  const [row, setRow] = useState(null)
  const form = useForm()
  const [note, setNote] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [location, setLocation] = useState('')
  const [meeting, setMeeting] = useState('')

  function load() {
    return api(`/api/applications/${id}`, { token }).then(setRow)
  }
  useEffect(() => {
    load().catch((err) => form.setError(err.message))
  }, [id, token])

  async function act(path, body) {
    await form.run(async () => {
      await api(path, { method: 'POST', token, body })
      await load()
    })
  }

  if (!row && !form.error) return <p className="muted">Loading…</p>
  if (!row) return <Message error={form.error} />

  const closed = row.job?.status === 'closed'
  const canAdvance = ['applied', 'interview', 'offer'].includes(row.stage) && !closed
  const canInterview = row.stage === 'shortlisted' && !closed
  const canReject = !['hired', 'rejected', 'withdrawn'].includes(row.stage)

  return (
    <section className="split">
      <div className="stack">
        <p className="eyebrow">{row.job?.title}</p>
        <h1>{row.candidate?.full_name}</h1>
        <p>
          {row.candidate?.email} · {row.candidate?.phone}
        </p>
        <p>
          Stage: <span className={`pill ${row.stage}`}>{stageLabel(row.stage)}</span>
        </p>
        <Message error={form.error} success={form.success} />
        <div className="actions">
          <button
            type="button"
            onClick={() =>
              form.run(async () => {
                const data = await api(`/api/applications/${id}/cv`, { token })
                if (String(data.url).startsWith('memory://')) {
                  form.setSuccess('CV file is attached to this application.')
                  return
                }
                window.open(data.url, '_blank', 'noopener')
              })
            }
          >
            Open CV
          </button>
          {canAdvance ? (
            <button type="button" onClick={() => act(`/api/applications/${id}/advance`)}>
              Move to next stage
            </button>
          ) : null}
          {canReject ? (
            <button type="button" className="danger" onClick={() => act(`/api/applications/${id}/reject`)}>
              Reject
            </button>
          ) : null}
        </div>
        {closed && canReject ? <p className="muted">This job is closed. Remaining applications can only be rejected.</p> : null}
        {canInterview ? (
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault()
              act(`/api/applications/${id}/interview`, {
                starts_at: new Date(startsAt).toISOString(),
                location: location || null,
                meeting_link: meeting || null,
              })
            }}
          >
            <h2>Schedule 1-hour interview</h2>
            <Field label="Date and time">
              <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} required />
            </Field>
            <Field label="Location">
              <input value={location} onChange={(e) => setLocation(e.target.value)} />
            </Field>
            <Field label="Meeting link">
              <input value={meeting} onChange={(e) => setMeeting(e.target.value)} />
            </Field>
            <button type="submit" disabled={form.busy}>
              Schedule interview
            </button>
          </form>
        ) : null}
        <div className="panel">
          <h2>History</h2>
          <ul>
            {row.history?.map((h) => (
              <li key={h.id}>
                {h.from_stage || '—'} → {stageLabel(h.to_stage)} · {formatDate(h.created_at)}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <aside className="panel">
        <h2>Private notes</h2>
        <ul>
          {row.notes?.map((n) => (
            <li key={n.id}>
              {n.body}
              <div className="muted">{formatDate(n.created_at)}</div>
            </li>
          ))}
        </ul>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            act(`/api/applications/${id}/notes`, { body: note }).then(() => setNote(''))
          }}
        >
          <Field label="Add a note">
            <textarea value={note} onChange={(e) => setNote(e.target.value)} required />
          </Field>
          <button type="submit" disabled={form.busy}>
            Save note
          </button>
        </form>
      </aside>
    </section>
  )
}
