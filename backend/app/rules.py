from datetime import date, datetime, timedelta, timezone
from typing import Any

from .errors import AppError

PDF_MAX_BYTES = 2 * 1024 * 1024
INTERVIEW_HOURS = 1

CANDIDATE = "candidate"
RECRUITER = "recruiter"
ADMIN = "admin"

STAGES = (
    "applied",
    "shortlisted",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
)

FORWARD_NEXT = {
    "applied": "shortlisted",
    "shortlisted": None,
    "interview": "offer",
    "offer": "hired",
    "hired": None,
    "rejected": None,
    "withdrawn": None,
}

FINAL_STAGES = frozenset({"hired", "rejected"})
ACTIVE_PIPELINE = frozenset({"applied", "shortlisted", "interview", "offer"})
JOB_TYPES = frozenset({"full_time", "part_time", "internship"})
JOB_STATUSES = frozenset({"draft", "open", "closed"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def require_role(profile: dict[str, Any], *roles: str) -> None:
    if profile.get("role") not in roles:
        raise AppError("You do not have permission to do that.", 403)
    if profile.get("role") == RECRUITER and not profile.get("is_active", True):
        raise AppError("This recruiter account is deactivated.", 403)


def validate_cv_file(filename: str, content_type: str | None, data: bytes) -> None:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if not name.endswith(".pdf") or (ctype and "pdf" not in ctype and ctype not in ("application/octet-stream", "")):
        raise AppError("Only PDF files of 2 MB or less are allowed.")
    if not data.startswith(b"%PDF"):
        raise AppError("Only PDF files of 2 MB or less are allowed.")
    if len(data) > PDF_MAX_BYTES:
        raise AppError("Only PDF files of 2 MB or less are allowed.")
    if len(data) == 0:
        raise AppError("Only PDF files of 2 MB or less are allowed.")


def job_is_past_last_date(job: dict[str, Any], today=None) -> bool:
    today = today or utcnow().date()
    last = job["last_date_to_apply"]
    if isinstance(last, datetime):
        last_date = last.date()
    elif isinstance(last, date):
        last_date = last
    else:
        last_date = date.fromisoformat(str(last)[:10])
    return today > last_date


def ensure_job_accepts_applications(job: dict[str, Any]) -> None:
    if job["status"] == "draft":
        raise AppError("This job is not open for applications.")
    if job["status"] == "closed" or job_is_past_last_date(job):
        raise AppError("This job is closed and is not accepting applications.")


def ensure_can_apply(existing_active: dict[str, Any] | None) -> None:
    if existing_active:
        raise AppError("You already have an active application for this job.")


def ensure_can_withdraw(application: dict[str, Any]) -> None:
    if application["stage"] in FINAL_STAGES:
        raise AppError("Hired and Rejected applications cannot be changed.")
    if application["stage"] == "withdrawn":
        raise AppError("This application is already withdrawn.")


def ensure_can_advance(application: dict[str, Any], job: dict[str, Any], target: str | None = None) -> str:
    stage = application["stage"]
    if stage in FINAL_STAGES:
        raise AppError("Hired and Rejected applications cannot be changed.")
    if stage == "withdrawn":
        raise AppError("Withdrawn applications cannot be moved.")
    if job["status"] == "closed":
        raise AppError("This job is closed. Remaining applications can only be rejected.")
    nxt = FORWARD_NEXT.get(stage)
    if nxt is None:
        if stage == "shortlisted":
            raise AppError("A Shortlisted applicant moves to Interview only when an interview is scheduled.")
        raise AppError("This application cannot be moved to the next stage.")
    if target and target != nxt:
        raise AppError("Stages cannot be skipped. Move to the next stage only.")
    return nxt


def ensure_can_reject(application: dict[str, Any]) -> None:
    stage = application["stage"]
    if stage in FINAL_STAGES:
        raise AppError("Hired and Rejected applications cannot be changed.")
    if stage == "withdrawn":
        raise AppError("Withdrawn applications cannot be moved.")
    if stage == "hired":
        raise AppError("Hired and Rejected applications cannot be changed.")


def ensure_can_hire(application: dict[str, Any], job: dict[str, Any], hired_count: int) -> None:
    ensure_can_advance(application, job, "hired")
    if hired_count >= int(job["openings"]):
        raise AppError("This job has no remaining openings.")


def ensure_can_schedule_interview(
    application: dict[str, Any],
    job: dict[str, Any],
    starts_at: datetime,
    location: str | None,
    meeting_link: str | None,
    existing_for_recruiter: list[dict[str, Any]],
    now: datetime | None = None,
) -> None:
    now = as_utc(now or utcnow())
    starts_at = as_utc(starts_at)
    if application["stage"] != "shortlisted":
        raise AppError("An interview can only be scheduled for a Shortlisted applicant.")
    if application["stage"] in FINAL_STAGES:
        raise AppError("Hired and Rejected applications cannot be changed.")
    if application["stage"] == "withdrawn":
        raise AppError("Withdrawn applications cannot be moved.")
    if job["status"] == "closed":
        raise AppError("This job is closed. Remaining applications can only be rejected.")
    if starts_at <= now:
        raise AppError("Interviews cannot be scheduled in the past.")
    if not (location or meeting_link):
        raise AppError("Provide a location or a meeting link for the interview.")
    new_end = starts_at + timedelta(hours=INTERVIEW_HOURS)
    for slot in existing_for_recruiter:
        other_start = as_utc(slot["starts_at"] if not isinstance(slot["starts_at"], str) else datetime.fromisoformat(slot["starts_at"].replace("Z", "+00:00")))
        other_end = other_start + timedelta(hours=INTERVIEW_HOURS)
        if starts_at < other_end and other_start < new_end:
            raise AppError("This interview overlaps another interview for this recruiter.")


def recruiter_assigned(assignments: list[str], recruiter_id: str) -> bool:
    return recruiter_id in assignments
