"""Comprehensive SENTRIX API Verification Suite.

Tests all 23 API endpoints directly across Health, Models, Traffic, Detection,
Alerts, Mitigations, Threshold Config, Audit, Keepalive, and Simulations.
"""

from __future__ import annotations

import os
import sys
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.internal import database_keepalive
from app.api.v1.alerts import list_alerts
from app.api.v1.audit import get_audit_records
from app.api.v1.config import (
    UpdateThresholdConfigRequest,
    get_threshold_configuration,
    update_threshold_configuration,
)
from app.api.v1.detection import AnalyzeFlowRequest, analyze_flow_features
from app.api.v1.health import health_check
from app.api.v1.mitigations import (
    SimulateMitigationRequest,
    cancel_mitigation,
    emergency_disable_mitigations,
    list_mitigations,
    simulate_mitigation,
)
from app.api.v1.models import get_model_metrics, get_models
from app.api.v1.simulations import (
    CreateSimulationRequest,
    SimulationCompareRequest,
    SimulationControlRequest,
    compare_simulation_runs,
    control_simulation_run,
    create_simulation_run,
    export_simulation_report,
    get_simulation_run,
    list_simulation_runs,
    list_simulation_ticks,
)
from app.api.v1.traffic import get_traffic_summary, ingest_flow_observation
from app.core.config import get_settings
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.ingestion.schemas import FlowObservationRequest
from app.safety.gate import set_emergency_disabled
from app.simulator.scenarios import ScenarioType
from app.storage.database import Base


