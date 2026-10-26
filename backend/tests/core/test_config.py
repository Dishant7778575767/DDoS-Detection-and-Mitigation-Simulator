import pytest
from pydantic import ValidationError

from app.core.config import Settings, validate_runtime_settings


def test_defaults_use_simulation_sqlite_and_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "APP_ENV",
        "MITIGATION_MODE",
        "MODEL_PATH",
        "DATABASE_URL",
        "API_AUTH_REQUIRED",
        "API_AUTH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.mitigation_mode == "simulation"
    assert settings.database_url == "sqlite:///./sentrix.db"
    assert settings.api_auth_required is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mitigation_mode", "lab"),
        ("database_url", "mysql://localhost/sentrix"),
        ("database_url", "oracle://localhost/sentrix"),
    ],
)
def test_rejects_unsupported_or_unsafe_configuration(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize(
    ("raw_url", "expected_prefix"),
    [
        ("sqlite:///./sentrix.db", "sqlite"),
        ("postgresql://user:pass@localhost:5432/sentrix", "postgresql"),
        ("postgresql+psycopg2://user:pass@localhost:5432/sentrix", "postgresql+psycopg2"),
        ("postgres://user:pass@localhost:5432/sentrix", "postgresql"),
    ],
)
def test_accepts_valid_postgresql_and_sqlite_urls(
    raw_url: str, expected_prefix: str
) -> None:
    settings = Settings(_env_file=None, database_url=raw_url)
    assert settings.database_url.startswith(expected_prefix)


def test_authentication_default_requires_a_token_at_runtime() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValueError, match="API_AUTH_TOKEN"):
        validate_runtime_settings(settings)


def test_authentication_can_be_disabled_explicitly_for_local_testing() -> None:
    settings = Settings(
        _env_file=None,
        api_auth_required=False,
    )

    validate_runtime_settings(settings)
