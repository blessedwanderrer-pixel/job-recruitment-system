import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ATS_USE_MEMORY"] = "true"
os.environ["N8N_WEBHOOK_URL"] = ""
os.environ.setdefault("ADMIN_PASSWORD", "Admin123!")
os.environ.setdefault("N8N_INTERNAL_SECRET", "test-n8n-internal-secret")
os.environ.setdefault("FRONTEND_PUBLIC_URL", "https://ats.example.test")

from app.deps import reset_runtime  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rules import ADMIN, CANDIDATE, RECRUITER  # noqa: E402


def cv_pdf(text: str) -> bytes:
    safe = text.replace("(", "\\(").replace(")", "\\)")
    return b"%PDF-1.4\n(" + safe.encode("latin-1", errors="replace") + b")\n%%EOF\n"


def tiny_pdf() -> bytes:
    return cv_pdf("Experienced Python developer. Built REST APIs and PostgreSQL databases for production systems.")


def big_pdf() -> bytes:
    return b"%PDF-1.4\n" + (b"0" * (2 * 1024 * 1024)) + b"\n%%EOF\n"


def future_slot(hours=24, minutes=0) -> str:
    when = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)
    return when.replace(microsecond=0).isoformat()


@pytest.fixture
def ctx():
    reset_runtime()
    os.environ["ATS_USE_MEMORY"] = "true"
    from app import config

    config.settings.ats_use_memory = True
    config.settings.n8n_webhook_url = ""
    config.settings.frontend_public_url = os.environ.get("FRONTEND_PUBLIC_URL", "https://ats.example.test")
    app = create_app()
    client = TestClient(app)
    from app.deps import get_service

    service = get_service()
    admin = service.store.get_profile_by_email(config.settings.admin_email)
    if not admin:
        user = service.store.create_auth_user("admin@nowsheradigital.com", "Admin123!", {"role": ADMIN}, {"full_name": "Hiring Manager"})
        admin = service.store.upsert_profile(
            {"id": user["id"], "role": ADMIN, "full_name": "Hiring Manager", "email": "admin@nowsheradigital.com", "is_active": True}
        )
    yield {"client": client, "service": service, "admin": admin}
    client.close()
    reset_runtime()


def auth(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def make_candidate(service, email, name="Candidate"):
    user = service.store.create_auth_user(email, "Pass123!", {"role": CANDIDATE}, {"full_name": name})
    return service.store.upsert_profile(
        {"id": user["id"], "role": CANDIDATE, "full_name": name, "phone": "03001234567", "email": email, "is_active": True}
    )


def make_recruiter(service, email="recruiter@nowsheradigital.com"):
    user = service.store.create_auth_user(email, "Pass123!", {"role": RECRUITER}, {"full_name": "Recruiter One"})
    return service.store.upsert_profile(
        {"id": user["id"], "role": RECRUITER, "full_name": "Recruiter One", "email": email, "is_active": True}
    )


def last_date(days=14) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def create_open_job(client, admin_id, recruiter_id, openings=2, title="Backend Developer", requirements="Python. REST APIs. PostgreSQL."):
    job = client.post(
        "/api/admin/jobs",
        headers=auth(admin_id),
        json={
            "title": title,
            "department": "Engineering",
            "location": "Nowshera",
            "job_type": "full_time",
            "description": "Build APIs.",
            "requirements": requirements,
            "last_date_to_apply": last_date(),
            "openings": openings,
        },
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["id"]
    opened = client.post(
        f"/api/admin/jobs/{job_id}/open",
        headers=auth(admin_id),
        json={"recruiter_ids": [recruiter_id]},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()


def upload_and_apply(client, candidate_id, job_id, filename="cv.pdf", data=None):
    files = {"file": (filename, data or tiny_pdf(), "application/pdf")}
    up = client.post("/api/cvs", headers=auth(candidate_id), files=files)
    applied = client.post(f"/api/jobs/{job_id}/apply", headers=auth(candidate_id))
    return up, applied
