#!/usr/bin/env python3
"""SENTRIX Prepared-File Flow Replay Tool (Phase 5 / TC-14).

Replays recorded flow observations from a prepared CSV dataset through the
runtime ingestion pipeline (POST /api/v1/traffic/flows).

All replayed flows are strictly labeled with demonstration provenance ('demo-replay:').

Usage:
    python scripts/replay_dataset.py [--file data/processed/test.csv]
                                     [--limit 50] [--delay 0.1]
                                     [--api-url http://127.0.0.1:8000]
                                     [--token dev-only-change-me]
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.features.definitions import FEATURE_NAMES

# ANSI Colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def replay_file(
    file_path: Path,
    limit: int,
    delay: float,
    api_url: str,
    token: str,
) -> bool:
    if not file_path.exists():
        print(f"{RED}Error: File not found: {file_path}{RESET}")
        return False

    print(
        f"\n{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(
        f"{BOLD}{CYAN}             SENTRIX PREPARED-FILE FLOW REPLAY (DEMO PROVENANCE)        {RESET}"
    )
    print(
        f"{BOLD}{CYAN}========================================================================{RESET}"
    )
    print(f" Source File:     {BOLD}{file_path}{RESET}")
    print(f" Target Endpoint: {BOLD}{api_url}/api/v1/traffic/flows{RESET}")
    print(
        f" Data Provenance: {BOLD}demo-replay:{file_path.name}:* (Not live telemetry){RESET}"
    )
    print(" ------------------------------------------------------------------------\n")

    url = f"{api_url.rstrip('/')}/api/v1/traffic/flows"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    sent_count = 0
    alert_count = 0
    t_start = time.perf_counter()

    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if sent_count >= limit:
                break

            # Extract features according to FEATURE_NAMES
            features: dict[str, float] = {}
            for name in FEATURE_NAMES:
                val = row.get(name, 0.0)
                try:
                    features[name] = float(val)
                except (ValueError, TypeError):
                    features[name] = 0.0

            now_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = {
                "source_id": f"demo-replay:{file_path.name}:row_{idx + 1:05d}",
                "timestamp": now_ts,
                "window_seconds": 10.0,
                "feature_schema_version": "1.0.0",
                "features": features,
                "target_ip": "192.168.1.180",
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    det = resp_data.get("detection", {})
                    pol = resp_data.get("policy_decision") or det.get(
                        "policy_decision", "unknown"
                    )
                    score = (
                        resp_data.get("score")
                        if resp_data.get("score") is not None
                        else det.get("score", 0.0)
                    )
                    has_alert = resp_data.get(
                        "alert_created", bool(resp_data.get("alert_id"))
                    )
                    if has_alert:
                        alert_count += 1

                    pol_color = (
                        RED
                        if pol == "request_mitigation"
                        else (YELLOW if pol == "alert" else GREEN)
                    )
                    print(
                        f"  Row {idx + 1:04d} -> {GREEN}HTTP 201{RESET} "
                        f"Policy: {pol_color}{pol:<18}{RESET} "
                        f"ML Score: {score:.4f} "
                        f"Alert: {'YES' if has_alert else 'NO '}"
                    )
                    sent_count += 1
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                json.JSONDecodeError,
            ) as exc:
                print(f"  Row {idx + 1:04d} -> {RED}Replay error:{RESET} {exc}")
                return False

            if delay > 0 and sent_count < limit:
                time.sleep(delay)

    total_time = time.perf_counter() - t_start
    print(
        f"\n{GREEN}{BOLD}Replay complete:{RESET} {sent_count} flows replayed in {total_time:.2f}s ({alert_count} alerts generated).\n"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="SENTRIX Prepared-File Flow Replay")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/processed/test.csv"),
        help="Path to CSV dataset to replay",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Maximum number of flows to replay"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="Delay between replayed flows (seconds)",
    )
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000", help="FastAPI backend URL"
    )
    parser.add_argument(
        "--token", default="dev-only-change-me", help="API authentication Bearer token"
    )
    args = parser.parse_args()

    # Fallback to sample file if test.csv does not exist
    target_file = args.file
    if not target_file.exists():
        print(
            f"{YELLOW}Warning: {target_file} not found. Checking data/fixtures/ ...{RESET}"
        )
        sample_csv = ROOT_DIR / "data" / "fixtures" / "sample_test.csv"
        if sample_csv.exists():
            target_file = sample_csv
        else:
            print(f"{RED}Error: Neither {args.file} nor {sample_csv} exists.{RESET}")
            sys.exit(1)

    success = replay_file(
        file_path=target_file,
        limit=args.limit,
        delay=args.delay,
        api_url=args.api_url,
        token=args.token,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
