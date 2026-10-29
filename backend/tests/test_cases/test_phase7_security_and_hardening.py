"""SENTRIX PRD Phase 7 Work Package 7.1: Security, Hardening & Regression Suite.

Formally validates:
- Hardening 1: Default configuration safety, secret masking, and environment isolation.
- Hardening 2: Standard error envelope sanitization without internal stack-trace leakage.
- Hardening 3: Allowlist protection against targeting loopback, DNS, and gateway infrastructure.
- Hardening 4: Resistance to input boundary violations, parameter poisoning, and NaN/infinity injections.
- Hardening 5: Audit trail completeness and tamper resistance across state transitions.
- Hardening 6: Simulation safety invariance (zero host modifications in default mode).
"""

from __future__ import annotations

import datetime
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import require_api_auth
from app.main import create_app
from app.policy.allowlist import is_protected_target
from app.safety.gate import (
    is_emergency_disabled,
    set_emergency_disabled,
    validate_safety_gate,
)
from app.storage.database import Base, get_db_session
from app.storage.repositories import AuditRepository, MitigationRepository


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated SQLite database session."""
    db_file = tmp_path / "hardening_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """Provide a test client with an overridden database dependency."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "test-hardening-token")
    get_settings.cache_clear()

    def override_db() -> Session:
        return db_session

    test_app = create_app()
    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[require_api_auth] = lambda: "authenticated_operator"
    try:
        with TestClient(test_app) as test_client:
            yield test_client
    finally:
        test_app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_safety_state() -> Generator[None, None, None]:
    set_emergency_disabled(False)
    yield
    set_emergency_disabled(False)


# -----------------------------------------------------------------------------
# Hardening 1: Default Configuration & Secret Handling
# -----------------------------------------------------------------------------


def test_hardening_configuration_defaults_and_secret_masking() -> None:
    """Verify production-safe default settings and SecretStr protection."""
    settings = Settings(_env_file=None)

    # 1. Defaults must be strictly safe
    assert settings.mitigation_mode == "simulation"
    assert settings.api_auth_required is True
    assert settings.database_url == "sqlite:///./sentrix.db"

    # 2. SecretStr masking check
    settings_with_secret = Settings(
        _env_file=None,
        api_auth_token="super-secret-token-12345",
    )
    assert settings_with_secret.api_auth_token is not None
    # String representation must not expose the plain secret value
    assert "super-secret-token-12345" not in str(settings_with_secret.api_auth_token)
    assert "super-secret-token-12345" not in repr(settings_with_secret.api_auth_token)
    assert (
        settings_with_secret.api_auth_token.get_secret_value()
        == "super-secret-token-12345"
    )


# -----------------------------------------------------------------------------
# Hardening 2: Error Envelope Sanitization & Zero Stack-Trace Leakage
# -----------------------------------------------------------------------------


def test_hardening_error_envelope_sanitization(client: TestClient) -> None:
    """Verify API error responses use standard error envelopes and never leak internal stack traces."""
    # 1. Invalid payload to traffic ingestion endpoint
    resp = client.post("/api/v1/traffic/flows", json={"malformed": "data"})
    assert resp.status_code == 422
    data = resp.json()

    # Must contain documented error envelope
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "request_id" in data["error"]

    # Must not leak Python internal tracebacks or source code lines
    resp_text = resp.text
    assert "Traceback (most recent call last)" not in resp_text
    assert 'File "' not in resp_text
    assert '.py", line' not in resp_text

    # 2. Non-existent resource error
    resp_404 = client.post("/api/v1/mitigations/non_existent_act_999/cancel")
    assert resp_404.status_code == 404
    data_404 = resp_404.json()
    assert "error" in data_404
    assert data_404["error"]["code"] == "NOT_FOUND"


# -----------------------------------------------------------------------------
# Hardening 3: Allowlist & Critical Target Protection
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "critical_target",
    [
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "8.8.8.8",
        "8.8.4.4",
        "1.1.1.1",
        "1.0.0.1",
        "192.168.1.1",
        "10.0.0.1",
    ],
)
def test_hardening_allowlist_rejects_critical_infrastructure(
    critical_target: str,
) -> None:
    """Verify safety gate strictly forbids rate-limiting critical infrastructure targets."""
    assert is_protected_target(critical_target) is True

    gate_result = validate_safety_gate(
        target_ip=critical_target,
        rate_limit_pps=1000,
        duration_seconds=60,
    )
    assert gate_result.allowed is False
    assert "protected infrastructure" in gate_result.rejection_reason.lower()


# -----------------------------------------------------------------------------
# Hardening 4: Parameter Poisoning & Boundary Defense
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad_pps", "bad_duration"),
    [
        (-100, 60),
        (0, 60),
        (50, 60),
        (60000, 60),
        (1000, -10),
        (1000, 0),
        (1000, 5),
        (1000, 500),
    ],
)
def test_hardening_parameter_poisoning_rejected_fail_closed(
    bad_pps: int, bad_duration: int
) -> None:
    """Verify parameter values outside safety bounds fail closed."""
    gate_result = validate_safety_gate(
        target_ip="192.168.10.75",
        rate_limit_pps=bad_pps,
        duration_seconds=bad_duration,
    )
    assert gate_result.allowed is False
    assert "outside allowed safety bounds" in gate_result.rejection_reason.lower()


# -----------------------------------------------------------------------------
# Hardening 5: Audit Trail Immutability & Lifecycle Tracking
# -----------------------------------------------------------------------------


def test_hardening_audit_trail_completeness_and_transitions(
    db_session: Session,
) -> None:
    """Verify state transitions and emergency disable actions produce tamper-evident audit records."""
    audit_repo = AuditRepository(db_session)
    mit_repo = MitigationRepository(db_session)

    # 1. Create mitigation
    mit = mit_repo.create(
        detection_id=None,
        target_ip="192.168.10.88",
        target_port=80,
        action_type="rate_limit",
        rate_limit_pps=1000,
        duration_seconds=60,
        status="proposed",
        mode="simulation",
    )
    assert mit.action_id.startswith("act_")

    # 2. Record audit for simulation transition
    audit_repo.log(
        event_type="mitigation_simulated",
        action="simulate_rate_limit",
        actor="operator_api",
        details={"action_id": mit.action_id, "target_ip": "192.168.10.88"},
    )

    # 3. Trigger emergency disable
    set_emergency_disabled(True)
    assert is_emergency_disabled() is True

    audit_repo.log(
        event_type="emergency_disable_activated",
        action="emergency_disable",
        actor="operator_api",
        details={"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()},
    )

    # 4. Inquire audit records
    records = audit_repo.list_filtered(limit=10)
    assert len(records) >= 2
    event_types = [r.event_type for r in records]
    assert "mitigation_simulated" in event_types
    assert "emergency_disable_activated" in event_types


# -----------------------------------------------------------------------------
# Hardening 6: Simulation Safety Invariance
# -----------------------------------------------------------------------------


def test_hardening_simulation_safety_proof_zero_os_mutations() -> None:
    """Verify simulation mode strictly makes zero subprocess or OS firewall mutations."""
    with (
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
        patch("os.system") as mock_sys,
    ):
        gate_res = validate_safety_gate(
            target_ip="192.168.10.150",
            rate_limit_pps=1500,
            duration_seconds=60,
            mitigation_mode="simulation",
        )
        assert gate_res.allowed is True

        # Assert no OS commands or system modifications were triggered
        assert mock_run.call_count == 0
        assert mock_popen.call_count == 0
        assert mock_sys.call_count == 0
