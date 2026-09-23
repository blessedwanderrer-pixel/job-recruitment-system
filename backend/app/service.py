from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from . import ai
from .config import settings
from .errors import AppError
from .mailer import Mailer
from .rules import (
    ADMIN,
    CANDIDATE,
    JOB_TYPES,
    RECRUITER,
    ensure_can_advance,
    ensure_can_apply,
    ensure_can_hire,
    ensure_can_reject,
    ensure_can_schedule_interview,
    ensure_can_withdraw,
    ensure_job_accepts_applications,
    job_is_past_last_date,
    recruiter_assigned,
    require_role,
    utcnow,
    validate_cv_file,
)

_log = logging.getLogger(__name__)


class HiringService:
    def __init__(self, store, mailer: Mailer):
        self.store = store
        self.mailer = mailer

    def close_expired_jobs(self) -> int:
        if hasattr(self.store, "close_expired_jobs"):
            return self.store.close_expired_jobs()
        closed = 0
        for job in self.store.list_jobs():
            if job["status"] == "open" and job_is_past_last_date(job):
                self.store.update_job(job["id"], {"status": "closed", "closed_at": utcnow().isoformat()})
                closed += 1
        return closed

    def _job(self, job_id: str) -> dict[str, Any]:
        self.close_expired_jobs()
        job = self.store.get_job(job_id)
        if not job:
            raise AppError("Job not found.", 404)
        return job

    def _application(self, application_id: str) -> dict[str, Any]:
        application = self.store.get_application(application_id)
        if not application:
            raise AppError("Application not found.", 404)
        return application

    def _assert_recruiter_job_access(self, actor: dict[str, Any], job_id: str) -> None:
        if actor["role"] == ADMIN:
            return
        if actor["role"] != RECRUITER:
            raise AppError("You do not have permission to do that.", 403)
        ids = self.store.job_recruiter_ids(job_id)
        if not recruiter_assigned(ids, actor["id"]):
            raise AppError("You do not have permission to do that.", 403)

    def _enrich_application(self, application: dict[str, Any], include_notes: bool, include_candidate: bool) -> dict[str, Any]:
        job = self.store.get_job(application["job_id"])
        cv = self.store.get_cv(application["cv_id"])
        interview = self.store.get_interview(application["id"])
        candidate = self.store.get_profile(application["candidate_id"]) if include_candidate else None
        payload = {
            **application,
            "job": job,
            "cv": {k: v for k, v in (cv or {}).items() if k != "storage_path"} if cv else None,
            "interview": interview,
            "history": self.store.list_stage_events(application["id"]),
        }
        if include_candidate and candidate:
            payload["candidate"] = {
                "id": candidate["id"],
                "full_name": candidate["full_name"],
                "email": candidate["email"],
                "phone": candidate.get("phone"),
            }
        if include_notes:
            payload["notes"] = self.store.list_notes(application["id"])
            payload["ai_summary"] = self._staff_ai_summary(application)
        return payload

    def _staff_ai_summary(self, application: dict[str, Any]) -> dict[str, Any] | None:
        try:
            row = self.store.get_ai_summary(application["id"])
        except Exception:
            row = None
        if not row:
            self._generate_ai_summary(application)
            try:
                row = self.store.get_ai_summary(application["id"])
            except Exception:
                row = None
        return ai.public_staff_summary(row)

    def _generate_ai_summary(self, application: dict[str, Any], job: dict[str, Any] | None = None) -> None:
        job = job or self.store.get_job(application["job_id"])
        try:
            data = self.store.get_cv_bytes(application["cv_id"]) or b""
            text = ai.extract_pdf_text(data)
            summary = ai.build_ai_summary(
                job or {},
                text,
                application["cv_id"],
                force_fail=bool(settings.ats_ai_force_fail),
            )
            self.store.upsert_ai_summary(ai.row_from_summary(application["id"], summary))
        except Exception:
            _log.exception(
                "AI summary generation failed application_id=%s cv_id=%s",
                application.get("id"),
                application.get("cv_id"),
            )
            try:
                self.store.upsert_ai_summary(
                    ai.row_from_summary(application["id"], ai.failed_summary(application.get("cv_id")))
                )
            except Exception:
                _log.exception(
                    "AI summary fallback persist failed application_id=%s cv_id=%s",
                    application.get("id"),
                    application.get("cv_id"),
                )

    def me(self, actor: dict[str, Any]) -> dict[str, Any]:
        profile = dict(actor)
        if actor.get("current_cv_id"):
            profile["current_cv"] = self.store.get_cv(actor["current_cv_id"])
        return profile

    def login(self, email: str, password: str) -> dict[str, Any]:
        profile = self.store.verify_password(email.strip().lower(), password)
        if not profile:
            raise AppError("Invalid email or password.", 401)
        if profile.get("role") == RECRUITER and not profile.get("is_active", True):
            raise AppError("This recruiter account is deactivated.", 403)
        from .supabase_store import current_access_token

        return {"token": current_access_token.get() or profile["id"], "profile": self.me(profile)}

    def set_recruiter_password(self, email: str, token: str, password: str) -> dict[str, Any]:
        if not password or len(password) < 6:
            raise AppError("Password must be at least 6 characters.")
        profile = self.store.set_password(email.strip().lower(), token, password)
        from .supabase_store import current_access_token

        return {"token": current_access_token.get() or profile["id"], "profile": self.me(profile)}

    def register_candidate(self, full_name: str, phone: str, email: str, password: str) -> dict[str, Any]:
        if not full_name.strip() or not phone.strip() or not email.strip() or not password:
            raise AppError("Name, phone number, email, and password are required.")
        existing = self.store.get_profile_by_email(email.strip())
        if existing:
            raise AppError("An account with this email already exists.")
        user = self.store.create_auth_user(
            email=email.strip().lower(),
            password=password,
            app_metadata={"role": CANDIDATE},
            user_metadata={"full_name": full_name.strip(), "phone": phone.strip()},
        )
        profile = {
            "id": user["id"],
            "role": CANDIDATE,
            "full_name": full_name.strip(),
            "phone": phone.strip(),
            "email": email.strip().lower(),
            "is_active": True,
        }
        try:
            return self.store.upsert_profile(profile)
        except AppError:
            return profile

    def list_recruiters(self, actor: dict[str, Any]) -> list[dict[str, Any]]:
        require_role(actor, ADMIN)
        profiles = self.store.list_profiles(RECRUITER)
        counts: dict[str, int] = {}
        for link in self.store.list_job_recruiter_links():
            recruiter_id = link.get("recruiter_id")
            if recruiter_id:
                counts[recruiter_id] = counts.get(recruiter_id, 0) + 1
        return [
            {
                "id": profile["id"],
                "full_name": profile["full_name"],
                "email": profile["email"],
                "role": profile["role"],
                "is_active": profile.get("is_active", True),
                "assigned_job_count": counts.get(profile["id"], 0),
            }
            for profile in profiles
        ]

    def create_recruiter(self, actor: dict[str, Any], full_name: str, email: str) -> dict[str, Any]:
        require_role(actor, ADMIN)
        if not full_name.strip() or not email.strip():
            raise AppError("Name and email are required.")
        if self.store.get_profile_by_email(email.strip()):
            raise AppError("An account with this email already exists.")
        from .links import require_public_email_origin, recruiter_set_password_path

        origin = require_public_email_origin()
        password = f"Tmp-{user_token()}"
        user = self.store.create_auth_user(
            email=email.strip().lower(),
            password=password,
            app_metadata={"role": RECRUITER},
            user_metadata={"full_name": full_name.strip()},
        )
        profile = self.store.upsert_profile(
            {
                "id": user["id"],
                "role": RECRUITER,
                "full_name": full_name.strip(),
                "phone": None,
                "email": email.strip().lower(),
                "is_active": True,
            }
        )
        link = self.store.generate_recovery_link(profile["email"], recruiter_set_password_path(origin))
        self.mailer.send(
            "recruiter_invite",
            profile,
            extra={
                "set_password_link": link,
                "frontend_public_url": origin,
                "full_name": profile["full_name"],
            },
        )
        return {
            "id": profile["id"],
            "full_name": profile["full_name"],
            "email": profile["email"],
            "role": profile["role"],
            "is_active": profile.get("is_active", True),
            "assigned_job_count": 0,
        }

    def deactivate_recruiter(self, actor: dict[str, Any], recruiter_id: str) -> dict[str, Any]:
        require_role(actor, ADMIN)
        if recruiter_id == actor["id"]:
            raise AppError("You cannot deactivate your own account.")
        profile = self.store.get_profile(recruiter_id)
        if not profile or profile["role"] != RECRUITER:
            raise AppError("Recruiter not found.", 404)
        if profile.get("role") == ADMIN:
            raise AppError("Admin accounts cannot be deactivated here.")
        profile["is_active"] = False
        updated = self.store.upsert_profile(profile)
        self.store.unassign_recruiter(recruiter_id)
        assigned = self.store.jobs_for_recruiter(updated["id"])
        return {
            "id": updated["id"],
            "full_name": updated["full_name"],
            "email": updated["email"],
            "role": updated["role"],
            "is_active": updated.get("is_active", False),
            "assigned_job_count": len(assigned),
        }

    def delete_recruiter(self, actor: dict[str, Any], recruiter_id: str) -> dict[str, Any]:
        require_role(actor, ADMIN)
        if recruiter_id == actor["id"]:
            raise AppError("You cannot delete your own admin account.")
        profile = self.store.get_profile(recruiter_id)
        if not profile or profile["role"] != RECRUITER:
            raise AppError("Recruiter not found.", 404)
        if profile.get("role") == ADMIN:
            raise AppError("You cannot delete your own admin account.")
        removed = {
            "id": profile["id"],
            "full_name": profile["full_name"],
            "email": profile["email"],
            "deleted": True,
        }
        self.store.purge_recruiter_account(recruiter_id, profile)
        return removed

    def upload_cv(self, actor: dict[str, Any], filename: str, content_type: str | None, data: bytes) -> dict[str, Any]:
        require_role(actor, CANDIDATE)
        validate_cv_file(filename, content_type, data)
        return self.store.save_cv(actor["id"], filename, data)

    def create_job(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        require_role(actor, ADMIN)
        job_type = payload.get("job_type")
        if job_type not in JOB_TYPES:
            raise AppError("Job type must be full-time, part-time, or internship.")
        try:
            openings = int(payload.get("openings"))
        except (TypeError, ValueError):
            raise AppError("Number of openings must be at least 1.")
        if openings < 1:
            raise AppError("Number of openings must be at least 1.")
        required = ("title", "department", "location", "description", "requirements", "last_date_to_apply")
        for field in required:
            if not str(payload.get(field) or "").strip():
                raise AppError("Please fill in all job fields.")
        return self.store.create_job(
            {
                "title": payload["title"].strip(),
                "department": payload["department"].strip(),
                "location": payload["location"].strip(),
                "job_type": job_type,
                "description": payload["description"].strip(),
                "requirements": payload["requirements"].strip(),
                "last_date_to_apply": payload["last_date_to_apply"],
                "openings": openings,
                "status": "draft",
                "created_by": actor["id"],
            }
        )

    def list_jobs(self, actor: dict[str, Any] | None) -> list[dict[str, Any]]:
        self.close_expired_jobs()
        jobs = self.store.list_jobs()
        if actor is None or actor["role"] == CANDIDATE:
            visible = []
            for job in jobs:
                if job["status"] == "open" and not job_is_past_last_date(job):
                    visible.append(self._public_job(job))
            return visible
        if actor["role"] == RECRUITER:
            assigned = {j["id"] for j in self.store.jobs_for_recruiter(actor["id"])}
            return [self._job_with_recruiters(j) for j in jobs if j["id"] in assigned]
        require_role(actor, ADMIN)
        return [self._job_with_recruiters(j) for j in jobs]

    def get_job(self, actor: dict[str, Any] | None, job_id: str) -> dict[str, Any]:
        job = self._job(job_id)
        if actor is None or actor["role"] == CANDIDATE:
            if job["status"] != "open" or job_is_past_last_date(job):
                raise AppError("Job not found.", 404)
            return self._public_job(job)
        if actor["role"] == RECRUITER:
            self._assert_recruiter_job_access(actor, job_id)
            return self._job_with_recruiters(job)
        require_role(actor, ADMIN)
        return self._job_with_recruiters(job)

    def open_job(self, actor: dict[str, Any], job_id: str, recruiter_ids: list[str] | None) -> dict[str, Any]:
        require_role(actor, ADMIN)
        job = self._job(job_id)
        if job["status"] == "closed":
            raise AppError("A closed job cannot be opened again.")
        if recruiter_ids is not None:
            self._validate_recruiters(recruiter_ids)
            self.store.set_job_recruiters(job_id, recruiter_ids)
        job = self.store.update_job(job_id, {"status": "open"})
        return self._job_with_recruiters(job)

    def close_job(self, actor: dict[str, Any], job_id: str) -> dict[str, Any]:
        require_role(actor, ADMIN)
        job = self._job(job_id)
        if job["status"] == "closed":
            return self._job_with_recruiters(job)
        job = self.store.update_job(job_id, {"status": "closed", "closed_at": utcnow().isoformat()})
        return self._job_with_recruiters(job)

    def assign_recruiters(self, actor: dict[str, Any], job_id: str, recruiter_ids: list[str]) -> dict[str, Any]:
        require_role(actor, ADMIN)
        job = self._job(job_id)
        self._validate_recruiters(recruiter_ids)
        self.store.set_job_recruiters(job["id"], recruiter_ids)
        return self._job_with_recruiters(job)

    def apply(self, actor: dict[str, Any], job_id: str) -> dict[str, Any]:
        require_role(actor, CANDIDATE)
        job = self._job(job_id)
        ensure_job_accepts_applications(job)
        ensure_can_apply(self.store.active_application(actor["id"], job_id))
        if not actor.get("current_cv_id"):
            raise AppError("Upload a PDF CV before you apply.")
        try:
            application = self.store.create_application(
                {
                    "job_id": job_id,
                    "candidate_id": actor["id"],
                    "cv_id": actor["current_cv_id"],
                    "stage": "applied",
                }
            )
        except Exception:
            raise AppError("You already have an active application for this job.")
        self.store.add_stage_event(
            {"application_id": application["id"], "from_stage": None, "to_stage": "applied", "changed_by": actor["id"]}
        )
        self.mailer.send(
            "application_received",
            actor,
            application["id"],
            extra={"job_title": job["title"]},
        )
        self._generate_ai_summary(application, job)
        try:
            return self._enrich_application(application, include_notes=False, include_candidate=False)
        except Exception:
            return {**application, "job": job}

    def my_applications(self, actor: dict[str, Any]) -> list[dict[str, Any]]:
        require_role(actor, CANDIDATE)
        rows = self.store.list_applications(candidate_id=actor["id"])
        return [self._enrich_application(r, include_notes=False, include_candidate=False) for r in rows]

    def withdraw(self, actor: dict[str, Any], application_id: str) -> dict[str, Any]:
        require_role(actor, CANDIDATE)
        application = self._application(application_id)
        if application["candidate_id"] != actor["id"]:
            raise AppError("You do not have permission to do that.", 403)
        ensure_can_withdraw(application)
        updated = self._move(application, "withdrawn", actor["id"])
        return self._enrich_application(updated, include_notes=False, include_candidate=False)

    def list_job_applications(self, actor: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
        require_role(actor, RECRUITER, ADMIN)
        self._assert_recruiter_job_access(actor, job_id)
        self._job(job_id)
        rows = self.store.list_applications(job_id=job_id)
        include_notes = actor["role"] in (RECRUITER, ADMIN)
        return [self._enrich_application(r, include_notes=include_notes, include_candidate=True) for r in rows]

    def get_application(self, actor: dict[str, Any], application_id: str) -> dict[str, Any]:
        application = self._application(application_id)
        if actor["role"] == CANDIDATE:
            if application["candidate_id"] != actor["id"]:
                raise AppError("You do not have permission to do that.", 403)
            return self._enrich_application(application, include_notes=False, include_candidate=False)
        require_role(actor, RECRUITER, ADMIN)
        self._assert_recruiter_job_access(actor, application["job_id"])
        return self._enrich_application(application, include_notes=True, include_candidate=True)

    def application_cv_url(self, actor: dict[str, Any], application_id: str) -> str:
        application = self.get_application(actor, application_id)
        cv = self.store.get_cv(application["cv_id"])
        if not cv:
            raise AppError("CV not found.", 404)
        return self.store.signed_cv_url(cv["storage_path"])

    def retry_ai_summary(self, actor: dict[str, Any], application_id: str) -> dict[str, Any]:
        require_role(actor, RECRUITER, ADMIN)
        application = self._application(application_id)
        self._assert_recruiter_job_access(actor, application["job_id"])
        self._generate_ai_summary(application)
        return self.get_application(actor, application_id)

    def add_note(self, actor: dict[str, Any], application_id: str, body: str) -> dict[str, Any]:
        require_role(actor, RECRUITER)
        if not body.strip():
            raise AppError("Note cannot be empty.")
        application = self._application(application_id)
        self._assert_recruiter_job_access(actor, application["job_id"])
        return self.store.add_note(
            {
                "application_id": application_id,
                "recruiter_id": actor["id"],
                "body": body.strip(),
                "recruiter_name": actor.get("full_name"),
                "recruiter_email": actor.get("email"),
            }
        )

    def advance(self, actor: dict[str, Any], application_id: str, to_stage: str | None = None) -> dict[str, Any]:
        require_role(actor, RECRUITER)
        application = self._application(application_id)
        job = self._job(application["job_id"])
        self._assert_recruiter_job_access(actor, job["id"])
        nxt = ensure_can_advance(application, job, to_stage)
        if nxt == "hired":
            ensure_can_hire(application, job, self.store.hired_count(job["id"]))
        updated = self._move(application, nxt, actor["id"])
        if nxt == "hired":
            self._after_hire(job, actor, updated)
        return self.get_application(actor, updated["id"])

    def reject(self, actor: dict[str, Any], application_id: str) -> dict[str, Any]:
        require_role(actor, RECRUITER)
        application = self._application(application_id)
        job = self._job(application["job_id"])
        self._assert_recruiter_job_access(actor, job["id"])
        ensure_can_reject(application)
        updated = self._move(application, "rejected", actor["id"])
        candidate = self.store.get_profile(updated["candidate_id"])
        if candidate:
            self.mailer.send("rejected", candidate, updated["id"], extra={"job_title": job["title"]})
        return self.get_application(actor, updated["id"])

    def schedule_interview(
        self,
        actor: dict[str, Any],
        application_id: str,
        starts_at: datetime,
        location: str | None,
        meeting_link: str | None,
    ) -> dict[str, Any]:
        require_role(actor, RECRUITER)
        application = self._application(application_id)
        job = self._job(application["job_id"])
        self._assert_recruiter_job_access(actor, job["id"])
        existing = self.store.interviews_for_recruiter(actor["id"])
        ensure_can_schedule_interview(application, job, starts_at, location, meeting_link, existing)
        interview = self.store.create_interview(
            {
                "application_id": application_id,
                "recruiter_id": actor["id"],
                "recruiter_name": actor.get("full_name"),
                "recruiter_email": actor.get("email"),
                "starts_at": starts_at,
                "location": location or None,
                "meeting_link": meeting_link or None,
            }
        )
        updated = self._move(application, "interview", actor["id"])
        candidate = self.store.get_profile(updated["candidate_id"])
        if candidate:
            self.mailer.send(
                "interview_invitation",
                candidate,
                updated["id"],
                extra={
                    "job_title": job["title"],
                    "starts_at": interview["starts_at"] if isinstance(interview["starts_at"], str) else interview["starts_at"].isoformat(),
                    "location": interview.get("location"),
                    "meeting_link": interview.get("meeting_link"),
                },
            )
        return self.get_application(actor, updated["id"])

    def dashboard(self, actor: dict[str, Any]) -> list[dict[str, Any]]:
        require_role(actor, ADMIN)
        self.close_expired_jobs()
        return self.store.dashboard_rows()

    def _move(self, application: dict[str, Any], to_stage: str, actor_id: str) -> dict[str, Any]:
        updated = self.store.update_application(application["id"], {"stage": to_stage})
        changer = self.store.get_profile(actor_id)
        self.store.add_stage_event(
            {
                "application_id": application["id"],
                "from_stage": application["stage"],
                "to_stage": to_stage,
                "changed_by": actor_id,
                "changed_by_name": (changer or {}).get("full_name"),
            }
        )
        return updated

    def _after_hire(self, job: dict[str, Any], actor: dict[str, Any], application: dict[str, Any]) -> None:
        candidate = self.store.get_profile(application["candidate_id"])
        if candidate:
            self.mailer.send("hired", candidate, application["id"], extra={"job_title": job["title"]})
        if self.store.hired_count(job["id"]) >= int(job["openings"]):
            self.store.update_job(job["id"], {"status": "closed", "closed_at": utcnow().isoformat()})

    def _public_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": job["id"],
            "title": job["title"],
            "department": job["department"],
            "location": job["location"],
            "job_type": job["job_type"],
            "description": job["description"],
            "requirements": job["requirements"],
            "last_date_to_apply": job["last_date_to_apply"],
            "openings": job["openings"],
            "status": job["status"],
        }

    def _job_with_recruiters(self, job: dict[str, Any]) -> dict[str, Any]:
        recruiter_ids = self.store.job_recruiter_ids(job["id"])
        recruiters = [self.store.get_profile(rid) for rid in recruiter_ids]
        return {
            **job,
            "recruiter_ids": recruiter_ids,
            "recruiters": [
                {"id": r["id"], "full_name": r["full_name"], "email": r["email"], "is_active": r["is_active"]}
                for r in recruiters
                if r
            ],
        }

    def _validate_recruiters(self, recruiter_ids: list[str]) -> None:
        for rid in recruiter_ids:
            profile = self.store.get_profile(rid)
            if not profile or profile["role"] != RECRUITER:
                raise AppError("One or more recruiters could not be found.")
            if not profile.get("is_active", True):
                raise AppError("A deactivated recruiter cannot be assigned to a job.")


def user_token() -> str:
    import uuid

    return uuid.uuid4().hex[:10]
