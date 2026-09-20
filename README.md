# Job Recruitment System

Applicant Tracking System (ATS) for **Nowshera Digital**. Candidates apply to jobs, recruiters move applications through a hiring pipeline, and an admin manages jobs, recruiters, and a hiring dashboard.

Repository: [github.com/blessedwanderrer-pixel/job-recruitment-system](https://github.com/blessedwanderrer-pixel/job-recruitment-system)

---

## Key features

- **Candidate registration and login** - candidates create an account; candidates, recruiters, and admin share one sign-in page
- **Job browsing and applications** - candidates see open jobs and apply with their current CV
- **CV upload and validation** - PDF only, 2 MB or less, validated on the server
- **Candidate application tracking** - candidates view stages and can withdraw (then reapply with a new CV)
- **Recruiter application pipeline** - assigned recruiters review applicants, add private notes, schedule interviews, advance, reject, and hire
- **Admin job management** - create jobs (draft), open or close them, assign recruiters, and manage recruiter accounts
- **Hiring workflow** - stages: Applied -> Shortlisted -> Interview -> Offer -> Hired (plus Rejected and Withdrawn). Stages cannot be skipped; interview is scheduled from Shortlisted
- **Role-based access control** - candidate, recruiter, and admin permissions are enforced in the FastAPI API
- **Supabase database and authentication** - PostgreSQL tables, Auth users, and CV storage (`cvs` bucket)
- **Email notifications** - FastAPI records each send and posts to an n8n webhook (application received, interview invitation, hired, rejected, recruiter invite)
- **n8n automation** - hiring emails plus a scheduled close of expired jobs
- **Automatic closing of expired jobs** - open jobs past `last_date_to_apply` are closed (also when openings are filled)
- **Mobile-friendly UI** - responsive layout for smaller screens

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, React Router |
| Backend | FastAPI, Python |
| Data and auth | Supabase (PostgreSQL, Auth, Storage) |
| Automation | n8n (webhook emails, scheduled job close) |

---

## Project structure

```text
.
|-- backend/                 # FastAPI app and pytest suite
|   |-- app/                 # config, routes, hiring rules, stores, mailer
|   `-- tests/               # PRD-style API tests (in-memory store)
|-- frontend/                # React + Vite UI
|   `-- src/pages/           # candidate, recruiter, admin screens
|-- n8n/
|   |-- hiring-emails.json   # webhook -> SMTP by email type
|   `-- close-expired-jobs.json
|-- supabase/migrations/     # ATS schema (additive SQL)
|-- .env.example             # placeholder environment variables
`-- .gitignore
```

---

## Local setup

### Prerequisites

- Python 3 (with `pip`)
- Node.js and npm
- A Supabase project (unless you only run the in-memory backend tests)
- An n8n instance if you want live email and scheduled job-close (optional for UI-only local work)

### 1. Clone

```bash
git clone https://github.com/blessedwanderrer-pixel/job-recruitment-system.git
cd job-recruitment-system
```

### 2. Environment files

Copy `.env.example` to `.env` in the **repository root**. The backend loads that file.

Copy the `VITE_*` values into `frontend/.env` as well (Vite does not read the root `.env`).

Do not commit `.env` or `frontend/.env`.

### 3. Environment variables

Use placeholders from `.env.example`. Never put real passwords, service-role keys, or internal secrets in git.

**Frontend (`frontend/.env`)**

| Variable | Purpose |
| --- | --- |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Publishable / anon key |
| `VITE_API_URL` | Backend origin (default in example: `http://127.0.0.1:8000`) |
| `VITE_USE_MEMORY` | `true` only for in-memory API login; use `false` with Supabase |

**Backend (root `.env`)**

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Same project URL as the frontend |
| `SUPABASE_ANON_KEY` | Anon / publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server only; never expose to the browser) |
| `FRONTEND_URL` | CORS / recruiter set-password links (example: `http://127.0.0.1:5173`) |
| `N8N_WEBHOOK_URL` | n8n hiring-email webhook URL (leave empty to skip outbound mail) |
| `N8N_INTERNAL_SECRET` | **Required.** Shared secret for `POST /api/internal/close-expired-jobs` |
| `ATS_USE_MEMORY` | `true` uses in-memory storage; `false` uses Supabase |
| `ADMIN_EMAIL` | Seeded admin email (created on backend startup if missing) |
| `ADMIN_PASSWORD` | **Required.** Seeded admin password (environment only) |
| `ADMIN_NAME` | Seeded admin display name |
| `ADMIN_PHONE` | Optional |

