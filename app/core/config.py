from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production-use-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Ecom API"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    docs_enabled: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://ecom:ecom@localhost:5432/ecom"
    db_echo: bool = False

    jwt_secret: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    cors_origins: str = "http://localhost:3000"  # comma-separated
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    refresh_cookie_name: str = "refresh_token"

    rate_limit_enabled: bool = True

    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "Admin@12345"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def refresh_cookie_path(self) -> str:
        return f"{self.api_prefix}/auth"

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment in ("staging", "production"):
            if self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be a random string of at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in staging/production")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
