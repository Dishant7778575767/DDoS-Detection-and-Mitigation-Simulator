from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_requires_authentication_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_health_returns_minimal_authenticated_status(
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "sentrix.db" not in response.text
    assert "test-token" not in response.text


def test_internal_error_does_not_expose_exception_details(
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_AUTH_REQUIRED", "false")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    app = create_app()

    def raise_internal_error() -> None:
        raise RuntimeError("private failure detail")

    app.add_api_route(
        "/test/internal-error",
        raise_internal_error,
        methods=["GET"],
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/internal-error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private failure detail" not in response.text
    assert "request_id" in response.json()["error"]


def test_validation_error_uses_documented_error_envelope(
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_AUTH_REQUIRED", "false")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    app = create_app()

    def requires_integer(value: int) -> dict[str, int]:
        return {"value": value}

    app.add_api_route(
        "/test/validation-error",
        requires_integer,
        methods=["GET"],
    )
    with TestClient(app) as client:
        response = client.get("/test/validation-error", params={"value": "invalid"})

    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message", "request_id"}
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
