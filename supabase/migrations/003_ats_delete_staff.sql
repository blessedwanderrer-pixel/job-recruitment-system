-- Admin-only recruiter deletion that works without a service-role key in the API.
-- Mirrors ats_create_staff: SECURITY DEFINER so Auth users can be removed while
-- snapshots keep notes, interviews, and stage history.

CREATE OR REPLACE FUNCTION public.ats_delete_staff(p_id uuid)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'auth'
AS $function$
DECLARE rec public.ats_profiles%ROWTYPE;
BEGIN
  IF NOT public.ats_is_admin() AND coalesce(auth.role(), '') <> 'service_role' THEN
    RAISE EXCEPTION 'not allowed';
  END IF;
  IF p_id = auth.uid() THEN
    RAISE EXCEPTION 'You cannot delete your own admin account.';
  END IF;
  SELECT * INTO rec FROM public.ats_profiles WHERE id = p_id;
  IF rec.id IS NULL OR rec.role <> 'recruiter' THEN
    RAISE EXCEPTION 'Recruiter not found.';
  END IF;

  UPDATE public.recruiter_notes
    SET recruiter_name = COALESCE(recruiter_name, rec.full_name),
        recruiter_email = COALESCE(recruiter_email, rec.email)
    WHERE recruiter_id = p_id;

  UPDATE public.interviews
    SET recruiter_name = COALESCE(recruiter_name, rec.full_name),
        recruiter_email = COALESCE(recruiter_email, rec.email)
    WHERE recruiter_id = p_id;

  UPDATE public.application_stage_events
    SET changed_by_name = COALESCE(changed_by_name, rec.full_name)
    WHERE changed_by = p_id;

  DELETE FROM public.job_recruiters WHERE recruiter_id = p_id;
  DELETE FROM auth.identities WHERE user_id = p_id;
  DELETE FROM auth.users WHERE id = p_id;

  RETURN json_build_object('id', rec.id, 'email', rec.email, 'full_name', rec.full_name, 'deleted', true);
END;
$function$;

GRANT EXECUTE ON FUNCTION public.ats_delete_staff(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ats_delete_staff(uuid) TO service_role;
