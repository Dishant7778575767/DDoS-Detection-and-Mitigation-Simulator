#!/usr/bin/env python3
"""SENTRIX Bounded Demonstration Traffic Generator (Phase 5 / TC-14).

Generates bounded synthetic traffic flow observations for testing PRD scenarios:
- TC-01: Normal traffic (Neither signal triggers; monitor)
- TC-02: Abnormal burst (Threshold exceeded; alert only)
- TC-03: Suspected SYN flood (Both signals trigger; request mitigation)
- TC-04: Threshold signal only (Alert only; no mitigation)
- TC-13: ML signal only (Alert only; no mitigation)

All generated flows are strictly marked with demonstration provenance ('demo-generator:').

Usage:
    python scripts/send_test_traffic.py [--scenario normal|burst|syn_flood|threshold_only|ml_only|all]
                                        [--count 1] [--target-ip 192.168.1.150]
                                        [--api-url http://127.0.0.1:8000]
                                        [--token dev-only-change-me]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT_DIR / "data" / "fixtures" / "test_flows.json"

# ANSI Colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_fixtures() -> dict[str, Any]:
    """Load deterministic test flow fixtures."""
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(f"Fixture file not found: {FIXTURE_PATH}")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def send_flow(
    api_url: str,
    token: str,
    flow_payload: dict[str, Any],
) -> tuple[int, dict[str, Any], float]:
    """Send flow observation to the SENTRIX ingestion endpoint."""
    url = f"{api_url.rstrip('/')}/api/v1/traffic/flows"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    data = json.dumps(flow_payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            elapsed = (time.perf_counter() - t0) * 1000
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body, elapsed
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"error": str(exc)}
        return exc.code, body, elapsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        return 0, {"error": str(exc)}, elapsed


def run_generator(
    scenario_key: str,
    count: int,
    target_ip: str | None,
    api_url: str,
    token: str,
    delay: float = 0.5,
) -> bool:
    fixtures = load_fixtures()["scenarios"]
    scenarios_to_run = (
        list(fixtures.keys())
        if scenario_key == "all"
        else [k for k in fixtures if scenario_key in k]
    )

    if not scenarios_to_run:
        print(
            f"{RED}Error: Unknown scenario '{scenario_key}'. Available: {list(fixtures.keys())}{RESET}"
        )
        return False

    print(
        f"\n{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(
        f"{BOLD}{CYAN}            SENTRIX BOUNDED TRAFFIC GENERATOR (DEMO PROVENANCE)         {RESET}"
    )
    print(
        f"{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(f" Target Endpoint: {BOLD}{api_url}/api/v1/traffic/flows{RESET}")
    print(f" Data Provenance: {BOLD}demo-generator:* (Not live telemetry){RESET}")
    print(" ------------------------------------------------------------------------\n")

    all_passed = True

    for skey in scenarios_to_run:
        scenario = fixtures[skey]
        print(f"{BOLD}{CYAN}Scenario:{RESET} {scenario['name']}")
        print(f"  Description:     {DIM}{scenario['description']}{RESET}")
        print(
            f"  Expected Policy: {YELLOW}{scenario['expected_policy']}{RESET} | Alert Expected: {scenario['expected_alert']}"
        )

        for i in range(count):
            now_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = {
                "source_id": f"{scenario['source_id']}:{i + 1:03d}",
                "timestamp": now_ts,
                "window_seconds": scenario["window_seconds"],
                "feature_schema_version": "1.0.0",
                "features": scenario["features"],
                "target_ip": target_ip or scenario["target_ip"],
            }

            status, body, elapsed = send_flow(api_url, token, payload)
            if status == 201:
                det = body.get("detection", {})
                pol_decision = det.get("policy_decision", "unknown")
                ml_score = det.get("score", 0.0)
                alert_created = body.get("alert_created", False)
                matches_policy = pol_decision == scenario["expected_policy"]

                status_color = GREEN if matches_policy else YELLOW
                print(
                    f"  [{i + 1}/{count}] {GREEN}HTTP 201{RESET} "
                    f"Policy: {status_color}{pol_decision:<18}{RESET} "
                    f"ML Score: {ml_score:.4f} "
                    f"Alert: {'YES' if alert_created else 'NO '} "
                    f"{DIM}({elapsed:5.1f}ms){RESET}"
                )
            else:
                all_passed = False
                print(f"  [{i + 1}/{count}] {RED}HTTP {status} FAILED:{RESET} {body}")

            if i < count - 1:
                time.sleep(delay)
        print()

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SENTRIX Demonstration Traffic Generator"
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["all", "normal", "burst", "syn_flood", "threshold_only", "ml_only"],
        help="Demonstration scenario to execute",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of flow packets to generate per scenario",
    )
    parser.add_argument(
        "--target-ip", default=None, help="Override destination target IP"
    )
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000", help="FastAPI backend URL"
    )
    parser.add_argument(
        "--token", default="dev-only-change-me", help="API authentication Bearer token"
    )
    parser.add_argument(
        "--delay", type=float, default=0.2, help="Seconds delay between packets"
    )
    args = parser.parse_args()

    success = run_generator(
        scenario_key=args.scenario,
        count=args.count,
        target_ip=args.target_ip,
        api_url=args.api_url,
        token=args.token,
        delay=args.delay,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
