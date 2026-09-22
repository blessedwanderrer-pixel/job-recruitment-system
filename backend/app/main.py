from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .deps import get_service
from .errors import AppError
from .links import frontend_email_origin
from .routers.api import router as api_router
from .routers.internal import router as internal_router
from .rules import ADMIN


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ats_use_memory or settings.supabase_service_role_key:
        service = get_service()
        if not service.store.get_profile_by_email(settings.admin_email):
            try:
                user = service.store.create_auth_user(
                    settings.admin_email,
                    settings.admin_password,
                    {"role": ADMIN},
                    {"full_name": settings.admin_name},
                )
                service.store.upsert_profile(
                    {
                        "id": user["id"],
                        "role": ADMIN,
                        "full_name": settings.admin_name,
                        "phone": settings.admin_phone or None,
                        "email": settings.admin_email.lower(),
                        "is_active": True,
                    }
                )
            except (AppError, ValueError):
                pass
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Nowshera Digital ATS", version="1.0.0", lifespan=lifespan)
    public_origin = frontend_email_origin()
    allow_origins = [
        settings.frontend_url,
        public_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in allow_origins if origin],
        allow_origin_regex=r"(http://(localhost|127\.0\.0\.1):\d+|https://[a-z0-9-]+\.trycloudflare\.com)",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(api_router, prefix="/api")
    app.include_router(internal_router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "nowshera-digital-ats"}

    return app


app = create_app()
