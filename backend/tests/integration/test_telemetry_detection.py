"""Integration test suite for Multi-Tier Telemetry Detection Endpoints (Milestone 2).

Tests:
1. Authentication enforcement on /detection/live and /detection/evaluate-telemetry
2. GET /detection/baseline response contract
3. POST /detection/evaluate-telemetry evaluation of benign, flash crowd, and attack payloads
4. End-to-end detection pipeline: Ingest HTTP telemetry via ingress -> query live detection
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_detection_endpoints_require_auth(monkeypatch) -> None:
    """Verifies all telemetry detection endpoints enforce Bearer authentication."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        resp_live = client.get("/api/v1/detection/live")
        assert resp_live.status_code == 401

        resp_baseline = client.get("/api/v1/detection/baseline")
        assert resp_baseline.status_code == 401

        resp_eval = client.post("/api/v1/detection/evaluate-telemetry", json={})
        assert resp_eval.status_code == 401


def test_detection_baseline_endpoints(monkeypatch) -> None:
    """Tests retrieval and re-calibration of adaptive EWMA baselines."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    with TestClient(create_app()) as client:
        # Retrieve baseline
        resp = client.get("/api/v1/detection/baseline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rps" in data
        assert "error_rate_pct" in data
        assert "p95_latency_ms" in data

        # Reset baseline
        resp_reset = client.post("/api/v1/detection/baseline/reset", headers=headers)
        assert resp_reset.status_code == 200
        assert resp_reset.json()["status"] == "reset"


def test_evaluate_telemetry_snapshot_api(monkeypatch) -> None:
    """Evaluates arbitrary snapshots via POST /api/v1/detection/evaluate-telemetry."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    with TestClient(create_app()) as client:
        # 1. Benign Snapshot
        benign_payload = {
            "window_duration_seconds": 10.0,
            "total_requests": 100,
            "requests_per_second": 10.0,
            "bytes_per_second": 5000.0,
            "status_codes": {
                "c_2xx": 98,
                "c_3xx": 0,
                "c_4xx": 2,
                "c_5xx": 0,
                "pct_2xx": 98.0,
                "pct_3xx": 0.0,
                "pct_4xx": 2.0,
                "pct_5xx": 0.0,
                "error_rate_pct": 2.0,
            },
            "latencies": {
                "p50_ms": 15.0,
                "p90_ms": 25.0,
                "p95_ms": 30.0,
                "p99_ms": 40.0,
                "min_ms": 5.0,
                "max_ms": 50.0,
                "avg_ms": 16.0,
            },
            "client_metrics": {
                "unique_clients": 25,
                "shannon_entropy": 4.5,
                "max_possible_entropy": 4.64,
                "entropy_ratio": 0.96,
            },
            "top_uris": [{"uri": "/api/v1/catalog", "count": 60, "pct": 60.0}],
            "top_methods": {"GET": 100},
            "is_anomaly": False,
        }
        resp_benign = client.post(
            "/api/v1/detection/evaluate-telemetry",
            json=benign_payload,
            headers=headers,
        )
        assert resp_benign.status_code == 200
        benign_res = resp_benign.json()
        assert benign_res["threat_type"] == "BENIGN"
        assert not benign_res["is_threat"]
        assert benign_res["recommended_action"] == "ALLOW"

        # 2. Flash Crowd Surge Snapshot
        flash_payload = dict(benign_payload)
        flash_payload["requests_per_second"] = 150.0  # Big surge
        flash_payload["total_requests"] = 1500
        flash_payload["client_metrics"] = {
            "unique_clients": 450,
            "shannon_entropy": 8.5,
            "max_possible_entropy": 8.8,
            "entropy_ratio": 0.96,
        }
        resp_flash = client.post(
            "/api/v1/detection/evaluate-telemetry",
            json=flash_payload,
            headers=headers,
        )
        assert resp_flash.status_code == 200
        flash_res = resp_flash.json()
        assert flash_res["threat_type"] == "FLASH_CROWD"
        assert flash_res["is_flash_crowd"]
        assert not flash_res["is_threat"]


def test_end_to_end_ingress_to_detection(monkeypatch) -> None:
    """Verifies that ingesting malicious telemetry immediately triggers live detection."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    with TestClient(create_app()) as client:
        # Reset telemetry buffer
        client.post("/api/v1/telemetry/reset", headers=headers)

        # Ingest an attack pattern: 50 failed login attempts in 1 second from 1 IP
        attack_items = [
            {
                "client_ip": "198.51.100.99",
                "method": "POST",
                "uri": "/api/v1/auth/login",
                "status_code": 401,
                "latency_ms": 12.0,
                "bytes_sent": 250,
            }
            for _ in range(50)
        ]
        resp_ingest = client.post(
            "/api/v1/telemetry/ingress",
            json={"items": attack_items, "anonymize_ips": True},
            headers=headers,
        )
        assert resp_ingest.status_code == 202

        # Query live detection endpoint
        resp_detect = client.get(
            "/api/v1/detection/live?window_seconds=10", headers=headers
        )
        assert resp_detect.status_code == 200
        detect_data = resp_detect.json()

        # Threat should be flagged (either CREDENTIAL_STUFFING_ERROR_BURST or SINGLE_SOURCE_FLOOD)
        assert detect_data["is_threat"]
        assert detect_data["severity"] in ("HIGH", "CRITICAL")
        assert len(detect_data["reasons"]) > 0
        assert len(detect_data["z_scores"]) > 0
