"""Unit tests for SENTRIX lab metrics collector."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collector.lab_collector import (
    FEATURE_SCHEMA_VERSION,
    InterfaceStats,
    calculate_features,
    generate_probe_features,
    read_proc_net_dev,
    run_collector,
)


def test_calculate_features_schema_contract() -> None:
    """Ensure calculate_features returns all 14 required Schema 1.0.0 features."""
    prev = InterfaceStats(rx_bytes=1000, rx_packets=10, tx_bytes=500, tx_packets=5)
    curr = InterfaceStats(rx_bytes=2000, rx_packets=20, tx_bytes=1000, tx_packets=10)
    delta_time = 1.0

    features = calculate_features(prev, curr, delta_time)

    assert isinstance(features, dict)
    assert len(features) == 14
    assert features["Total Length of Fwd Packets"] == 1000.0
    assert features["Fwd Packets/s"] == 10.0
    assert features["Flow Bytes/s"] == 1000.0
    assert "Init_Win_bytes_forward" in features
    assert "Subflow Fwd Packets" in features


def test_generate_probe_features() -> None:
    """Ensure probe features generate bounded valid values in mock mode."""
    features = generate_probe_features(iteration=1)
    assert len(features) == 14
    assert features["Fwd Packets/s"] > 0
    assert features["Flow Bytes/s"] > 0


def test_read_proc_net_dev_parsing(tmp_path: Path) -> None:
    """Ensure /proc/net/dev format is parsed correctly."""
    sample_proc_dev = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 123456       10    0    0    0     0          0         0   123456      10    0    0    0     0       0          0
sentrix0: 5000000    25000    0    0    0     0          0         0  1000000   12000    0    0    0     0       0          0
"""
    fake_proc = tmp_path / "proc_net_dev"
    fake_proc.write_text(sample_proc_dev, encoding="utf-8")

    with patch("collector.lab_collector.Path") as mock_path:
        mock_path.return_value = fake_proc
        stats = read_proc_net_dev("sentrix0")

        assert stats is not None
        assert stats.rx_bytes == 5000000
        assert stats.rx_packets == 25000
        assert stats.tx_bytes == 1000000
        assert stats.tx_packets == 12000


def test_run_collector_bounded_run() -> None:
    """Ensure collector monitoring loop runs with max_iterations and handles submissions."""
    with patch(
        "collector.lab_collector.submit_observation",
        return_value=(
            201,
            {
                "policy_decision": "monitor",
                "prediction": "benign",
                "score": 0.05,
            },
        ),
    ):
        code = run_collector(
            interface="sentrix0",
            api_url="http://127.0.0.1:8000",
            token="test-token",
            interval=0.01,
            target_ip="10.200.0.50",
            max_iterations=2,
        )
        assert code == 0
        assert FEATURE_SCHEMA_VERSION == "1.0.0"

