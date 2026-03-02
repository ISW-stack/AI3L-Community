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
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:15173,http://localhost:13000"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Cookie settings
    COOKIE_SECURE: bool = False  # Set True in production (requires HTTPS)
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

    # Celery
    CELERY_BROKER_URL: str = "redis://:changeme_redis@redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://:changeme_redis@redis:6379/2"

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
    LOG_LEVEL: str = "DEBUG"
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

    @property
    def is_development(self) -> bool:
        return self.FASTAPI_ENV == "development"


settings = Settings()
