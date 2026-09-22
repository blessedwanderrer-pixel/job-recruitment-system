-- AI CV summaries (staff-only SELECT). Candidates may insert/update their own application row so generation can run after apply.

CREATE TABLE IF NOT EXISTS public.application_ai_summaries (
  application_id uuid PRIMARY KEY REFERENCES public.applications(id) ON DELETE CASCADE,
  cv_id uuid NOT NULL REFERENCES public.cv_files(id),
  status text NOT NULL CHECK (status IN ('pending', 'ready', 'failed')),
  generated_by_ai boolean NOT NULL DEFAULT true,
  profile_bullets jsonb NOT NULL DEFAULT '[]'::jsonb,
  requirements_found jsonb NOT NULL DEFAULT '[]'::jsonb,
  requirements_missing jsonb NOT NULL DEFAULT '[]'::jsonb,
  interview_questions jsonb NOT NULL DEFAULT '[]'::jsonb,
  message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.application_ai_summaries ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.ats_can_review_application(p_application_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.ats_is_admin()
    OR EXISTS (
      SELECT 1
      FROM public.applications a
      JOIN public.job_recruiters jr ON jr.job_id = a.job_id
      WHERE a.id = p_application_id
        AND jr.recruiter_id = auth.uid()
    );
$$;

CREATE OR REPLACE FUNCTION public.ats_owns_application(p_application_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.applications a
    WHERE a.id = p_application_id AND a.candidate_id = auth.uid()
  );
$$;

DROP POLICY IF EXISTS application_ai_summaries_select ON public.application_ai_summaries;
CREATE POLICY application_ai_summaries_select
  ON public.application_ai_summaries
  FOR SELECT
  TO authenticated
  USING (public.ats_can_review_application(application_id));

DROP POLICY IF EXISTS application_ai_summaries_insert ON public.application_ai_summaries;
CREATE POLICY application_ai_summaries_insert
  ON public.application_ai_summaries
  FOR INSERT
  TO authenticated
  WITH CHECK (public.ats_can_review_application(application_id));

DROP POLICY IF EXISTS application_ai_summaries_update ON public.application_ai_summaries;
CREATE POLICY application_ai_summaries_update
  ON public.application_ai_summaries
  FOR UPDATE
  TO authenticated
  USING (public.ats_can_review_application(application_id))
  WITH CHECK (public.ats_can_review_application(application_id));

GRANT SELECT, INSERT, UPDATE ON public.application_ai_summaries TO authenticated;
GRANT ALL ON public.application_ai_summaries TO service_role;
GRANT EXECUTE ON FUNCTION public.ats_can_review_application(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ats_owns_application(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ats_is_admin() TO authenticated;
