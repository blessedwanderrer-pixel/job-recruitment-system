from fastapi import APIRouter, Depends, Header

from ..config import settings
from ..deps import get_service
from ..errors import AppError
from ..service import HiringService

router = APIRouter()


@router.post("/internal/close-expired-jobs")
def close_expired_jobs(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    service: HiringService = Depends(get_service),
):
    if x_internal_secret != settings.n8n_internal_secret:
        raise AppError("You do not have permission to do that.", 403)
    closed = service.close_expired_jobs()
    return {"closed": closed}
