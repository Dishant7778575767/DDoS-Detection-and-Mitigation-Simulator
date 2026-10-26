#!/usr/bin/env python3
"""SENTRIX End-to-End API Test Suite.

Tests all 14 PRD Section 7 REST API endpoints against a live server or in-memory
FastAPI app with detailed response formatting and latency tracking.

Usage:
    python scripts/test_all_apis.py [--url http://127.0.0.1:8000] [--token dev-only-change-me]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.safety.gate import set_emergency_disabled

# ANSI Color formatting
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class ApiTestRunner:
    """Dispatches HTTP requests and formats test assertions."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.passed = 0
        self.failed = 0

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any, float]:
        url = f"{self.base_url}{path}"
        req_headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        data = None
        if payload is not None:
            req_headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        t0 = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                content_type = resp.headers.get("Content-Type", "")
                raw_body = resp.read().decode("utf-8")
                if "application/json" in content_type:
                    body = json.loads(raw_body)
                else:
                    body = raw_body
                return resp.status, body, elapsed_ms
        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            raw_body = exc.read().decode("utf-8")
            try:
                body = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = raw_body
            return exc.code, body, elapsed_ms
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return 0, str(exc), elapsed_ms

    def assert_test(
        self,
        index: int,
        name: str,
        method: str,
        path: str,
        expected_status: int | tuple[int, ...],
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        status, body, elapsed = self.request(method, path, payload, headers)
        if isinstance(expected_status, int):
            is_pass = status == expected_status
            expected_repr = str(expected_status)
        else:
            is_pass = status in expected_status
            expected_repr = "/".join(str(s) for s in expected_status)

        if is_pass:
            self.passed += 1
            status_badge = f"{GREEN}PASS [{status}]{RESET}"
        else:
            self.failed += 1
            status_badge = f"{RED}FAIL [{status} != {expected_repr}]{RESET}"

        latency_badge = f"{DIM}({elapsed:5.1f}ms){RESET}"
        print(
            f" {CYAN}#{index:02d}{RESET} {BOLD}{name:<38}{RESET} {method:<6} {path:<34} {status_badge} {latency_badge}"
        )

        if not is_pass:
            print(
                f"     {RED}Response:{RESET} {json.dumps(body) if isinstance(body, dict) else body}"
            )

        return status, body


def run_all_tests(base_url: str, token: str) -> bool:
    print(
        f"\n{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(
        f"{BOLD}{CYAN}               SENTRIX API CONTRACT VERIFICATION SUITE                  {RESET}"
    )
    print(
        f"{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(f" Target Host: {BOLD}{base_url}{RESET}")
    print(
        f" Auth Token:  {BOLD}{token[:4]}****{token[-4:] if len(token) > 8 else ''}{RESET}"
    )
    print(" ------------------------------------------------------------------------\n")

    runner = ApiTestRunner(base_url, token)

    # Pre-test cleanup: ensure safety gate emergency disable switch is cleared on live server
    runner.request("POST", "/api/v1/mitigations/disable?enable=true")

    # 1. Health
    runner.assert_test(1, "Service Health Check", "GET", "/api/v1/health", 200)

    # 2. Models List
    runner.assert_test(2, "List Available Models", "GET", "/api/v1/models", 200)

    # 3. Model Metrics
    runner.assert_test(
        3, "Model Evaluation Metrics", "GET", "/api/v1/models/metrics", 200
    )

    # 4. Ingest Flow Observation (Normal Traffic)
    benign_flow = {
        "source_id": "sensor-cli-01",
        "timestamp": "2026-10-26T10:00:00Z",
        "window_seconds": 10.0,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": {name: 50.0 for name in FEATURE_NAMES},
        "target_ip": "192.168.1.100",
    }
    runner.assert_test(
        4,
        "Ingest Normal Traffic Flow",
        "POST",
        "/api/v1/traffic/flows",
        201,
        payload=benign_flow,
    )

    # 5. Ingest Flow Observation (DDoS Attack Scenario - Exceeds PPS & SYN limits)
    ddos_flow = {
        "source_id": "sensor-cli-02",
        "timestamp": "2026-10-26T10:00:05Z",
        "window_seconds": 10.0,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": {
            name: (8500.0 if "pkt" in name or "flow" in name else 1000.0)
            for name in FEATURE_NAMES
        },
        "target_ip": "192.168.1.150",
    }
    runner.assert_test(
        5,
        "Ingest High-Volume Threat Flow",
        "POST",
        "/api/v1/traffic/flows",
        201,
        payload=ddos_flow,
    )

    # 6. Traffic Summary
    runner.assert_test(
        6, "Get Traffic Summary & Series", "GET", "/api/v1/traffic/summary", 200
    )

    # 7. Ad-Hoc Flow Analysis
    analysis_req = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": {name: 25.0 for name in FEATURE_NAMES},
    }
    runner.assert_test(
        7,
        "Ad-Hoc Feature Vector Analysis",
        "POST",
        "/api/v1/detection/analyze",
        200,
        payload=analysis_req,
    )

    # 8. List Alerts
    _, alerts_data = runner.assert_test(
        8, "List Detection Alerts", "GET", "/api/v1/alerts?limit=10", 200
    )

    # 9. List Mitigations
    runner.assert_test(
        9, "List Mitigation Lifecycle States", "GET", "/api/v1/mitigations", 200
    )

    # 10. Simulate Mitigation
    target_alert_id = None
    if isinstance(alerts_data, dict) and alerts_data.get("alerts"):
        target_alert_id = alerts_data["alerts"][0].get("id")

    sim_payload = {
        "target_ip": "192.168.1.150",
        "duration_seconds": 60,
        "alert_id": target_alert_id,
    }
    _, sim_data = runner.assert_test(
        10,
        "Simulate Bounded Mitigation",
        "POST",
        "/api/v1/mitigations/simulate",
        (200, 201),
        payload=sim_payload,
    )

    # 11. Cancel Mitigation
    action_id = sim_data.get("action_id") if isinstance(sim_data, dict) else "unknown"
    runner.assert_test(
        11,
        "Cancel Active Mitigation Action",
        "POST",
        f"/api/v1/mitigations/{action_id}/cancel",
        200,
    )

    # 12. Emergency Disable Toggle
    runner.assert_test(
        12,
        "Emergency Disable Safety Override",
        "POST",
        "/api/v1/mitigations/disable",
        200,
    )
    # Restore mitigation safety gate after testing emergency disable
    runner.request("POST", "/api/v1/mitigations/disable?enable=true")

    # 13. Audit Records (JSON & CSV)
    runner.assert_test(
        13, "Get Operator Audit Records (JSON)", "GET", "/api/v1/audit?format=json", 200
    )
    runner.assert_test(
        14, "Get Operator Audit Records (CSV)", "GET", "/api/v1/audit?format=csv", 200
    )

    # 15. Read Threshold Configuration
    runner.assert_test(
        15, "Read Detection Thresholds", "GET", "/api/v1/config/thresholds", 200
    )

    # 16. Update Threshold Configuration
    update_cfg = {
        "pps_threshold": 6000.0,
        "bps_threshold": 12000000.0,
        "syn_pps_threshold": 600.0,
        "rf_probability_threshold": 0.80,
    }
    runner.assert_test(
        16,
        "Update Detection Thresholds",
        "PATCH",
        "/api/v1/config/thresholds",
        200,
        payload=update_cfg,
    )

    # Summary
    total = runner.passed + runner.failed
    print("\n ------------------------------------------------------------------------")
    if runner.failed == 0:
        print(
            f" {GREEN}{BOLD}RESULT: ALL {total} API CONTRACT CHECKS PASSED SUCCESSFULLY!{RESET}\n"
        )
    else:
        print(f" {RED}{BOLD}RESULT: {runner.failed}/{total} CHECKS FAILED.{RESET}\n")

    # Reset emergency disabled state for clean test isolation
    set_emergency_disabled(False)

    return runner.failed == 0


def main() -> None:
    # Load .env so API_AUTH_TOKEN is automatically used if present
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")

    default_token = os.environ.get("API_AUTH_TOKEN", "dev-only-change-me")

    parser = argparse.ArgumentParser(description="Test all SENTRIX backend REST APIs")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of SENTRIX FastAPI backend",
    )
    parser.add_argument(
        "--token", default=default_token, help="API authentication Bearer token"
    )
    args = parser.parse_args()

    # Verify if backend is reachable
    print(f"Checking connectivity to {args.url}/api/v1/health ...")
    try:
        req = urllib.request.Request(
            f"{args.url}/api/v1/health",
            headers={"Authorization": f"Bearer {args.token}"},
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status != 200:
                print(f"{YELLOW}Warning: Server returned status {resp.status}{RESET}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"{YELLOW}Could not connect to {args.url}: {exc}{RESET}")
        print(
            f"\n{BOLD}TIP:{RESET} Start the backend server first in another terminal:"
        )
        print(
            f"  {CYAN}python -m uvicorn backend.app.main:app --reload --port 8000{RESET}\n"
        )
        sys.exit(1)

    success = run_all_tests(args.url, args.token)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
