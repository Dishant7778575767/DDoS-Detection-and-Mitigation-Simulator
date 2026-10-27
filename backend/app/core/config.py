from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def is_psycopg2_usable() -> bool:
    """Check if psycopg2 can be loaded without Windows DLL / AppLocker blocking."""
    try:
        import psycopg2  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    app_env: str = "development"
    mitigation_mode: str = "simulation"
    model_path: Path = Path("models/approved_model.joblib")
    database_url: str = "sqlite:///./sentrix.db"
    api_auth_required: bool = True
    api_auth_token: SecretStr | None = None
    keepalive_secret: SecretStr | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("APP_ENV must not be empty")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        cleaned = value.strip()
        driver_prefix = (
            "postgresql+psycopg2" if is_psycopg2_usable() else "postgresql+pg8000"
        )
        if cleaned.startswith("postgres://"):
            cleaned = f"{driver_prefix}://" + cleaned[len("postgres://") :]
        elif (
            cleaned.startswith("postgresql://")
            and "+psycopg" not in cleaned
            and "+pg8000" not in cleaned
        ):
            cleaned = f"{driver_prefix}://" + cleaned[len("postgresql://") :]
        try:
            url = make_url(cleaned)
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL must be a valid database URL") from exc
        allowed_prefixes = ("sqlite", "postgresql")
        if not any(url.drivername.startswith(p) for p in allowed_prefixes):
            raise ValueError(
                f"Unsupported database dialect '{url.drivername}'. DATABASE_URL must use SQLite or PostgreSQL."
            )
        return cleaned


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings(settings: Settings) -> None:
    if settings.api_auth_required and (
        settings.api_auth_token is None
        or not settings.api_auth_token.get_secret_value().strip()
    ):
        raise ValueError("API_AUTH_TOKEN must be set when API_AUTH_REQUIRED is true")
