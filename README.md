# Job Recruitment System

Applicant Tracking System (ATS) for **Nowshera Digital**. Candidates apply to jobs, recruiters move applications through a hiring pipeline, and an admin manages jobs, recruiters, and a hiring dashboard.

Repository: [github.com/blessedwanderrer-pixel/job-recruitment-system](https://github.com/blessedwanderrer-pixel/job-recruitment-system)

---

## Key features

- **Candidate registration and login** - candidates create an account. Admin, recruiter, and candidate each have a dedicated sign-in page (`/admin/login`, `/recruiter/login`, `/candidate/login`). There is also a home chooser at `/login`.
- **Job browsing and applications** - candidates see open jobs and apply with their current CV
- **CV upload and validation** - PDF only, 2 MB or less, validated on the server
- **Candidate application tracking** - candidates view stages and can withdraw (then reapply with a new CV)
- **Recruiter application pipeline** - assigned recruiters review applicants, add private notes, schedule interviews, advance, reject, and hire
- **Admin job and recruiter management** - create jobs (draft), open or close them, assign recruiters, and **add**, **deactivate**, or **delete** recruiter accounts (deletion keeps jobs, applications, CVs, interviews, notes, and stage history)
- **AI CV summaries (staff only)** - after apply, FastAPI builds a short AI-generated summary from the CV attached to that application (3–5 bullets, requirements found/not found, exactly 3 interview questions). Candidates never see it. Failure does not block apply or `application_received` email; recruiters can **Try again**.
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
| `VITE_ALLOWED_HOST` | Optional extra Vite dev hostname (Cloudflare tunnel host, no `https://`) |

**Backend (root `.env`)**

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Same project URL as the frontend |
| `SUPABASE_ANON_KEY` | Anon / publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server only; never expose to the browser) |
| `FRONTEND_URL` | Local frontend origin for CORS (example: `http://127.0.0.1:5173`) |
| `FRONTEND_PUBLIC_URL` | **Public** frontend origin used in recruiter invite emails (https, not localhost). Example: your Cloudflare tunnel URL |
| `N8N_WEBHOOK_URL` | n8n hiring-email webhook URL (leave empty to skip outbound mail) |
| `N8N_INTERNAL_SECRET` | **Required.** Shared secret for `POST /api/internal/close-expired-jobs` |
| `ATS_USE_MEMORY` | `true` uses in-memory storage; `false` uses Supabase |
| `ATS_AI_FORCE_FAIL` | Test-only. `true` makes AI summary generation fail so recruiters see “Summary not available” and can retry. Keep `false` in normal use. |
| `ADMIN_EMAIL` | Seeded admin email (created on backend startup if missing) |
| `ADMIN_PASSWORD` | **Required.** Seeded admin password (environment only) |
| `ADMIN_NAME` | Seeded admin display name |
| `ADMIN_PHONE` | Optional |

If `ADMIN_PASSWORD` or `N8N_INTERNAL_SECRET` is missing or empty, the backend process exits with a clear error. There are no hardcoded secret defaults in application config.

### 4. Supabase

Apply the SQL files in `supabase/migrations/` in order (`001` core schema, `002`/`003` recruiter delete, `004` AI summaries). Create a Storage bucket named **`cvs`** for uploaded PDFs.

### Recruiter management

Admin can:

1. **Add recruiter** — creates the account and sends an invite email with a **set-password** link.
2. **Deactivate recruiter** — they cannot sign in as a recruiter; job assignments are cleared; hiring history stays.
3. **Delete recruiter** — removes the Auth/profile account so the email can be reused. Foreign keys on notes, stage history, interviews, and jobs are set null where needed so historical records remain. Admin cannot deactivate or delete their own account.

Invite emails use **`FRONTEND_PUBLIC_URL`** (never `127.0.0.1` or `localhost`). **`FRONTEND_URL`** remains the local origin for CORS and local UI.

If you develop behind a Cloudflare Quick Tunnel, set **`VITE_ALLOWED_HOST`** to the tunnel hostname (no `https://`) so Vite accepts that Host header. Do not hardcode tunnel hostnames in application code.

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

Production frontend build:

```bash
cd frontend
npm run build
```

The output is `frontend/dist/`. Serve it behind the same origin as `/api`, or set `VITE_API_URL` to the public FastAPI origin before building.

---

## Authentication overview

- Candidates register at `/signup`. Admin and recruiters are created by an admin (invite email + `/set-password`).
- Sign-in uses **Supabase Auth**. The browser holds the session; FastAPI verifies the JWT on each `/api` call (`Authorization: Bearer …`).
- Roles live in `ats_profiles` (`admin`, `recruiter`, `candidate`). The API is the authority: recruiters only see assigned jobs; candidates cannot read notes, AI summaries, or other people’s CVs.
- Set `ATS_USE_MEMORY=false` and `VITE_USE_MEMORY=false` for real Auth and Postgres. Memory mode is for `pytest` only.

---

## ATS workflow

1. Admin creates a **Draft** job, then **Opens** it and assigns recruiters.
2. Candidate uploads a PDF CV (≤ 2 MB) and applies. Stage starts at **Applied**. `application_received` email is recorded once.
3. Assigned recruiter: Applied → Shortlisted → schedule 1-hour interview → Interview → Offer → Hired (or Reject at allowed stages). Stages cannot be skipped.
4. Candidate may **Withdraw** and apply again with a new CV; the old application stays Withdrawn with the old CV.
5. When hired count reaches `openings`, the job **Closes**. Remaining applicants can still be rejected, not hired.
6. Open jobs past `last_date_to_apply` are closed when jobs are listed/loaded, and optionally by n8n calling the internal close endpoint.

