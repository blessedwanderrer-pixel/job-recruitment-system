from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Protocol

from .errors import AppError
from .rules import utcnow


def _now_iso() -> str:
    return utcnow().isoformat()


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


class Store(Protocol):
    def get_profile(self, user_id: str) -> dict[str, Any] | None: ...
    def get_profile_by_email(self, email: str) -> dict[str, Any] | None: ...
    def list_profiles(self, role: str | None = None) -> list[dict[str, Any]]: ...
    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]: ...
    def create_auth_user(self, email: str, password: str, app_metadata: dict[str, Any], user_metadata: dict[str, Any], confirm: bool = True) -> dict[str, Any]: ...
    def generate_recovery_link(self, email: str, redirect_to: str) -> str: ...
    def verify_password(self, email: str, password: str) -> dict[str, Any] | None: ...
    def save_cv(self, candidate_id: str, filename: str, data: bytes) -> dict[str, Any]: ...
    def get_cv(self, cv_id: str) -> dict[str, Any] | None: ...
    def signed_cv_url(self, storage_path: str) -> str: ...
    def create_job(self, job: dict[str, Any]) -> dict[str, Any]: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def list_jobs(self) -> list[dict[str, Any]]: ...
    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def set_job_recruiters(self, job_id: str, recruiter_ids: list[str]) -> list[str]: ...
    def job_recruiter_ids(self, job_id: str) -> list[str]: ...
    def list_job_recruiter_links(self) -> list[dict[str, Any]]: ...
    def jobs_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]: ...
    def unassign_recruiter(self, recruiter_id: str) -> int: ...
    def purge_recruiter_account(self, recruiter_id: str, profile: dict[str, Any]) -> None: ...
    def create_application(self, application: dict[str, Any]) -> dict[str, Any]: ...
    def get_application(self, application_id: str) -> dict[str, Any] | None: ...
    def list_applications(self, job_id: str | None = None, candidate_id: str | None = None) -> list[dict[str, Any]]: ...
    def active_application(self, candidate_id: str, job_id: str) -> dict[str, Any] | None: ...
    def update_application(self, application_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def add_stage_event(self, event: dict[str, Any]) -> dict[str, Any]: ...
    def list_stage_events(self, application_id: str) -> list[dict[str, Any]]: ...
    def add_note(self, note: dict[str, Any]) -> dict[str, Any]: ...
    def list_notes(self, application_id: str) -> list[dict[str, Any]]: ...
    def create_interview(self, interview: dict[str, Any]) -> dict[str, Any]: ...
    def get_interview(self, application_id: str) -> dict[str, Any] | None: ...
    def interviews_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]: ...
    def record_email(self, email_type: str, recipient_user_id: str, application_id: str | None) -> bool: ...
    def list_email_deliveries(self) -> list[dict[str, Any]]: ...
    def hired_count(self, job_id: str) -> int: ...
    def dashboard_rows(self) -> list[dict[str, Any]]: ...
    def get_cv_bytes(self, cv_id: str) -> bytes | None: ...
    def get_ai_summary(self, application_id: str) -> dict[str, Any] | None: ...
    def upsert_ai_summary(self, row: dict[str, Any]) -> dict[str, Any]: ...


