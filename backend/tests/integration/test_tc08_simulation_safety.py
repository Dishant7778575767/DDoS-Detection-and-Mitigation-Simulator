"""SENTRIX PRD Section 10.2 TC-08: Simulation Mode Safety Proof.

Strict verification that SimulationAdapter and the end-to-end simulation flow
NEVER invoke privileged host networking or enforcement mechanisms (such as
iptables, nftables, tc, netsh, route modifications, or subprocess calls),
and that host networking remains completely untouched.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.mitigations import (
    SimulateMitigationRequest,
    cancel_mitigation,
    simulate_mitigation,
)
from app.mitigation.simulation import SimulationAdapter
from app.services.pipeline import process_flow_pipeline
from app.storage.database import Base
from app.storage.models import AuditEventModel, MitigationModel

FIXTURES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "fixtures" / "test_flows.json"
)


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "safety_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


def test_tc08_simulation_adapter_isolated_unit() -> None:
    """TC-08 Unit: SimulationAdapter methods make zero system or networking calls."""
    adapter = SimulationAdapter()

    with (
        patch("subprocess.run") as mock_subproc_run,
        patch("subprocess.Popen") as mock_subproc_popen,
        patch("os.system") as mock_os_system,
    ):
        # 1. Apply simulated rate limit
        res_apply = adapter.apply_rate_limit(
            action_id="act_test001",
            target_ip="192.168.100.50",
            rate_limit_pps=1500,
            duration_seconds=60,
        )

        assert res_apply["action_id"] == "act_test001"
        assert res_apply["target_ip"] == "192.168.100.50"
        assert res_apply["rate_limit_pps"] == 1500
        assert res_apply["duration_seconds"] == 60
        assert res_apply["mode"] == "simulation"
        assert res_apply["status"] == "simulated"
        assert res_apply["host_networking_modified"] is False

        # 2. Cancel simulated rate limit
        res_cancel = adapter.cancel_rate_limit(
            action_id="act_test001",
            target_ip="192.168.100.50",
        )

        assert res_cancel["action_id"] == "act_test001"
        assert res_cancel["mode"] == "simulation"
        assert res_cancel["status"] == "cancelled"
        assert res_cancel["host_networking_modified"] is False

        # Strict assertion: ZERO privileged enforcement commands were invoked
        assert mock_subproc_run.call_count == 0
        assert mock_subproc_popen.call_count == 0
        assert mock_os_system.call_count == 0


def test_tc08_e2e_pipeline_simulation_safety(db_session: Session) -> None:
    """TC-08 Integration: Full runtime pipeline processes dual-signal threat without modifying host networking."""
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)
    syn_flood_sc = fixtures["scenarios"]["tc03_syn_flood"]

    with (
        patch("subprocess.run") as mock_subproc_run,
        patch("subprocess.Popen") as mock_subproc_popen,
        patch("os.system") as mock_os_system,
    ):
        result = process_flow_pipeline(
            session=db_session,
            source_id="demo-generator:tc08_verifier",
            timestamp="2026-10-26T12:05:00Z",
            window_seconds=10.0,
            feature_schema_version="1.0.0",
            features=syn_flood_sc["features"],
            target_ip="192.168.100.55",
            target_port=80,
        )

        # Mitigation action must be triggered in simulation mode
        assert result["policy_decision"] == "request_mitigation"
        assert result["mitigation_action_id"] is not None
        assert result["mitigation_mode"] == "simulation"

        # Check database records
        mit = (
            db_session.query(MitigationModel)
            .filter_by(action_id=result["mitigation_action_id"])
            .first()
        )
        assert mit is not None
        assert mit.status == "simulated"
        assert mit.mode == "simulation"
        # Must never report applied
        assert mit.status != "applied"

        # Check audit trail recorded simulation safely
        audit_events = (
            db_session.query(AuditEventModel)
            .filter_by(event_type="mitigation_simulated")
            .all()
        )
        assert len(audit_events) >= 1
        sim_audit = audit_events[0]
        assert sim_audit.actor == "safety_gate"
        assert sim_audit.action == "simulate_rate_limit"
        details = json.loads(sim_audit.details_json)
        assert details.get("host_networking_modified") is False

        # Cancel action
        cancel_res = cancel_mitigation(mit.action_id, db_session)
        assert cancel_res["status"] == "cancelled"
        assert cancel_res["host_networking_modified"] is False

        # Assert no OS modifications took place
        assert mock_subproc_run.call_count == 0
        assert mock_subproc_popen.call_count == 0
        assert mock_os_system.call_count == 0


def test_tc08_simulate_api_endpoint_safety(db_session: Session) -> None:
    """TC-08 API: POST /api/v1/mitigations/simulate executes safely under system hooks."""
    with (
        patch("subprocess.run") as mock_subproc_run,
        patch("subprocess.Popen") as mock_subproc_popen,
    ):
        req = SimulateMitigationRequest(
            target_ip="192.168.100.99",
            target_port=443,
            rate_limit_pps=2500,
            duration_seconds=30,
        )
        api_res = simulate_mitigation(req, db_session)

        assert api_res["status"] == "simulated"
        assert api_res["mode"] == "simulation"
        assert api_res["host_networking_modified"] is False
        assert mock_subproc_run.call_count == 0
        assert mock_subproc_popen.call_count == 0
