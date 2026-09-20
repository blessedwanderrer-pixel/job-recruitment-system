from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    frontend_url: str = "http://127.0.0.1:5173"
    n8n_webhook_url: str = ""
    n8n_internal_secret: str = Field(..., min_length=1)
    admin_email: str = "admin@nowsheradigital.com"
    admin_password: str = Field(..., min_length=1)
    admin_name: str = "Hiring Manager"
    admin_phone: str = ""
    ats_use_memory: bool = False


try:
    settings = Settings()
except ValidationError as exc:
    missing = [str(err["loc"][0]).upper() for err in exc.errors() if err.get("loc")]
    names = ", ".join(dict.fromkeys(missing)) or "ADMIN_PASSWORD, N8N_INTERNAL_SECRET"
    raise RuntimeError(
        f"Missing required environment variable(s): {names}. "
        "Set them in .env (see .env.example). Empty values are not allowed."
    ) from exc