If `ADMIN_PASSWORD` or `N8N_INTERNAL_SECRET` is missing or empty, the backend process exits with a clear error. There are no hardcoded secret defaults in application config.

### 4. Supabase

Apply `supabase/migrations/001_ats_core.sql` to the project (profiles, jobs, applications, CVs, interviews, notes, email log, and related RPCs). Create a Storage bucket named **`cvs`** for uploaded PDFs.

---

## Run the backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/api/health`

On startup, if the admin profile does not exist, the backend seeds it from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

---

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on port **5173** and proxies `/api` to `http://127.0.0.1:8000`. Open `http://127.0.0.1:5173`.

---

## Testing

From `backend`:

```bash
cd backend
python -m pytest -q
```

Tests set `ATS_USE_MEMORY=true` and required secrets in `backend/tests/conftest.py`. They do not need a live Supabase project or n8n.

---

## Security notes

- **Never commit `.env` or `frontend/.env`.** They are listed in `.gitignore`.
- Supply secrets **only** through environment variables (`ADMIN_PASSWORD`, `N8N_INTERNAL_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and similar).
- Do not put real credentials, JWTs, or service-role keys in README, n8n exports, or issues.
- The internal close-jobs endpoint requires header `X-Internal-Secret` matching `N8N_INTERNAL_SECRET`.
- Recruiter notes and other candidates' CVs / applications are not exposed to candidates.

---

## n8n automation

Workflow JSON lives in `n8n/`. Import into n8n, attach SMTP (and the internal secret) in the n8n UI - do not commit real credentials.

### Hiring emails

1. FastAPI `Mailer` writes an `email_deliveries` row (so the same event is not sent twice).
2. It `POST`s JSON to `N8N_WEBHOOK_URL` (path `ats-emails` in the sample workflow).
3. n8n switches on `type` and sends SMTP mail:
   - `application_received`
   - `interview_invitation`
   - `hired`
   - `rejected`
   - `recruiter_invite` (set-password link)

If the webhook is unset, the API still records the event in memory/tests without calling n8n.

### Expired jobs

- **Sample workflow:** schedule trigger (`15 0 * * *`) -> `POST /api/internal/close-expired-jobs` with `X-Internal-Secret`.
- The API closes open jobs whose last apply date has passed (and related hiring rules close a job when openings are filled).
- FastAPI also closes expired jobs when jobs are listed or loaded, so dates are enforced even if the scheduler has not run yet.

### Local n8n Cloud connectivity

n8n Cloud cannot call `http://127.0.0.1:8000` on a developer machine. For local demos, a **Cloudflare Quick Tunnel** was used so the path was:

**n8n Cloud -> Cloudflare Quick Tunnel -> local FastAPI -> Supabase** (expired-job close).

That tunnel is a **development/demo setup**, not a permanent production URL. For production, point n8n at a stable, authenticated public API host.

---

## Testing and QA summary

Verified against the current codebase (backend pytest plus the hiring and n8n flows described above). This is not a claim of exhaustive production load testing.

| Area | What was verified |
| --- | --- |
| Candidate application | Apply with a CV; application-received email event |
| Job creation and hiring | Draft -> open -> pipeline through to hired, with stage history |
| Duplicate applications | Second active application for the same job is rejected |
| Openings-based auto-close | Job closes when hired count reaches openings; further applies/hires blocked |
| Closed / past-date jobs | Closed and past `last_date_to_apply` jobs do not accept applications |
| Withdraw and reapply | Withdraw, then apply again with a different CV; old application stays withdrawn |
| CV validation | Non-PDF and over-2 MB uploads rejected |
| Interview rules | No past times; no overlapping 1-hour slots for the same recruiter |
| Role restrictions | Candidates and unassigned recruiters cannot advance another person's application |
| Private CV / application access | Candidates cannot read another candidate's application, CV, or recruiter notes |
| Dashboard and email dedup | Admin stage counts; one recorded email per event type |
| Expired-job close via n8n | n8n Cloud -> Cloudflare Quick Tunnel -> local FastAPI -> Supabase (demo tunnel only) |
| Backend tests | `python -m pytest -q` in `backend`: **10 passed** |
