from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    app_env: str = "development"
    mitigation_mode: Literal["simulation"] = "simulation"
    model_path: Path = Path("models/approved_model.joblib")
    database_url: str = "sqlite:///./sentrix.db"
    api_auth_required: bool = True
    api_auth_token: SecretStr | None = None

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("APP_ENV must not be empty")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL must be a valid SQLite URL") from exc
        if url.drivername != "sqlite":
            raise ValueError("DATABASE_URL must use SQLite")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings(settings: Settings) -> None:
    if settings.api_auth_required and (
        settings.api_auth_token is None
        or not settings.api_auth_token.get_secret_value().strip()
    ):
        raise ValueError(
            "API_AUTH_TOKEN must be set when API_AUTH_REQUIRED is true"
        )
