import os
import sys
import zlib
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
    return text_pdf(text)


def text_pdf(text: str, *, compressed: bool = False, producer: str = "ATS test fixture") -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT\n/F1 12 Tf\n72 720 Td\n({safe}) Tj\nET\n".encode("latin-1", errors="replace")
    stream = zlib.compress(content) if compressed else content
    stream_dict = f"<< /Length {len(stream)}" + (" /Filter /FlateDecode" if compressed else "") + " >>"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        stream_dict.encode("ascii") + b"\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Producer ({producer}) >>".encode("latin-1", errors="replace"),
    ]
    return _pdf_with_xref(objects, info_object=6)


def empty_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>",
    ]
    return _pdf_with_xref(objects)


def image_only_pdf() -> bytes:
    image = zlib.compress(b"\x80")
    content = zlib.compress(b"q 100 0 0 100 72 600 cm /Im1 Do Q")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} /Filter /FlateDecode >>".encode("ascii")
        + b"\nstream\n"
        + content
        + b"\nendstream",
        (
            f"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
            f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(image)} >>"
        ).encode("ascii")
        + b"\nstream\n"
        + image
        + b"\nendstream",
    ]
    return _pdf_with_xref(objects)


def _pdf_with_xref(objects: list[bytes], info_object: int | None = None) -> bytes:
    pdf = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    info = f" /Info {info_object} 0 R" if info_object else ""
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R{info} >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


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
