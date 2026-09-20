from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field

from ..deps import get_current_user, get_optional_user, get_service
from ..service import HiringService

router = APIRouter()


class RegisterBody(BaseModel):
    full_name: str
    phone: str
    email: EmailStr
    password: str = Field(min_length=6)


class RecruiterBody(BaseModel):
    full_name: str
    email: EmailStr


class JobBody(BaseModel):
    title: str
    department: str
    location: str
    job_type: str
    description: str
    requirements: str
    last_date_to_apply: str
    openings: int


class OpenJobBody(BaseModel):
    recruiter_ids: list[str] = []


class AssignBody(BaseModel):
    recruiter_ids: list[str]


class NoteBody(BaseModel):
    body: str


class InterviewBody(BaseModel):
    starts_at: datetime
    location: str | None = None
    meeting_link: str | None = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/login")
def login(body: LoginBody, service: HiringService = Depends(get_service)):
    return service.login(body.email, body.password)


class SetPasswordBody(BaseModel):
    email: EmailStr
    token: str
    password: str = Field(min_length=6)


@router.post("/auth/set-password")
def set_password(body: SetPasswordBody, service: HiringService = Depends(get_service)):
    return service.set_recruiter_password(body.email, body.token, body.password)


@router.post("/auth/register")
def register(body: RegisterBody, service: HiringService = Depends(get_service)):
    profile = service.register_candidate(body.full_name, body.phone, body.email, body.password)
    return {"id": profile["id"], "email": profile["email"], "message": "Account created. You can sign in."}


@router.get("/me")
def me(actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.me(actor)


@router.get("/admin/recruiters")
def list_recruiters(actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.list_recruiters(actor)


@router.post("/admin/recruiters")
def create_recruiter(body: RecruiterBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.create_recruiter(actor, body.full_name, body.email)


@router.post("/admin/recruiters/{recruiter_id}/deactivate")
def deactivate_recruiter(recruiter_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.deactivate_recruiter(actor, recruiter_id)


@router.post("/cvs")
async def upload_cv(
    file: UploadFile = File(...),
    actor: dict[str, Any] = Depends(get_current_user),
    service: HiringService = Depends(get_service),
):
    data = await file.read()
    return service.upload_cv(actor, file.filename or "cv.pdf", file.content_type, data)


@router.get("/jobs")
def list_jobs(actor: dict[str, Any] | None = Depends(get_optional_user), service: HiringService = Depends(get_service)):
    return service.list_jobs(actor)


@router.post("/admin/jobs")
def create_job(body: JobBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.create_job(actor, body.model_dump())


@router.get("/jobs/{job_id}")
def get_job(job_id: str, actor: dict[str, Any] | None = Depends(get_optional_user), service: HiringService = Depends(get_service)):
    return service.get_job(actor, job_id)


@router.post("/admin/jobs/{job_id}/open")
def open_job(job_id: str, body: OpenJobBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.open_job(actor, job_id, body.recruiter_ids)


@router.post("/admin/jobs/{job_id}/close")
def close_job(job_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.close_job(actor, job_id)


@router.post("/admin/jobs/{job_id}/recruiters")
def assign_recruiters(job_id: str, body: AssignBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.assign_recruiters(actor, job_id, body.recruiter_ids)


@router.post("/jobs/{job_id}/apply")
def apply(job_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.apply(actor, job_id)


@router.get("/applications/me")
def my_applications(actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.my_applications(actor)


@router.get("/jobs/{job_id}/applications")
def job_applications(job_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.list_job_applications(actor, job_id)


@router.get("/applications/{application_id}")
def get_application(application_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.get_application(actor, application_id)


@router.get("/applications/{application_id}/cv")
def application_cv(application_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return {"url": service.application_cv_url(actor, application_id)}


@router.post("/applications/{application_id}/withdraw")
def withdraw(application_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.withdraw(actor, application_id)


@router.post("/applications/{application_id}/notes")
def add_note(application_id: str, body: NoteBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.add_note(actor, application_id, body.body)


@router.post("/applications/{application_id}/advance")
async def advance(application_id: str, request: Request, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    to_stage = None
    if (request.headers.get("content-type") or "").startswith("application/json"):
        raw = await request.body()
        if raw:
            import json
            data = json.loads(raw)
            if isinstance(data, dict):
                to_stage = data.get("to_stage")
    return service.advance(actor, application_id, to_stage)


@router.post("/applications/{application_id}/reject")
def reject(application_id: str, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.reject(actor, application_id)


@router.post("/applications/{application_id}/interview")
def schedule_interview(application_id: str, body: InterviewBody, actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.schedule_interview(actor, application_id, body.starts_at, body.location, body.meeting_link)


@router.get("/admin/dashboard")
def dashboard(actor: dict[str, Any] = Depends(get_current_user), service: HiringService = Depends(get_service)):
    return service.dashboard(actor)
