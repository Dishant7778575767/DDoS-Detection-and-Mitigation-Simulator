#!/usr/bin/env python3
"""SENTRIX Lab Traffic Metrics Collector.

Monitors an isolated network interface (e.g. 'sentrix0') in the Linux lab environment,
aggregates flow metrics over a short time window, computes Feature Schema 1.0.0 features,
and submits observations to the SENTRIX ingestion API.

Features:
- Live Linux Interface Polling: Reads delta statistics from `/proc/net/dev`.
- Graceful Fallback / Probe Mode: If run on Windows or outside the Linux lab namespace,
  falls back to safe probe mode with clear diagnostic messaging.
- Strict Feature Schema 1.0.0 compatibility.
- Standard library only: No external C-dependencies or libpcap required.

Usage:
    python collector/lab_collector.py --interface sentrix0 \\
                                      --api-url http://127.0.0.1:8000 \\
                                      --interval 2.0 \\
                                      --token dev-only-change-me \\
                                      --target-ip 10.200.0.50
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Standard Schema 1.0.0 Feature List
FEATURE_SCHEMA_VERSION = "1.0.0"
DEFAULT_INTERFACE = "sentrix0"
DEFAULT_TARGET_IP = "10.200.0.50"


class InterfaceStats:
    """Snapshot of interface counters."""

    def __init__(self, rx_bytes: int, rx_packets: int, tx_bytes: int, tx_packets: int) -> None:
        self.rx_bytes = rx_bytes
        self.rx_packets = rx_packets
        self.tx_bytes = tx_bytes
        self.tx_packets = tx_packets
        self.timestamp = time.perf_counter()


def read_proc_net_dev(interface: str) -> InterfaceStats | None:
    """Read interface bytes and packets from /proc/net/dev on Linux."""
    proc_path = Path("/proc/net/dev")
    if not proc_path.exists():
        return None

    try:
        content = proc_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith(f"{interface}:"):
                parts = line.split(":", 1)[1].split()
                # Linux /proc/net/dev format:
                # rx_bytes, rx_packets, rx_errs, rx_drop, rx_fifo, rx_frame, rx_compressed, rx_multicast,
                # tx_bytes, tx_packets, ...
                rx_bytes = int(parts[0])
                rx_packets = int(parts[1])
                tx_bytes = int(parts[8])
                tx_packets = int(parts[9])
                return InterfaceStats(rx_bytes, rx_packets, tx_bytes, tx_packets)
    except (OSError, ValueError, IndexError):
        return None
    return None


def calculate_features(
    prev: InterfaceStats,
    curr: InterfaceStats,
    delta_time: float,
) -> dict[str, float]:
    """Calculate Schema 1.0.0 flow features from delta interface counters."""
    rx_pkts_delta = max(0, curr.rx_packets - prev.rx_packets)
    rx_bytes_delta = max(0, curr.rx_bytes - prev.rx_bytes)
    tx_pkts_delta = max(0, curr.tx_packets - prev.tx_packets)

    fwd_pps = float(rx_pkts_delta / delta_time) if delta_time > 0 else 0.0
    flow_bps = float(rx_bytes_delta / delta_time) if delta_time > 0 else 0.0

    avg_pkt_len = float(rx_bytes_delta / rx_pkts_delta) if rx_pkts_delta > 0 else 64.0
    iat_avg_us = float((delta_time / rx_pkts_delta) * 1_000_000.0) if rx_pkts_delta > 0 else 1000.0

    return {
        "Total Length of Fwd Packets": float(rx_bytes_delta),
        "Bwd Packet Length Max": min(avg_pkt_len * 1.5, 1460.0),
        "Flow Bytes/s": round(flow_bps, 2),
        "Fwd IAT Total": round(iat_avg_us * rx_pkts_delta, 2),
        "Bwd IAT Total": round(iat_avg_us * max(1, tx_pkts_delta), 2),
        "Fwd PSH Flags": 0.0,
        "Fwd Packets/s": round(fwd_pps, 2),
        "FIN Flag Count": 0.0,
        "Fwd Avg Bytes/Bulk": 0.0,
        "Bwd Avg Bulk Rate": 0.0,
        "Subflow Fwd Packets": float(rx_pkts_delta),
        "Init_Win_bytes_forward": 29200.0,
        "Active Mean": 10000.0,
        "Idle Mean": 0.0,
    }


def generate_probe_features(iteration: int) -> dict[str, float]:
    """Generate safe, bounded baseline flow features in non-Linux or mock environments."""
    # Synthetic clean background traffic: ~150-250 pps, ~15-25 KB/s
    fwd_pps = 150.0 + (iteration % 10) * 10.0
    flow_bps = fwd_pps * 128.0

    return {
        "Total Length of Fwd Packets": flow_bps * 2.0,
        "Bwd Packet Length Max": 128.0,
        "Flow Bytes/s": round(flow_bps, 2),
        "Fwd IAT Total": 20000.0,
        "Bwd IAT Total": 25000.0,
        "Fwd PSH Flags": 0.0,
        "Fwd Packets/s": round(fwd_pps, 2),
        "FIN Flag Count": 0.0,
        "Fwd Avg Bytes/Bulk": 0.0,
        "Bwd Avg Bulk Rate": 0.0,
        "Subflow Fwd Packets": fwd_pps * 2.0,
        "Init_Win_bytes_forward": 29200.0,
        "Active Mean": 12000.0,
        "Idle Mean": 0.0,
    }


def submit_observation(
    api_url: str,
    token: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """Submit flow observation to the SENTRIX FastAPI backend."""
    url = f"{api_url.rstrip('/')}/api/v1/traffic/flows"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as exc:
        try:
            err_data = json.loads(exc.read().decode("utf-8"))
        except (OSError, ValueError):
            err_data = {"error": {"message": str(exc)}}
        return exc.code, err_data
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return 0, {"error": {"message": f"Connection error: {exc}"}}


def run_collector(
    interface: str,
    api_url: str,
    token: str,
    interval: float,
    target_ip: str,
    max_iterations: int | None = None,
) -> int:
    """Main collector monitoring loop."""
    print("=" * 70)
    print("🚀 SENTRIX Lab Traffic Metrics Collector")
    print("=" * 70)
    print(f"Interface:       {interface}")
    print(f"Backend API:     {api_url}")
    print(f"Window Interval: {interval}s")
    print(f"Target Subnet:   {target_ip}")
    print(f"Schema Version:  {FEATURE_SCHEMA_VERSION}")

    # Check live Linux /proc/net/dev availability
    initial_stats = read_proc_net_dev(interface)
    is_live = initial_stats is not None

    if is_live:
        print(f"[STATUS] Linux /proc/net/dev detected. Live interface capture active on '{interface}'.")
    else:
        print(f"[STATUS] Interface '{interface}' or /proc/net/dev not available on host.")
        print("[STATUS] Running in Lab Probe / Fallback Mode (Schema 1.0.0 telemetry).")
    print("-" * 70)

    last_stats = initial_stats or InterfaceStats(0, 0, 0, 0)
    iteration = 0
    submitted_count = 0

    try:
        while max_iterations is None or iteration < max_iterations:
            time.sleep(interval)
            iteration += 1

            if is_live:
                curr_stats = read_proc_net_dev(interface)
                if curr_stats:
                    dt = curr_stats.timestamp - last_stats.timestamp
                    features = calculate_features(last_stats, curr_stats, dt)
                    last_stats = curr_stats
                else:
                    features = generate_probe_features(iteration)
            else:
                features = generate_probe_features(iteration)

            now_iso = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = {
                "source_id": f"lab-collector:{interface}",
                "timestamp": now_iso,
                "window_seconds": interval,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "features": features,
                "target_ip": target_ip,
                "target_port": 80,
            }

            status_code, response = submit_observation(api_url, token, payload)
            if status_code in (200, 201):
                submitted_count += 1
                decision = response.get("policy_decision", "monitor")
                pred = response.get("prediction", "benign")
                score = response.get("score", 0.0)
                print(
                    f"[{now_iso}] Batch #{iteration:03d} | PPS: {features['Fwd Packets/s']:6.1f} | "
                    f"BPS: {features['Flow Bytes/s']:8.1f} | Prediction: {pred:10s} (Score: {score:.3f}) | Decision: {decision}"
                )
            else:
                err = response.get("error", {}).get("message", "Unknown error")
                print(f"[{now_iso}] Batch #{iteration:03d} | Failed to submit (HTTP {status_code}): {err}")

    except KeyboardInterrupt:
        print("\n[STOPPED] Collector loop terminated by operator.")

    print(f"\n[SUMMARY] Total batches submitted: {submitted_count}/{iteration}")
    return 0


def main() -> None:
    """CLI Argument Parser and entry point."""
    parser = argparse.ArgumentParser(
        description="SENTRIX Lab Traffic Metrics Collector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--interface",
        default=os.getenv("LAB_INTERFACE", DEFAULT_INTERFACE),
        help="Designated Linux lab interface to monitor",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("SENTRIX_API_URL", "http://127.0.0.1:8000"),
        help="Target SENTRIX FastAPI backend base URL",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("API_AUTH_TOKEN", "dev-only-change-me"),
        help="API authentication bearer token",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Aggregation time-window interval in seconds",
    )
    parser.add_argument(
        "--target-ip",
        default=DEFAULT_TARGET_IP,
        help="Target IP within isolated lab subnet (10.200.0.0/24)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Max iterations to run before stopping (defaults to continuous loop)",
    )

    args = parser.parse_args()
    code = run_collector(
        interface=args.interface,
        api_url=args.api_url,
        token=args.token,
        interval=args.interval,
        target_ip=args.target_ip,
        max_iterations=args.iterations,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
