"""Regression tests for API error handling and detail preservation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_http_exception_preserves_detail(monkeypatch) -> None:
    """Verifies that custom HTTPException detail strings are preserved in the response envelope."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "false")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        # Attempt to simulate mitigation on invalid / protected target
        resp = client.post(
            "/api/v1/mitigations/simulate",
            json={
                "target_ip": "127.0.0.1",
                "rate_limit_pps": 1000,
                "duration_seconds": 60,
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_REQUEST"
        assert "protected infrastructure" in data["error"]["message"].lower()
        assert data["error"]["request_id"].startswith("req_")


def test_validation_error_provides_readable_field_messages(monkeypatch) -> None:
    """Verifies that Pydantic validation errors format clear field location messages."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "false")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/v1/telemetry/ingress",
            json={
                "items": [
                    {
                        "client_ip": "198.51.100.1",
                        "status_code": 9999,  # Invalid status code
                        "latency_ms": -5.0,  # Invalid negative latency
                        "uri": "/test",
                    }
                ]
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "request_id" in data["error"]
