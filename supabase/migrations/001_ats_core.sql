-- ATS core schema (additive). Does not alter event-management tables.
-- Applied to the linked Supabase project as migration ats_core_schema.

CREATE TABLE IF NOT EXISTS public.ats_profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('candidate', 'recruiter', 'admin')),
  full_name text NOT NULL,
  phone text,
  email text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  current_cv_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.cv_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.ats_profiles(id) ON DELETE CASCADE,
  storage_path text NOT NULL,
  original_filename text NOT NULL,
  file_size_bytes integer NOT NULL CHECK (file_size_bytes > 0 AND file_size_bytes <= 2097152),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  department text NOT NULL,
  location text NOT NULL,
  job_type text NOT NULL CHECK (job_type IN ('full_time', 'part_time', 'internship')),
  description text NOT NULL,
  requirements text NOT NULL,
  last_date_to_apply date NOT NULL,
  openings integer NOT NULL CHECK (openings > 0),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
  created_by uuid NOT NULL REFERENCES public.ats_profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.job_recruiters (
  job_id uuid NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  recruiter_id uuid NOT NULL REFERENCES public.ats_profiles(id) ON DELETE CASCADE,
  assigned_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (job_id, recruiter_id)
);

CREATE TABLE IF NOT EXISTS public.applications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  candidate_id uuid NOT NULL REFERENCES public.ats_profiles(id) ON DELETE CASCADE,
  cv_id uuid NOT NULL REFERENCES public.cv_files(id),
  stage text NOT NULL DEFAULT 'applied' CHECK (stage IN (
    'applied', 'shortlisted', 'interview', 'offer', 'hired', 'rejected', 'withdrawn'
  )),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_application_per_job
  ON public.applications (candidate_id, job_id)
  WHERE stage <> 'withdrawn';

CREATE TABLE IF NOT EXISTS public.application_stage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
  from_stage text,
  to_stage text NOT NULL,
  changed_by uuid REFERENCES public.ats_profiles(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.recruiter_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
  recruiter_id uuid NOT NULL REFERENCES public.ats_profiles(id),
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.interviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL UNIQUE REFERENCES public.applications(id) ON DELETE CASCADE,
  recruiter_id uuid NOT NULL REFERENCES public.ats_profiles(id),
  starts_at timestamptz NOT NULL,
  location text,
  meeting_link text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT interviews_place_or_link CHECK (location IS NOT NULL OR meeting_link IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS public.email_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_type text NOT NULL CHECK (email_type IN (
    'recruiter_invite', 'application_received', 'interview_invitation', 'hired', 'rejected'
  )),
  application_id uuid REFERENCES public.applications(id) ON DELETE SET NULL,
  recipient_user_id uuid NOT NULL REFERENCES public.ats_profiles(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
