import json
from collections.abc import Sequence
from enum import StrEnum
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application configuration with strict environment validation.
    Protects against deploying insecure development defaults to production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "healthyIndia API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = Environment.LOCAL
    DEBUG: bool = False

    # Server binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Security configuration
    # Fake placeholder for development; production enforces a high-entropy secret
    SECRET_KEY: str = "insecure-dev-secret-key-replace-in-production-min-32-chars"

    # Restrictive CORS: explicit list of origins
    ALLOWED_ORIGINS: Sequence[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Allowed Hosts for Host header validation
    ALLOWED_HOSTS: Sequence[str] = Field(default=["localhost", "127.0.0.1", "testserver"])

    # Request limits (Phase 1 baseline)
    MAX_REQUEST_BODY_BYTES: int = 1_048_576  # 1 MB
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError("ALLOWED_ORIGINS must be a list of strings or comma-separated string")

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [host.strip() for host in v.split(",") if host.strip()]
        if isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError("ALLOWED_HOSTS must be a list of strings or comma-separated string")

    @model_validator(mode="after")
    def validate_environment_constraints(self) -> "Settings":
        # Staging & Production strict checks
        if self.ENVIRONMENT in (Environment.PRODUCTION, Environment.STAGING):
            if self.DEBUG:
                raise ValueError(f"DEBUG must be False in {self.ENVIRONMENT.value} environment.")

            # Enforce strong production SECRET_KEY
            insecure_indicators = ("insecure", "changeme", "change-me", "default", "example")
            if len(self.SECRET_KEY) < 32 or any(
                ind in self.SECRET_KEY.lower() for ind in insecure_indicators
            ):
                raise ValueError(
                    f"A cryptographically strong SECRET_KEY (min 32 characters, no default terms) "
                    f"is required in {self.ENVIRONMENT.value}."
                )

            # Prevent wildcard origin or localhost origins in production
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Wildcard '*' CORS origin is forbidden in production/staging.")

            for origin in self.ALLOWED_ORIGINS:
                if "localhost" in origin or "127.0.0.1" in origin:
                    raise ValueError(
                        f"Localhost origin '{origin}' is forbidden in {self.ENVIRONMENT.value}."
                    )

        # In any environment, disallow wildcard origin if credentials could be used
        if "*" in self.ALLOWED_ORIGINS and len(self.ALLOWED_ORIGINS) > 1:
            raise ValueError("Wildcard origin cannot be combined with explicit origins.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
