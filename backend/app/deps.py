from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import Depends, Header

from .config import settings
from .errors import AppError
from .mailer import Mailer
from .rules import RECRUITER
from .service import HiringService
from .store import MemoryStore
from .supabase_store import SupabaseStore, current_access_token

_memory_store: MemoryStore | None = None
_supabase_store: SupabaseStore | None = None
_service: HiringService | None = None


def get_store():
    global _memory_store, _supabase_store
    if settings.ats_use_memory:
        if _memory_store is None:
            _memory_store = MemoryStore()
        return _memory_store
    if not settings.supabase_url or not (settings.supabase_service_role_key or settings.supabase_anon_key):
        raise AppError("Supabase is not configured. Set SUPABASE_URL and a service-role or anon key.", 500)
    if _supabase_store is None:
        _supabase_store = SupabaseStore(
            settings.supabase_url,
            settings.supabase_anon_key,
            settings.supabase_service_role_key,
        )
    return _supabase_store


def get_service(
    authorization: Annotated[str | None, Header()] = None,
) -> HiringService:
    global _service
    store = get_store()
    if settings.ats_use_memory:
        if _service is None:
            _service = HiringService(store, Mailer(store))
        return _service
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip() or None
    if token:
        current_access_token.set(token)
        if hasattr(store, "authed"):
            store = store.authed(token)
    return HiringService(store, Mailer(store))


def reset_runtime() -> None:
    global _memory_store, _supabase_store, _service
    _memory_store = None
    _supabase_store = None
    _service = None


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("Sign in is required.", 401)
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError("Sign in is required.", 401)
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    service: HiringService = Depends(get_service),
) -> dict[str, Any]:
    token = _bearer(authorization)
    current_access_token.set(token)
    if settings.ats_use_memory or not settings.supabase_url:
        profile = service.store.get_profile(token)
        if not profile:
            raise AppError("Sign in is required.", 401)
        if profile.get("role") == RECRUITER and not profile.get("is_active", True):
            raise AppError("This recruiter account is deactivated.", 403)
        return profile

    url = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": settings.supabase_anon_key or settings.supabase_service_role_key,
        "Authorization": f"Bearer {token}",
    }
    try:
        response = httpx.get(f"{url}/auth/v1/user", headers=headers, timeout=15.0)
    except httpx.HTTPError:
        raise AppError("Could not verify your session.", 401)
    if response.status_code >= 400:
        raise AppError("Sign in is required.", 401)
    data = response.json()
    user_id = data.get("id")
    if not user_id:
        raise AppError("Sign in is required.", 401)
    profile = service.store.get_profile(user_id)
    if not profile:
        raise AppError("Your account is not set up for this hiring site.", 403)
    if profile.get("role") == RECRUITER and not profile.get("is_active", True):
        raise AppError("This recruiter account is deactivated.", 403)
    return profile


def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    service: HiringService = Depends(get_service),
) -> dict[str, Any] | None:
    if not authorization:
        return None
    try:
        return get_current_user(authorization, service)
    except AppError as exc:
        if exc.status_code == 401:
            return None
        raise