class MemoryStore:
    def __init__(self):
        self.profiles: dict[str, dict[str, Any]] = {}
        self.passwords: dict[str, str] = {}
        self.cvs: dict[str, dict[str, Any]] = {}
        self.cv_bytes: dict[str, bytes] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_recruiters: dict[str, list[str]] = {}
        self.applications: dict[str, dict[str, Any]] = {}
        self.stage_events: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.interviews: dict[str, dict[str, Any]] = {}
        self.emails: list[dict[str, Any]] = []
        self.recovery_links: dict[str, str] = {}
        self.ai_summaries: dict[str, dict[str, Any]] = {}

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        row = self.profiles.get(user_id)
        return deepcopy(row) if row else None

    def get_profile_by_email(self, email: str) -> dict[str, Any] | None:
        email_l = email.lower()
        for row in self.profiles.values():
            if row["email"].lower() == email_l:
                return deepcopy(row)
        return None

    def list_profiles(self, role: str | None = None) -> list[dict[str, Any]]:
        rows = list(self.profiles.values())
        if role:
            rows = [r for r in rows if r["role"] == role]
        return deepcopy(rows)

    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(profile)
        row.setdefault("is_active", True)
        row.setdefault("phone", None)
        row.setdefault("current_cv_id", None)
        row.setdefault("created_at", _now_iso())
        row["updated_at"] = _now_iso()
        self.profiles[row["id"]] = row
        return deepcopy(row)

    def create_auth_user(self, email: str, password: str, app_metadata: dict[str, Any], user_metadata: dict[str, Any], confirm: bool = True) -> dict[str, Any]:
        existing = self.get_profile_by_email(email)
        if existing:
            raise ValueError("A user with this email already exists.")
        user_id = str(uuid.uuid4())
        self.passwords[user_id] = password
        return {"id": user_id, "email": email, "app_metadata": app_metadata, "user_metadata": user_metadata}

    def verify_password(self, email: str, password: str) -> dict[str, Any] | None:
        profile = self.get_profile_by_email(email)
        if not profile:
            return None
        if self.passwords.get(profile["id"]) != password:
            return None
        return deepcopy(profile)

    def set_password(self, email: str, token: str, password: str) -> dict[str, Any]:
        expected = self.recovery_links.get(email.lower(), "")
        if not expected or token not in expected:
            raise AppError("This set-password link is invalid.")
        profile = self.get_profile_by_email(email)
        if not profile:
            raise AppError("Account not found.", 404)
        self.passwords[profile["id"]] = password
        return deepcopy(profile)

    def generate_recovery_link(self, email: str, redirect_to: str) -> str:
        token = uuid.uuid4().hex
        from .links import encode_set_password_link
        from urllib.parse import urlparse

        parsed = urlparse(redirect_to)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else redirect_to.rsplit("/set-password", 1)[0]
        link = encode_set_password_link(origin, email, token)
        self.recovery_links[email.lower()] = link
        return link

    def save_cv(self, candidate_id: str, filename: str, data: bytes) -> dict[str, Any]:
        cv_id = str(uuid.uuid4())
        path = f"{candidate_id}/{cv_id}.pdf"
        row = {
            "id": cv_id,
            "candidate_id": candidate_id,
            "storage_path": path,
            "original_filename": filename,
            "file_size_bytes": len(data),
            "created_at": _now_iso(),
        }
        self.cvs[cv_id] = row
        self.cv_bytes[cv_id] = data
        profile = self.profiles[candidate_id]
        profile["current_cv_id"] = cv_id
        profile["updated_at"] = _now_iso()
        return deepcopy(row)

    def get_cv(self, cv_id: str) -> dict[str, Any] | None:
        row = self.cvs.get(cv_id)
        return deepcopy(row) if row else None

    def signed_cv_url(self, storage_path: str) -> str:
        return f"memory://{storage_path}"

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(job)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("status", "draft")
        row["last_date_to_apply"] = str(_parse_date(row["last_date_to_apply"]))
        row.setdefault("created_at", _now_iso())
        row["updated_at"] = _now_iso()
        row.setdefault("closed_at", None)
        self.jobs[row["id"]] = row
        self.job_recruiters.setdefault(row["id"], [])
        return deepcopy(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.jobs.get(job_id)
        return deepcopy(row) if row else None

    def list_jobs(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.jobs.values()))

    def close_expired_jobs(self) -> int:
        from .rules import job_is_past_last_date

        closed = 0
        for job in list(self.jobs.values()):
            if job["status"] == "open" and job_is_past_last_date(job):
                job["status"] = "closed"
                job["closed_at"] = _now_iso()
                job["updated_at"] = _now_iso()
                closed += 1
        return closed

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self.jobs[job_id]
        for key, value in fields.items():
            if key == "last_date_to_apply" and value is not None:
                row[key] = str(_parse_date(value))
            else:
                row[key] = value
        row["updated_at"] = _now_iso()
        return deepcopy(row)

    def set_job_recruiters(self, job_id: str, recruiter_ids: list[str]) -> list[str]:
        ids = list(dict.fromkeys(recruiter_ids))
        self.job_recruiters[job_id] = ids
        return list(ids)

    def job_recruiter_ids(self, job_id: str) -> list[str]:
        return list(self.job_recruiters.get(job_id, []))

    def list_job_recruiter_links(self) -> list[dict[str, Any]]:
        return [{"recruiter_id": rid} for recs in self.job_recruiters.values() for rid in recs]

    def jobs_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]:
        ids = [jid for jid, recs in self.job_recruiters.items() if recruiter_id in recs]
        return deepcopy([self.jobs[jid] for jid in ids if jid in self.jobs])

    def unassign_recruiter(self, recruiter_id: str) -> int:
        removed = 0
        for job_id, recs in list(self.job_recruiters.items()):
            if recruiter_id in recs:
                self.job_recruiters[job_id] = [rid for rid in recs if rid != recruiter_id]
                removed += 1
        return removed

    def purge_recruiter_account(self, recruiter_id: str, profile: dict[str, Any]) -> None:
        name = profile.get("full_name")
        email = (profile.get("email") or "").lower()
        for note in self.notes:
            if note.get("recruiter_id") == recruiter_id:
                note["recruiter_name"] = note.get("recruiter_name") or name
                note["recruiter_email"] = note.get("recruiter_email") or email
                note["recruiter_id"] = None
        for interview in self.interviews.values():
            if interview.get("recruiter_id") == recruiter_id:
                interview["recruiter_name"] = interview.get("recruiter_name") or name
                interview["recruiter_email"] = interview.get("recruiter_email") or email
                interview["recruiter_id"] = None
        for event in self.stage_events:
            if event.get("changed_by") == recruiter_id:
                event["changed_by_name"] = event.get("changed_by_name") or name
                event["changed_by"] = None
        for row in self.emails:
            if row.get("recipient_user_id") == recruiter_id:
                row["recipient_user_id"] = None
        self.unassign_recruiter(recruiter_id)
        self.passwords.pop(recruiter_id, None)
        self.profiles.pop(recruiter_id, None)
        if email:
            self.recovery_links.pop(email, None)

    def create_application(self, application: dict[str, Any]) -> dict[str, Any]:
        if self.active_application(application["candidate_id"], application["job_id"]):
            raise ValueError("duplicate")
        row = deepcopy(application)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("stage", "applied")
        row.setdefault("created_at", _now_iso())
        row["updated_at"] = _now_iso()
        self.applications[row["id"]] = row
        return deepcopy(row)

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        row = self.applications.get(application_id)
        return deepcopy(row) if row else None

    def list_applications(self, job_id: str | None = None, candidate_id: str | None = None) -> list[dict[str, Any]]:
        rows = list(self.applications.values())
        if job_id:
            rows = [r for r in rows if r["job_id"] == job_id]
        if candidate_id:
            rows = [r for r in rows if r["candidate_id"] == candidate_id]
        return deepcopy(sorted(rows, key=lambda r: r["created_at"], reverse=True))

    def active_application(self, candidate_id: str, job_id: str) -> dict[str, Any] | None:
        for row in self.applications.values():
            if row["candidate_id"] == candidate_id and row["job_id"] == job_id and row["stage"] != "withdrawn":
                return deepcopy(row)
        return None

    def update_application(self, application_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self.applications[application_id]
        row.update(fields)
        row["updated_at"] = _now_iso()
        return deepcopy(row)

    def add_stage_event(self, event: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(event)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", _now_iso())
        self.stage_events.append(row)
        return deepcopy(row)

    def list_stage_events(self, application_id: str) -> list[dict[str, Any]]:
        rows = [e for e in self.stage_events if e["application_id"] == application_id]
        return deepcopy(sorted(rows, key=lambda r: r["created_at"]))

    def add_note(self, note: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(note)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", _now_iso())
        self.notes.append(row)
        return deepcopy(row)

    def list_notes(self, application_id: str) -> list[dict[str, Any]]:
        return deepcopy([n for n in self.notes if n["application_id"] == application_id])

    def create_interview(self, interview: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(interview)
        row.setdefault("id", str(uuid.uuid4()))
        starts = row["starts_at"]
        if isinstance(starts, datetime):
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=timezone.utc)
            row["starts_at"] = starts.isoformat()
        row.setdefault("created_at", _now_iso())
        self.interviews[row["application_id"]] = row
        return deepcopy(row)

    def get_interview(self, application_id: str) -> dict[str, Any] | None:
        row = self.interviews.get(application_id)
        return deepcopy(row) if row else None

    def interviews_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]:
        rows = []
        for row in self.interviews.values():
            if row["recruiter_id"] == recruiter_id:
                item = deepcopy(row)
                if isinstance(item["starts_at"], str):
                    item["starts_at"] = datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00"))
                rows.append(item)
        return rows

    def record_email(self, email_type: str, recipient_user_id: str, application_id: str | None) -> bool:
        for row in self.emails:
            if application_id and row.get("application_id") == application_id and row["email_type"] == email_type:
                return False
            if email_type == "recruiter_invite" and row["email_type"] == "recruiter_invite" and row["recipient_user_id"] == recipient_user_id:
                return False
        self.emails.append(
            {
                "id": str(uuid.uuid4()),
                "email_type": email_type,
                "application_id": application_id,
                "recipient_user_id": recipient_user_id,
                "created_at": _now_iso(),
            }
        )
        return True

    def delete_email_record(self, email_type: str, recipient_user_id: str, application_id: str | None) -> None:
        self.emails = [
            row
            for row in self.emails
            if not (
                row["email_type"] == email_type
                and row["recipient_user_id"] == recipient_user_id
                and row.get("application_id") == application_id
            )
        ]

    def list_email_deliveries(self) -> list[dict[str, Any]]:
        return deepcopy(self.emails)

    def hired_count(self, job_id: str) -> int:
        return sum(1 for a in self.applications.values() if a["job_id"] == job_id and a["stage"] == "hired")

    def dashboard_rows(self) -> list[dict[str, Any]]:
        from collections import Counter

        rows = []
        for job in self.jobs.values():
            counts: Counter[str] = Counter()
            for app in self.applications.values():
                if app["job_id"] == job["id"]:
                    counts[app["stage"]] += 1
            rows.append(
                {
                    "job": deepcopy(job),
                    "total_applied": sum(counts.values()),
                    "stages": {
                        "applied": counts["applied"],
                        "shortlisted": counts["shortlisted"],
                        "interview": counts["interview"],
                        "offer": counts["offer"],
                        "hired": counts["hired"],
                        "rejected": counts["rejected"],
                        "withdrawn": counts["withdrawn"],
                    },
                }
            )
        rows.sort(key=lambda r: r["job"]["created_at"], reverse=True)
        return rows

    def get_cv_bytes(self, cv_id: str) -> bytes | None:
        return self.cv_bytes.get(cv_id)

    def get_ai_summary(self, application_id: str) -> dict[str, Any] | None:
        row = self.ai_summaries.get(application_id)
        return deepcopy(row) if row else None

    def upsert_ai_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(row)
        stored["updated_at"] = _now_iso()
        stored.setdefault("created_at", _now_iso())
        stored.setdefault("generated_by_ai", True)
        self.ai_summaries[row["application_id"]] = stored
        return deepcopy(stored)
