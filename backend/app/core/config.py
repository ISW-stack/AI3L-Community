import warnings
from typing import ClassVar

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # FastAPI
    FASTAPI_ENV: str = "development"
    FASTAPI_DEBUG: bool = False
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000
    FASTAPI_WORKERS: int = 1
    SECRET_KEY: str = "changeme_secret_key_at_least_32_characters_long"

    # PostgreSQL
    POSTGRES_USER: str = "ai3l"
    POSTGRES_PASSWORD: str = "changeme_postgres"
    POSTGRES_DB: str = "ai3l_community"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "changeme_redis"

    # JWT
    JWT_SECRET_KEY: str = "changeme_jwt_secret_key"
    JWT_ALGORITHM: str = "HS256"
    JWT_GUEST_EXPIRE_MINUTES: int = 45
    JWT_MEMBER_EXPIRE_MINUTES: int = 180
    JWT_ADMIN_EXPIRE_MINUTES: int = 300
    JWT_SUPER_ADMIN_EXPIRE_MINUTES: int = 480

    # CORS
    CORS_ORIGINS: str = "http://localhost:15173,http://localhost:13000"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Cookie settings
    # COOKIE_SECURE defaults to True in production, False otherwise.
    # Can always be overridden by the COOKIE_SECURE env var.
    COOKIE_SECURE: bool | None = None  # None means "auto-derive from FASTAPI_ENV"
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""  # Empty = browser default (current domain)

    # CSRF
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # MinIO
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "changeme_minio"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_BUCKET_NAME: str = "ai3l-uploads"
    MINIO_USE_SSL: bool = False
    MINIO_PUBLIC_URL: str = (
        ""  # Browser-accessible URL for presigned URLs (e.g. http://localhost:19000 in dev)
    )

    # Celery — URLs built dynamically from Redis settings via @property below

    # Super Admin (bootstrap)
    SUPER_ADMIN_USERNAME: str = "superadmin"
    SUPER_ADMIN_PASSWORD: str = "changeme_admin"

    # Sentry
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Datadog
    DD_AGENT_HOST: str = ""
    DD_TRACE_ENABLED: bool = False

    # Storage quota
    MAX_USER_STORAGE_BYTES: int = 1_073_741_824  # 1 GB

    # VirusTotal
    VT_API_KEY: str = ""

    # Trusted Hosts (comma-separated, e.g. "example.com,api.example.com")
    TRUSTED_HOSTS: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    _VALID_ENVS: ClassVar[frozenset[str]] = frozenset({"development", "production", "test"})

    @model_validator(mode="after")
    def _validate_fastapi_env(self) -> "Settings":
        if self.FASTAPI_ENV not in self._VALID_ENVS:
            warnings.warn(
                f"FASTAPI_ENV='{self.FASTAPI_ENV}' is not recognized. "
                f"Expected one of: {', '.join(sorted(self._VALID_ENVS))}. "
                f"Treating as non-development.",
                stacklevel=1,
            )
        # Block startup with default/insecure secrets for any non-dev/non-test environment
        if self.FASTAPI_ENV not in ("development", "test"):
            if "changeme" in self.JWT_SECRET_KEY:
                raise ValueError(
                    "JWT_SECRET_KEY contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique secret."
                )
            if "changeme" in self.SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique secret."
                )
            if "changeme" in self.SUPER_ADMIN_PASSWORD:
                raise ValueError(
                    "SUPER_ADMIN_PASSWORD contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique password."
                )
            if "changeme" in self.POSTGRES_PASSWORD:
                raise ValueError(
                    "POSTGRES_PASSWORD contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique password."
                )
            if "changeme" in self.REDIS_PASSWORD:
                raise ValueError(
                    "REDIS_PASSWORD contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique password."
                )
            if "changeme" in self.MINIO_ROOT_PASSWORD:
                raise ValueError(
                    "MINIO_ROOT_PASSWORD contains 'changeme' — refusing to start in production. "
                    "Set a strong, unique password."
                )
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters for HS256."
                )
        # Auto-derive COOKIE_SECURE from FASTAPI_ENV when not explicitly set
        if self.COOKIE_SECURE is None:
            self.COOKIE_SECURE = self.FASTAPI_ENV == "production"
        return self

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    @property
    def is_development(self) -> bool:
        return self.FASTAPI_ENV == "development"


settings = Settings()