---

## API overview

All application routes are under `/api`. JWT required except login, register, set-password, and health.

| Method | Path | Who |
| --- | --- | --- |
| GET | `/health` | Public |
| POST | `/auth/login` `/auth/register` `/auth/set-password` | Public |
| GET | `/me` | Signed-in |
| GET/POST | `/jobs`, `/jobs/{id}/apply` | Candidate (open jobs) |
| POST | `/cvs` | Candidate |
| GET/POST | `/applications/me`, `/applications/{id}/withdraw` | Candidate |
| GET/POST | `/jobs/{id}/applications`, `/applications/{id}/advance`, `/reject`, `/interview`, `/notes`, `/ai-summary/retry` | Assigned recruiter |
| GET/POST/DELETE | `/admin/jobs…`, `/admin/recruiters…`, `/admin/dashboard` | Admin |
| POST | `/internal/close-expired-jobs` | n8n (`X-Internal-Secret`) |

There is **no** `/close-expired` alias. The close endpoint is **`POST /api/internal/close-expired-jobs`**.

---

## Deployment notes

This repository is the source for a FastAPI + Vite + Supabase ATS. A typical production layout:

1. Apply `supabase/migrations/` in order; create the `cvs` storage bucket.
2. Run FastAPI on a **stable public HTTPS** host (not a Quick Tunnel).
3. Build the frontend with the production API origin (or same-origin reverse proxy).
4. Set `FRONTEND_PUBLIC_URL` to the public site used in recruiter invite emails.
5. Point n8n’s hiring webhook at `N8N_WEBHOOK_URL`, and the close-jobs HTTP node at `https://<public-api>/api/internal/close-expired-jobs` with `X-Internal-Secret`.

A Cloudflare Quick Tunnel was used only so **n8n Cloud** could reach a **developer machine**. That hostname is temporary. FastAPI still closes expired jobs when listings are loaded, so hiring rules work without the tunnel.

---

## Testing

From `backend`:

```bash
cd backend
python -m pytest -q
```

Tests set `ATS_USE_MEMORY=true` and required secrets in `backend/tests/conftest.py`. They do not need a live Supabase project or n8n.

Frontend:

```bash
cd frontend
npm run build
npm run lint
```

Optional live QA against real Supabase (creates temporary `prd14-*@example.com` users; does not delete existing data):

```bash
cd backend
python scripts/live_prd14.py
```

`LIVE_START=11` skips cases 1–10 when those already passed.

---

## Security notes

- **Never commit `.env` or `frontend/.env`.** They are listed in `.gitignore`.
- Supply secrets **only** through environment variables (`ADMIN_PASSWORD`, `N8N_INTERNAL_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and similar).
- Do not put real credentials, JWTs, or service-role keys in README, n8n exports, or issues.
- The internal close-jobs endpoint requires header `X-Internal-Secret` matching `N8N_INTERNAL_SECRET`.
- Recruiter notes, AI summaries, and other candidates' CVs / applications are not exposed to candidates.
- AI generation runs on the **backend** only. There is no AI provider API key in the frontend. Keep any provider keys out of git.

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
   - `recruiter_invite` (set-password link built from `FRONTEND_PUBLIC_URL`, not localhost)

If the webhook is unset, the API still records the event in memory/tests without calling n8n.

### Expired jobs

- **Sample workflow:** schedule trigger (`15 0 * * *`) -> `POST /api/internal/close-expired-jobs` with `X-Internal-Secret`. The sample JSON uses `http://127.0.0.1:8000/...` for a local n8n instance. **n8n Cloud cannot use that URL**; replace it with a public FastAPI origin.
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
| Private CV / application access | Candidates cannot read another candidate's application, CV, recruiter notes, or AI summary |
| Dashboard and email dedup | Admin stage counts; one recorded email per event type |
| AI CV summary | Staff-only summary after apply; no scoring or hire/reject advice; Try again does not resend `application_received` |
| Expired-job close via n8n | n8n Cloud -> Cloudflare Quick Tunnel -> local FastAPI -> Supabase (demo tunnel only) |
| Backend tests | `python -m pytest -q` in `backend` (in-memory store; includes PRD cases 1–14 plus recruiter admin tests) |

---

## Reviewer note

This is a hiring ATS for **Nowshera Digital**: candidates apply with a PDF CV; assigned recruiters move applications through Applied → Shortlisted → Interview → Offer → Hired; admin manages jobs and recruiters.

**Completed:** JWT/Supabase Auth and Postgres persistence (not mock mode in normal `.env`); role-separated portals; recruiter add / deactivate / delete (history kept); dashboard counts from the database; CV and application privacy; staff-only AI CV summaries; n8n hiring emails (`application_received`, interview, hired, rejected, recruiter invite).

**Tests:** Backend `pytest` covers the PRD hiring cases in memory. Live hiring cases 1–10 were run against real Supabase. Mobile layout uses wrapping nav, stacking splits, and horizontal table scroll; a 390×844 pass was recorded in earlier QA. This is not a load-test or hosted-production certification.

**Limitation:** n8n Cloud reaching a laptop FastAPI process needs a public URL. A Cloudflare Quick Tunnel was used for demos only. For a lasting deploy, host FastAPI on a stable HTTPS origin and point n8n at that origin.

