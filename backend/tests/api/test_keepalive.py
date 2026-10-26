"""Unit tests covering the authenticated /internal/keepalive endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import create_app
from app.storage.database import get_db_session


@pytest.fixture
def test_app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "main-test-token")
    monkeypatch.setenv("KEEPALIVE_SECRET", "super-secret-keepalive-key")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_keepalive_unauthenticated_rejected(test_app_client: TestClient) -> None:
    """Missing or invalid token returns HTTP 401 Unauthorized."""
    # 1. No Authorization header
    res_no_auth = test_app_client.get("/internal/keepalive")
    assert res_no_auth.status_code == 401
    assert "error" in res_no_auth.json()

    # 2. Bad bearer token
    res_bad_auth = test_app_client.get(
        "/internal/keepalive",
        headers={"Authorization": "Bearer wrong-token-123"},
    )
    assert res_bad_auth.status_code == 401


def test_keepalive_authenticated_success(test_app_client: TestClient) -> None:
    """Valid keepalive secret returns HTTP 200 with status ok and connected database."""
    res = test_app_client.get(
        "/internal/keepalive",
        headers={"Authorization": "Bearer super-secret-keepalive-key"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_keepalive_fallback_to_api_token_when_secret_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When KEEPALIVE_SECRET is not configured, API_AUTH_TOKEN serves as fallback."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "fallback-token-456")
    monkeypatch.setenv("KEEPALIVE_SECRET", "")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        res = client.get(
            "/internal/keepalive",
            headers={"Authorization": "Bearer fallback-token-456"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
    get_settings.cache_clear()


def test_keepalive_database_failure_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the database is unreachable, keepalive returns 503 without leaking stack traces."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("KEEPALIVE_SECRET", "super-secret-keepalive-key")
    get_settings.cache_clear()

    app = create_app()

    def failing_db_session():
        mock_session = MagicMock(spec=Session)
        mock_session.execute.side_effect = RuntimeError("Supabase connection timeout")
        yield mock_session

    app.dependency_overrides[get_db_session] = failing_db_session
    try:
        with TestClient(app) as client:
            res = client.get(
                "/internal/keepalive",
                headers={"Authorization": "Bearer super-secret-keepalive-key"},
            )
            assert res.status_code == 503
            data = res.json()
            assert "error" in data
            assert data["error"]["code"] == "HTTP_ERROR"
            # Invariant: Must not expose raw internal exception traceback or secrets
            assert "Supabase connection timeout" not in res.text
            assert "super-secret-keepalive-key" not in res.text
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
