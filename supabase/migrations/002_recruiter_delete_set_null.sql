-- Safe recruiter deletion: keep hiring history when a recruiter Auth/profile is removed.
-- Historical rows snapshot recruiter identity, then FKs SET NULL instead of CASCADE.

ALTER TABLE public.recruiter_notes
  ADD COLUMN IF NOT EXISTS recruiter_name text,
  ADD COLUMN IF NOT EXISTS recruiter_email text;

ALTER TABLE public.interviews
  ADD COLUMN IF NOT EXISTS recruiter_name text,
  ADD COLUMN IF NOT EXISTS recruiter_email text;

ALTER TABLE public.application_stage_events
  ADD COLUMN IF NOT EXISTS changed_by_name text;

UPDATE public.recruiter_notes n
SET recruiter_name = COALESCE(n.recruiter_name, p.full_name),
    recruiter_email = COALESCE(n.recruiter_email, p.email)
FROM public.ats_profiles p
WHERE n.recruiter_id = p.id;

UPDATE public.interviews i
SET recruiter_name = COALESCE(i.recruiter_name, p.full_name),
    recruiter_email = COALESCE(i.recruiter_email, p.email)
FROM public.ats_profiles p
WHERE i.recruiter_id = p.id;

UPDATE public.application_stage_events e
SET changed_by_name = COALESCE(e.changed_by_name, p.full_name)
FROM public.ats_profiles p
WHERE e.changed_by = p.id;

ALTER TABLE public.recruiter_notes ALTER COLUMN recruiter_id DROP NOT NULL;
ALTER TABLE public.recruiter_notes DROP CONSTRAINT IF EXISTS recruiter_notes_recruiter_id_fkey;
ALTER TABLE public.recruiter_notes
  ADD CONSTRAINT recruiter_notes_recruiter_id_fkey
  FOREIGN KEY (recruiter_id) REFERENCES public.ats_profiles(id) ON DELETE SET NULL;

ALTER TABLE public.interviews ALTER COLUMN recruiter_id DROP NOT NULL;
ALTER TABLE public.interviews DROP CONSTRAINT IF EXISTS interviews_recruiter_id_fkey;
ALTER TABLE public.interviews
  ADD CONSTRAINT interviews_recruiter_id_fkey
  FOREIGN KEY (recruiter_id) REFERENCES public.ats_profiles(id) ON DELETE SET NULL;

ALTER TABLE public.application_stage_events DROP CONSTRAINT IF EXISTS application_stage_events_changed_by_fkey;
ALTER TABLE public.application_stage_events
  ADD CONSTRAINT application_stage_events_changed_by_fkey
  FOREIGN KEY (changed_by) REFERENCES public.ats_profiles(id) ON DELETE SET NULL;

ALTER TABLE public.email_deliveries ALTER COLUMN recipient_user_id DROP NOT NULL;
ALTER TABLE public.email_deliveries DROP CONSTRAINT IF EXISTS email_deliveries_recipient_user_id_fkey;
ALTER TABLE public.email_deliveries
  ADD CONSTRAINT email_deliveries_recipient_user_id_fkey
  FOREIGN KEY (recipient_user_id) REFERENCES public.ats_profiles(id) ON DELETE SET NULL;