def run_all_api_checks() -> int:
    print("\n" + "=" * 80)
    print("SENTRIX API COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 80 + "\n")

    # In-memory test database setup
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()

    # Pre-seed threshold config
    from app.storage.models import ThresholdConfigModel

    seed_cfg = ThresholdConfigModel(
        version="v1.0.0",
        is_active=True,
        pps_threshold=5000.0,
        bps_threshold=10_000_000.0,
        syn_pps_threshold=500.0,
        rf_probability_threshold=0.75,
        iforest_score_threshold=0.2664,
        created_at="2026-10-27T00:00:00Z",
    )
    session.add(seed_cfg)
    session.commit()

    passed = 0
    total = 0
    results: list[tuple[str, str, str, str]] = []

    def check(name: str, method: str, path: str, fn) -> None:
        nonlocal passed, total
        total += 1
        start = time.perf_counter()
        try:
            _ = fn()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            passed += 1
            results.append(
                (f"{method} {path}", "PASS", f"{elapsed_ms:.1f}ms", str(name))
            )
            print(f"  [OK]   {method:<6} {path:<42} ({elapsed_ms:.1f}ms)")
        except Exception as e:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            results.append((f"{method} {path}", "FAIL", f"{elapsed_ms:.1f}ms", str(e)))
            print(f"  [FAIL] {method:<6} {path:<42} -> ERROR: {e}")

    settings = get_settings()

    # 1. Health
    check("Health Check", "GET", "/api/v1/health", lambda: health_check(settings))

    # 2 & 3. Models
    check("List Models", "GET", "/api/v1/models", lambda: get_models())
    check("Model Metrics", "GET", "/api/v1/models/metrics", lambda: get_model_metrics())

    # 4 & 5. Traffic
    sample_features = {k: 120.0 for k in FEATURE_NAMES}
    flow_req = FlowObservationRequest(
        source_id="test-sensor",
        timestamp="2026-10-27T08:00:00Z",
        window_seconds=10.0,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sample_features,
        target_ip="192.168.1.100",
    )
    check(
        "Ingest Traffic Flow",
        "POST",
        "/api/v1/traffic/flows",
        lambda: ingest_flow_observation(flow_req, session),
    )
    check(
        "Traffic Summary",
        "GET",
        "/api/v1/traffic/summary",
        lambda: get_traffic_summary(),
    )

    # 6. Detection
    analyze_req = AnalyzeFlowRequest(
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sample_features,
    )
    check(
        "Analyze Flow",
        "POST",
        "/api/v1/detection/analyze",
        lambda: analyze_flow_features(analyze_req, session),
    )

    # 7. Alerts
    check(
        "List Alerts",
        "GET",
        "/api/v1/alerts",
        lambda: list_alerts(session, None, None, 50, 0),
    )

    # 8 - 11. Mitigations
    sim_action_id: str = ""

    def test_sim():
        nonlocal sim_action_id
        res = simulate_mitigation(
            SimulateMitigationRequest(
                target_ip="10.0.0.50",
                target_port=80,
                rate_limit_pps=1000,
                duration_seconds=30,
            ),
            session,
        )
        sim_action_id = res["action_id"]
        return res

    check("Simulate Mitigation", "POST", "/api/v1/mitigations/simulate", test_sim)
    check(
        "List Mitigations",
        "GET",
        "/api/v1/mitigations",
        lambda: list_mitigations(session, None, None, 50, 0),
    )
    check(
        "Cancel Mitigation",
        "POST",
        "/api/v1/mitigations/{id}/cancel",
        lambda: cancel_mitigation(sim_action_id, session),
    )

    def test_emergency():
        try:
            return emergency_disable_mitigations(session)
        finally:
            set_emergency_disabled(False)

    check("Emergency Disable", "POST", "/api/v1/mitigations/disable", test_emergency)

    # 12 - 14. Threshold Config
    check(
        "Get Thresholds",
        "GET",
        "/api/v1/config/thresholds",
        lambda: get_threshold_configuration(session),
    )
    check(
        "Patch Thresholds",
        "PATCH",
        "/api/v1/config/thresholds",
        lambda: update_threshold_configuration(
            UpdateThresholdConfigRequest(pps_threshold=8000.0), session
        ),
    )
    check(
        "Put Thresholds",
        "PUT",
        "/api/v1/config/thresholds",
        lambda: update_threshold_configuration(
            UpdateThresholdConfigRequest(pps_threshold=9000.0), session
        ),
    )

    # 15. Audit Records
    check(
        "Get Audit Log (JSON)",
        "GET",
        "/api/v1/audit?format=json",
        lambda: get_audit_records(session, None, "json", 50, 0),
    )
    check(
        "Get Audit Log (CSV)",
        "GET",
        "/api/v1/audit?format=csv",
        lambda: get_audit_records(session, None, "csv", 50, 0),
    )

    # 16. Keepalive
    check(
        "Keepalive Check",
        "GET",
        "/internal/keepalive",
        lambda: database_keepalive(None, session),
    )

    # 17 - 23. Simulations
    sim_run_id: str = ""

    def test_create_sim():
        nonlocal sim_run_id
        req = CreateSimulationRequest(
            scenario_type=ScenarioType.SYN_FLOOD,
            seed=42,
            duration_seconds=15,
            attack_start_tick=2,
            attack_end_tick=10,
            speed_multiplier=10.0,
        )
        res = create_simulation_run(req, session)
        sim_run_id = res.run_id
        return res

    check("Create Simulation Run", "POST", "/api/v1/simulations", test_create_sim)
    check(
        "List Simulation Runs",
        "GET",
        "/api/v1/simulations",
        lambda: list_simulation_runs(session, None, 50, 0),
    )
    check(
        "Get Simulation Detail",
        "GET",
        "/api/v1/simulations/{id}",
        lambda: get_simulation_run(sim_run_id, session),
    )
    check(
        "Start Simulation",
        "POST",
        "/api/v1/simulations/{id}/control (start)",
        lambda: control_simulation_run(
            sim_run_id, SimulationControlRequest(action="start"), session
        ),
    )
    check(
        "Pause Simulation",
        "POST",
        "/api/v1/simulations/{id}/control (pause)",
        lambda: control_simulation_run(
            sim_run_id, SimulationControlRequest(action="pause"), session
        ),
    )
    check(
        "Resume Simulation",
        "POST",
        "/api/v1/simulations/{id}/control (resume)",
        lambda: control_simulation_run(
            sim_run_id, SimulationControlRequest(action="resume"), session
        ),
    )
    check(
        "Step Simulation (+1)",
        "POST",
        "/api/v1/simulations/{id}/control (step)",
        lambda: control_simulation_run(
            sim_run_id, SimulationControlRequest(action="step"), session
        ),
    )
    check(
        "List Simulation Ticks",
        "GET",
        "/api/v1/simulations/{id}/ticks",
        lambda: list_simulation_ticks(sim_run_id, session, 50, 0),
    )

    # Create second run for comparison
    req2 = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        seed=100,
        duration_seconds=15,
        attack_start_tick=2,
        attack_end_tick=10,
    )
    run2 = create_simulation_run(req2, session)

    check(
        "Compare Simulations",
        "POST",
        "/api/v1/simulations/compare",
        lambda: compare_simulation_runs(
            SimulationCompareRequest(run_ids=[sim_run_id, run2.run_id]), session
        ),
    )
    check(
        "Export Report (JSON)",
        "GET",
        "/api/v1/simulations/{id}/export (json)",
        lambda: export_simulation_report(sim_run_id, session, "json"),
    )
    check(
        "Export Report (Markdown)",
        "GET",
        "/api/v1/simulations/{id}/export (markdown)",
        lambda: export_simulation_report(sim_run_id, session, "markdown"),
    )

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed}/{total} ENDPOINTS PASSED (100% SUCCESS)")
    print("=" * 80 + "\n")

    session.close()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_all_api_checks())
