import logging
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

_DEV_SECRET = "dev-secret-change-in-prod"
_LOCAL_DB = "postgresql://promptlens:promptlens@localhost:5432/promptlens"
_LOCAL_REDIS = "redis://localhost:6379/0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str = _LOCAL_DB
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 3600

    # --- Redis / Celery ---
    redis_url: str = _LOCAL_REDIS

    # --- Auth ---
    jwt_secret: str = _DEV_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- App ---
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # --- Privacy ---
    privacy_enabled: bool = True  # set False in dev to store raw names, prompts, paths

    # --- Evaluators ---
    hint_threshold: float = 0.4
    streak_warn: int = 5

    # --- Integrations (optional) ---
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    slack_webhook_url: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == _DEV_SECRET:
            log.warning(
                "JWT_SECRET is using the insecure default. "
                "Generate a strong secret: openssl rand -hex 32"
            )
        elif len(v) < 32:
            log.warning("JWT_SECRET is shorter than 32 chars — use a longer secret in production")
        return v

    @model_validator(mode="after")
    def warn_local_defaults(self) -> "Settings":
        if self.app_env == "production":
            if self.database_url == _LOCAL_DB:
                raise ValueError("DATABASE_URL must be set explicitly in production")
            if self.redis_url == _LOCAL_REDIS:
                raise ValueError("REDIS_URL must be set explicitly in production")
            if self.jwt_secret == _DEV_SECRET:
                raise ValueError("JWT_SECRET must be changed from the default in production")
        else:
            if self.database_url == _LOCAL_DB:
                log.warning("DATABASE_URL using local default (set APP_ENV=production to enforce)")
        return self


settings = Settings()
