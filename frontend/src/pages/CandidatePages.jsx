import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, jobTypeLabel, stageLabel } from '../api'
import { useAuth } from '../auth'
import { Field, Message, useForm } from '../ui'

export function JobsPage() {
  const { token } = useAuth()
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    api('/api/jobs', { token }).then(setJobs).catch((err) => setError(err.message))
  }, [token])
  return (
    <section>
      <h1>Open roles</h1>
      <p className="lede">Browse jobs at Nowshera Digital. Upload your CV, then apply from the job page.</p>
      <Message error={error} />
      <div className="card-grid">
        {jobs.map((job) => (
          <article className="card" key={job.id}>
            <p className="eyebrow">{job.department}</p>
            <h2>{job.title}</h2>
            <p>
              {job.location} · {jobTypeLabel(job.job_type)}
            </p>
            <p>Apply by {job.last_date_to_apply}</p>
            <Link className="btn-link" to={`/jobs/${job.id}`}>
              View and apply
            </Link>
          </article>
        ))}
      </div>
      {jobs.length === 0 && !error ? <p className="muted">There are no open jobs right now.</p> : null}
    </section>
  )
}

export function JobDetailPage() {
  const { id } = useParams()
  const { token, refresh } = useAuth()
  const [job, setJob] = useState(null)
  const form = useForm()
  useEffect(() => {
    api(`/api/jobs/${id}`, { token })
      .then(setJob)
      .catch((err) => form.setError(err.message))
  }, [id, token])

  if (!job && !form.error) return <p className="muted">Loading…</p>
  if (!job) return <Message error={form.error} />

  return (
    <section className="stack">
      <p className="eyebrow">{job.department}</p>
      <h1>{job.title}</h1>
      <p>
        {job.location} · {jobTypeLabel(job.job_type)} · Apply by {job.last_date_to_apply}
      </p>
      <h2>Description</h2>
      <p className="prose">{job.description}</p>
      <h2>Requirements</h2>
      <p className="prose">{job.requirements}</p>
      <Message error={form.error} success={form.success} />
      <button
        type="button"
        disabled={form.busy}
        onClick={() =>
          form.run(async () => {
            await api(`/api/jobs/${id}/apply`, { method: 'POST', token })
            await refresh()
            form.setSuccess('Application received. Check My applications and your email.')
          })
        }
      >
        Apply with my current CV
      </button>
    </section>
  )
}

export function CvPage() {
  const { token, profile, refresh } = useAuth()
  const form = useForm()
  const [file, setFile] = useState(null)
  return (
    <section className="stack">
      <h1>My CV</h1>
      <p className="lede">Upload a PDF of 2 MB or less. Applications you already sent keep the CV used at the time.</p>
      {profile?.current_cv ? (
        <p>
          Current file: <strong>{profile.current_cv.original_filename}</strong> ({Math.round(profile.current_cv.file_size_bytes / 1024)} KB)
        </p>
      ) : (
        <p className="muted">No CV uploaded yet.</p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          form.run(async () => {
            if (!file) throw new Error('Choose a PDF file.')
            const data = new FormData()
            data.append('file', file)
            await api('/api/cvs', { method: 'POST', token, form: data })
            await refresh()
            form.setSuccess('CV uploaded.')
          })
        }}
      >
        <Message error={form.error} success={form.success} />
        <Field label="PDF file">
          <input type="file" accept="application/pdf,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Field>
        <button type="submit" disabled={form.busy}>
          Upload CV
        </button>
      </form>
    </section>
  )
}

export function ApplicationsPage() {
  const { token } = useAuth()
  const [rows, setRows] = useState([])
  const form = useForm()
  function load() {
    api('/api/applications/me', { token }).then(setRows).catch((err) => form.setError(err.message))
  }
  useEffect(load, [token])
  return (
    <section>
      <h1>My applications</h1>
      <Message error={form.error} success={form.success} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Stage</th>
              <th>Applied</th>
              <th>Interview</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.job?.title}</td>
                <td>
                  <span className={`pill ${row.stage}`}>{stageLabel(row.stage)}</span>
                </td>
                <td>{formatDate(row.created_at)}</td>
                <td>
                  {row.interview
                    ? `${formatDate(row.interview.starts_at)}${row.interview.location ? ` · ${row.interview.location}` : ''}${row.interview.meeting_link ? ` · ${row.interview.meeting_link}` : ''}`
                    : '—'}
                </td>
                <td>
                  {row.stage !== 'hired' && row.stage !== 'rejected' && row.stage !== 'withdrawn' ? (
                    <button
                      type="button"
                      className="text-btn"
                      onClick={() =>
                        form.run(async () => {
                          await api(`/api/applications/${row.id}/withdraw`, { method: 'POST', token })
                          form.setSuccess('Application withdrawn.')
                          load()
                        })
                      }
                    >
                      Withdraw
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
