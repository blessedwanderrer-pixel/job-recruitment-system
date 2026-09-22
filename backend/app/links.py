from urllib.parse import quote, urlparse

from .config import settings
from .errors import AppError

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})  # not allowed in invite emails


def frontend_email_origin() -> str:
    public = (settings.frontend_public_url or "").strip().rstrip("/")
    if public:
        return public
    return (settings.frontend_url or "").strip().rstrip("/")


def require_public_email_origin() -> str:
    if settings.ats_use_memory:
        return frontend_email_origin()
    origin = (settings.frontend_public_url or "").strip().rstrip("/")
    if not origin:
        raise AppError(
            "Set FRONTEND_PUBLIC_URL to a public https frontend origin so recruiter invite emails are reachable.",
            500,
        )
    parsed = urlparse(origin)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host in _LOOPBACK_HOSTS:
        raise AppError("FRONTEND_PUBLIC_URL must be a public http(s) origin, not localhost or 127.0.0.1.", 500)
    return origin


def recruiter_set_password_path(origin: str) -> str:
    return f"{origin.rstrip('/')}/set-password"


def encode_set_password_link(origin: str, email: str, token: str) -> str:
    query = f"email={quote(email.strip().lower(), safe='')}&token={quote(token, safe='')}"
    return f"{recruiter_set_password_path(origin)}?{query}"
