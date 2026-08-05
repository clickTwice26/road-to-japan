"""Application configuration.

All settings are read from the environment (or a local ``.env`` file) and
validated by pydantic-settings, so the app fails fast and loudly at boot
instead of blowing up on the first request with a ``None`` somewhere.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---------------------------------------------------------------
    ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(min_length=16)
    APP_NAME: str = "roadtojapan"
    API_PREFIX: str = "/api/v1"

    # --- PostgreSQL ---------------------------------------------------------
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "roadtojapan"
    POSTGRES_USER: str = "roadtojapan"
    POSTGRES_PASSWORD: str

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # --- Redis --------------------------------------------------------------
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB_CACHE: int = 0
    REDIS_DB_LIMITER: int = 1
    REDIS_DB_SESSION: int = 2

    CACHE_DEFAULT_TIMEOUT: int = 300
    RATELIMIT_DEFAULT: str = "200 per minute"

    # --- HTTP ---------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["*"]
    JSON_SORT_KEYS: bool = False

    # --- Logging ------------------------------------------------------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON: bool = True

    # --- Derived URLs -------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    def _redis_url(self, db: int) -> str:
        return str(
            RedisDsn.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                password=self.REDIS_PASSWORD,
                path=str(db),
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_CACHE_URL(self) -> str:
        return self._redis_url(self.REDIS_DB_CACHE)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_LIMITER_URL(self) -> str:
        return self._redis_url(self.REDIS_DB_LIMITER)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_SESSION_URL(self) -> str:
        return self._redis_url(self.REDIS_DB_SESSION)

    # --- Flask config mapping ----------------------------------------------
    def as_flask_config(self) -> dict[str, object]:
        """Translate settings into the keys Flask and its extensions expect."""
        return {
            "ENV": self.ENV,
            "DEBUG": self.DEBUG,
            "TESTING": self.ENV == "testing",
            "SECRET_KEY": self.SECRET_KEY,
            "APP_NAME": self.APP_NAME,
            "API_PREFIX": self.API_PREFIX,
            "JSON_SORT_KEYS": self.JSON_SORT_KEYS,
            "PROPAGATE_EXCEPTIONS": False,
            # SQLAlchemy
            "SQLALCHEMY_DATABASE_URI": self.SQLALCHEMY_DATABASE_URI,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ECHO": self.DB_ECHO,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "pool_size": self.DB_POOL_SIZE,
                "max_overflow": self.DB_MAX_OVERFLOW,
                "pool_recycle": self.DB_POOL_RECYCLE,
                "pool_pre_ping": True,
            },
            # Flask-Caching
            "CACHE_TYPE": "RedisCache",
            "CACHE_REDIS_URL": self.REDIS_CACHE_URL,
            "CACHE_DEFAULT_TIMEOUT": self.CACHE_DEFAULT_TIMEOUT,
            "CACHE_KEY_PREFIX": f"{self.APP_NAME}:cache:",
            # Flask-Limiter. RATELIMIT_DEFAULT must arrive via config: the
            # limiter parses it during init_app, so assigning the attribute
            # afterwards silently leaves the default limit unregistered.
            "RATELIMIT_ENABLED": self.ENV != "testing",
            "RATELIMIT_DEFAULT": self.RATELIMIT_DEFAULT,
            "RATELIMIT_STORAGE_URI": self.REDIS_LIMITER_URL,
            "RATELIMIT_STRATEGY": "moving-window",
            "RATELIMIT_HEADERS_ENABLED": True,
            # Sessions (server-side, Redis-backed)
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "SESSION_COOKIE_SECURE": self.ENV == "production",
            # Misc
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "LOG_LEVEL": self.LOG_LEVEL,
            "LOG_JSON": self.LOG_JSON,
        }


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so the environment is parsed exactly once."""
    return Settings()
