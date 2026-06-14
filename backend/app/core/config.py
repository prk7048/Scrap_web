from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = Field(min_length=16)
    admin_email: str
    admin_password: str
    database_url: str
    public_api_base_url: str = "http://localhost:8000"
    backend_cors_origins: str = "http://localhost:5173"
    data_dir: str = "data"
    backup_dir: str = "backups"
    session_cookie_name: str = "archive_session"
    session_ttl_days: int = 90
    capture_timeout_ms: int = 30_000

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
