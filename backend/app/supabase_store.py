from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

import httpx

from .errors import AppError

current_access_token: ContextVar[str | None] = ContextVar("current_access_token", default=None)


class SupabaseStore:
    def __init__(self, url: str, anon_key: str, service_role_key: str = ""):
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.service_key = service_role_key
        self._request_token: str | None = None
        self.rest = f"{self.url}/rest/v1"
        self.auth = f"{self.url}/auth/v1"
        self.storage = f"{self.url}/storage/v1"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0)

    def authed(self, token: str) -> "SupabaseStore":
        clone = SupabaseStore(self.url, self.anon_key, self.service_key)
        clone._request_token = token
        return clone

    def _headers(self) -> dict[str, str]:
        token = self._request_token or current_access_token.get()
        api_key = self.service_key or self.anon_key
        bearer = self.service_key or token or self.anon_key
        return {
            "apikey": api_key,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        }

    def _anon_headers(self) -> dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }

    def _rest(self, method: str, path: str, **kwargs) -> Any:
        headers = self._headers()
        headers.update(kwargs.pop("headers", {}))
        with self._client() as client:
            response = client.request(method, f"{self.rest}/{path}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise AppError(self._pretty_error(response), response.status_code if response.status_code < 500 else 400)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        return self._rest("POST", f"rpc/{name}", json=payload or {})

    def _pretty_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
            msg = payload.get("message") or payload.get("error_description") or payload.get("error") or payload.get("msg") or str(payload)
            text = str(msg)
            if "one_active_application_per_job" in text:
                return "You already have an active application for this job."
            if "one_email_per_application_type" in text or "one_recruiter_invite" in text:
                return "This email was already sent."
            if "invalid token" in text.lower():
                return "This set-password link is invalid."
            if "not allowed" in text.lower():
                return "You do not have permission to do that."
            return text
        except Exception:
            return response.text or "The request could not be completed."

    def close_expired_jobs(self) -> int:
        result = self._rpc("ats_close_expired_jobs")
        if isinstance(result, int):
            return result
        if isinstance(result, list) and result:
            value = result[0]
            if isinstance(value, dict):
                return int(next(iter(value.values()), 0) or 0)
            return int(value or 0)
        return int(result or 0)

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "ats_profiles", params={"id": f"eq.{user_id}", "select": "*"})
        return rows[0] if rows else None

    def get_profile_by_email(self, email: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "ats_profiles", params={"email": f"eq.{email.lower()}", "select": "*"})
        return rows[0] if rows else None

    def list_profiles(self, role: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.desc"}
        if role:
            params["role"] = f"eq.{role}"
        return self._rest("GET", "ats_profiles", params=params) or []

    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        rows = self._rest(
            "POST",
            "ats_profiles",
            json=profile,
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        return rows[0]

    def create_auth_user(self, email: str, password: str, app_metadata: dict[str, Any], user_metadata: dict[str, Any], confirm: bool = True) -> dict[str, Any]:
        role = app_metadata.get("role") or "candidate"
        if role in ("recruiter", "admin"):
            uid = self._rpc(
                "ats_create_staff",
                {
                    "p_email": email.lower(),
                    "p_full_name": user_metadata.get("full_name") or email,
                    "p_role": role,
                    "p_password": password,
                },
            )
            if isinstance(uid, list):
                uid = uid[0]
            if isinstance(uid, dict):
                uid = uid.get("ats_create_staff") or uid.get("id")
            return {"id": str(uid), "email": email.lower(), "app_metadata": app_metadata, "user_metadata": user_metadata}

        with self._client() as client:
            response = client.post(
                f"{self.auth}/signup",
                headers=self._anon_headers(),
                json={
                    "email": email.lower(),
                    "password": password,
                    "data": user_metadata,
                },
            )
        if response.status_code >= 400:
            text = self._pretty_error(response).lower()
            if "already" in text or "registered" in text or "exists" in text:
                raise AppError("An account with this email already exists.")
            raise AppError(self._pretty_error(response), 400)
        data = response.json()
        user = data.get("user") or data
        access = data.get("access_token") or (data.get("session") or {}).get("access_token")
        if access:
            current_access_token.set(access)
        uid = user.get("id")
        if not uid:
            raise AppError("The account could not be created.")
        return {"id": uid, "email": user.get("email", email.lower()), "app_metadata": app_metadata, "user_metadata": user_metadata}

    def verify_password(self, email: str, password: str) -> dict[str, Any] | None:
        with self._client() as client:
            response = client.post(
                f"{self.auth}/token?grant_type=password",
                headers=self._anon_headers(),
                json={"email": email.lower(), "password": password},
            )
        if response.status_code >= 400:
            return None
        data = response.json()
        access = data.get("access_token")
        user = data.get("user") or {}
        if access:
            current_access_token.set(access)
        uid = user.get("id")
        if not uid:
            return None
        return self.get_profile(uid)

    def generate_recovery_link(self, email: str, redirect_to: str) -> str:
        token = uuid.uuid4().hex
        self._rest(
            "POST",
            "ats_invite_tokens",
            json={"email": email.lower(), "token": token},
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        joiner = "&" if "?" in redirect_to else "?"
        return f"{redirect_to}{joiner}email={email.lower()}&token={token}"

    def set_password(self, email: str, token: str, password: str) -> dict[str, Any]:
        try:
            self._rpc(
                "ats_set_password",
                {"p_email": email.lower(), "p_token": token, "p_password": password},
            )
        except AppError as exc:
            if "invalid" in exc.message.lower():
                raise AppError("This set-password link is invalid.")
            raise
        profile = self.verify_password(email.lower(), password)
        if not profile:
            raise AppError("Password saved. Sign in with your new password.")
        return profile

    def save_cv(self, candidate_id: str, filename: str, data: bytes) -> dict[str, Any]:
        cv_id = str(uuid.uuid4())
        path = f"{candidate_id}/{cv_id}.pdf"
        headers = self._headers()
        headers.pop("Content-Type", None)
        headers["Content-Type"] = "application/pdf"
        headers["x-upsert"] = "false"
        with self._client() as client:
            upload = client.post(
                f"{self.storage}/object/cvs/{path}",
                headers=headers,
                content=data,
            )
        if upload.status_code >= 400:
            raise AppError("The CV could not be stored. Please try again.")
        rows = self._rest(
            "POST",
            "cv_files",
            json={
                "id": cv_id,
                "candidate_id": candidate_id,
                "storage_path": path,
                "original_filename": filename,
                "file_size_bytes": len(data),
            },
            headers={"Prefer": "return=representation"},
        )
        row = rows[0]
        self._rest(
            "PATCH",
            "ats_profiles",
            params={"id": f"eq.{candidate_id}"},
            json={"current_cv_id": cv_id, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        return row

    def get_cv(self, cv_id: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "cv_files", params={"id": f"eq.{cv_id}", "select": "*"})
        return rows[0] if rows else None

    def signed_cv_url(self, storage_path: str) -> str:
        with self._client() as client:
            response = client.post(
                f"{self.storage}/object/sign/cvs/{storage_path}",
                headers=self._headers(),
                json={"expiresIn": 120},
            )
        if response.status_code >= 400:
            raise AppError("The CV could not be opened.")
        payload = response.json()
        signed = payload.get("signedURL") or payload.get("url")
        if not signed:
            raise AppError("The CV could not be opened.")
        if signed.startswith("http"):
            return signed
        return f"{self.storage}{signed}"

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = dict(job)
        payload.pop("id", None)
        rows = self._rest("POST", "jobs", json=payload, headers={"Prefer": "return=representation"})
        return rows[0]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "jobs", params={"id": f"eq.{job_id}", "select": "*"})
        return rows[0] if rows else None

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._rest("GET", "jobs", params={"select": "*", "order": "created_at.desc"}) or []

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        payload = dict(fields)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        rows = self._rest("PATCH", "jobs", params={"id": f"eq.{job_id}"}, json=payload, headers={"Prefer": "return=representation"})
        return rows[0]

    def set_job_recruiters(self, job_id: str, recruiter_ids: list[str]) -> list[str]:
        self._rest("DELETE", "job_recruiters", params={"job_id": f"eq.{job_id}"})
        ids = list(dict.fromkeys(recruiter_ids))
        if ids:
            self._rest("POST", "job_recruiters", json=[{"job_id": job_id, "recruiter_id": rid} for rid in ids])
        return ids

    def job_recruiter_ids(self, job_id: str) -> list[str]:
        rows = self._rest("GET", "job_recruiters", params={"job_id": f"eq.{job_id}", "select": "recruiter_id"}) or []
        return [r["recruiter_id"] for r in rows]

    def jobs_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]:
        links = self._rest("GET", "job_recruiters", params={"recruiter_id": f"eq.{recruiter_id}", "select": "job_id"}) or []
        job_ids = [l["job_id"] for l in links]
        if not job_ids:
            return []
        jobs = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                jobs.append(job)
        return jobs

    def create_application(self, application: dict[str, Any]) -> dict[str, Any]:
        payload = dict(application)
        payload.pop("id", None)
        rows = self._rest("POST", "applications", json=payload, headers={"Prefer": "return=representation"})
        return rows[0]

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "applications", params={"id": f"eq.{application_id}", "select": "*"})
        return rows[0] if rows else None

    def list_applications(self, job_id: str | None = None, candidate_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.desc"}
        if job_id:
            params["job_id"] = f"eq.{job_id}"
        if candidate_id:
            params["candidate_id"] = f"eq.{candidate_id}"
        return self._rest("GET", "applications", params=params) or []

    def active_application(self, candidate_id: str, job_id: str) -> dict[str, Any] | None:
        rows = self._rest(
            "GET",
            "applications",
            params={
                "candidate_id": f"eq.{candidate_id}",
                "job_id": f"eq.{job_id}",
                "stage": "neq.withdrawn",
                "select": "*",
            },
        ) or []
        return rows[0] if rows else None

    def update_application(self, application_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        payload = dict(fields)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        rows = self._rest(
            "PATCH",
            "applications",
            params={"id": f"eq.{application_id}"},
            json=payload,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def add_stage_event(self, event: dict[str, Any]) -> dict[str, Any]:
        rows = self._rest("POST", "application_stage_events", json=event, headers={"Prefer": "return=representation"})
        return rows[0]

    def list_stage_events(self, application_id: str) -> list[dict[str, Any]]:
        return self._rest(
            "GET",
            "application_stage_events",
            params={"application_id": f"eq.{application_id}", "select": "*", "order": "created_at.asc"},
        ) or []

    def add_note(self, note: dict[str, Any]) -> dict[str, Any]:
        rows = self._rest("POST", "recruiter_notes", json=note, headers={"Prefer": "return=representation"})
        return rows[0]

    def list_notes(self, application_id: str) -> list[dict[str, Any]]:
        return self._rest(
            "GET",
            "recruiter_notes",
            params={"application_id": f"eq.{application_id}", "select": "*", "order": "created_at.asc"},
        ) or []

    def create_interview(self, interview: dict[str, Any]) -> dict[str, Any]:
        payload = dict(interview)
        starts = payload["starts_at"]
        if isinstance(starts, datetime):
            payload["starts_at"] = starts.astimezone(timezone.utc).isoformat()
        rows = self._rest("POST", "interviews", json=payload, headers={"Prefer": "return=representation"})
        return rows[0]

    def get_interview(self, application_id: str) -> dict[str, Any] | None:
        rows = self._rest("GET", "interviews", params={"application_id": f"eq.{application_id}", "select": "*"})
        return rows[0] if rows else None

    def interviews_for_recruiter(self, recruiter_id: str) -> list[dict[str, Any]]:
        rows = self._rest("GET", "interviews", params={"recruiter_id": f"eq.{recruiter_id}", "select": "*"}) or []
        parsed = []
        for row in rows:
            item = dict(row)
            starts = item["starts_at"]
            if isinstance(starts, str):
                item["starts_at"] = datetime.fromisoformat(starts.replace("Z", "+00:00"))
            parsed.append(item)
        return parsed

    def record_email(self, email_type: str, recipient_user_id: str, application_id: str | None) -> bool:
        try:
            self._rest(
                "POST",
                "email_deliveries",
                json={
                    "email_type": email_type,
                    "recipient_user_id": recipient_user_id,
                    "application_id": application_id,
                },
                headers={"Prefer": "return=minimal"},
            )
            return True
        except AppError as exc:
            if "already" in exc.message.lower() or "duplicate" in exc.message.lower() or "unique" in exc.message.lower():
                return False
            raise

    def delete_email_record(self, email_type: str, recipient_user_id: str, application_id: str | None) -> None:
        params: dict[str, str] = {"email_type": f"eq.{email_type}", "recipient_user_id": f"eq.{recipient_user_id}"}
        if application_id:
            params["application_id"] = f"eq.{application_id}"
        else:
            params["application_id"] = "is.null"
        try:
            self._rest("DELETE", "email_deliveries", params=params)
        except AppError:
            pass

    def list_email_deliveries(self) -> list[dict[str, Any]]:
        return self._rest("GET", "email_deliveries", params={"select": "*", "order": "created_at.asc"}) or []

    def hired_count(self, job_id: str) -> int:
        rows = self._rest(
            "GET",
            "applications",
            params={"job_id": f"eq.{job_id}", "stage": "eq.hired", "select": "id"},
        ) or []
        return len(rows)

    def dashboard_rows(self) -> list[dict[str, Any]]:
        jobs = self.list_jobs()
        apps = self.list_applications()
        rows = []
        for job in jobs:
            stages = {k: 0 for k in ("applied", "shortlisted", "interview", "offer", "hired", "rejected", "withdrawn")}
            total = 0
            for app in apps:
                if app["job_id"] == job["id"]:
                    stages[app["stage"]] = stages.get(app["stage"], 0) + 1
                    total += 1
            rows.append({"job": job, "total_applied": total, "stages": stages})
        return rows
