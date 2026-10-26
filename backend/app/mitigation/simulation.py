"""Simulation mitigation adapter performing no host networking modifications."""

from __future__ import annotations

import time
from typing import Any

from app.mitigation.base import MitigationAdapter


class SimulationAdapter(MitigationAdapter):
    """Safe adapter that records simulated mitigation actions without altering firewall rules."""

    def apply_rate_limit(
        self,
        action_id: str,
        target_ip: str,
        rate_limit_pps: int,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Record simulation outcome."""
        return {
            "action_id": action_id,
            "target_ip": target_ip,
            "rate_limit_pps": rate_limit_pps,
            "duration_seconds": duration_seconds,
            "mode": "simulation",
            "host_networking_modified": False,
            "status": "simulated",
            "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def cancel_rate_limit(
        self,
        action_id: str,
        target_ip: str,
    ) -> dict[str, Any]:
        """Record simulation cancellation."""
        return {
            "action_id": action_id,
            "target_ip": target_ip,
            "mode": "simulation",
            "host_networking_modified": False,
            "status": "cancelled",
            "cancelled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
