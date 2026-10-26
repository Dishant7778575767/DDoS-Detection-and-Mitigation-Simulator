"""TTL expiration worker and verification for Linux lab enforcement rules."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import Any

from enforcement.agent import CleanupVerificationError, LinuxEnforcementAgent

logger = logging.getLogger("sentrix.enforcement.expiry")


class EnforcementExpiryManager:
    """Manages lifecycle expiration of active lab enforcement rules."""

    def __init__(
        self,
        agent: LinuxEnforcementAgent,
        on_cleanup_failure: Callable[[str, str], None] | None = None,
    ) -> None:
        self.agent = agent
        self.on_cleanup_failure = on_cleanup_failure
        self._tracked_rules: dict[str, dict[str, Any]] = {}

    def track_action(
        self,
        action_id: str,
        target_ip: str,
        duration_seconds: int,
        applied_at_utc: datetime.datetime | None = None,
    ) -> None:
        """Register a newly applied rule for TTL tracking."""
        base_time = applied_at_utc or datetime.datetime.now(datetime.timezone.utc)
        expires_at = base_time + datetime.timedelta(seconds=duration_seconds)
        self._tracked_rules[action_id] = {
            "action_id": action_id,
            "target_ip": target_ip,
            "expires_at": expires_at,
            "status": "applied",
        }

    def check_and_expire(
        self, now_dt: datetime.datetime | None = None
    ) -> list[dict[str, Any]]:
        """Scan tracked rules, remove expired entries from nftables, and verify removal."""
        now = now_dt or datetime.datetime.now(datetime.timezone.utc)
        expired_results: list[dict[str, Any]] = []

        for action_id, info in list(self._tracked_rules.items()):
            if info["status"] != "applied":
                continue

            if now >= info["expires_at"]:
                target_ip = info["target_ip"]
                try:
                    # Attempt cleanup and verification
                    self.agent.cancel_rate_limit(action_id, target_ip)
                    info["status"] = "expired"
                    expired_results.append(
                        {
                            "action_id": action_id,
                            "target_ip": target_ip,
                            "status": "expired",
                            "cleanup_verified": True,
                        }
                    )
                except (
                    CleanupVerificationError,
                    RuntimeError,
                    OSError,
                    ValueError,
                ) as exc:
                    logger.critical(
                        "TC-10 Cleanup failure for action '%s': %s", action_id, exc
                    )
                    info["status"] = "failed"
                    if self.on_cleanup_failure:
                        self.on_cleanup_failure(action_id, str(exc))
                    expired_results.append(
                        {
                            "action_id": action_id,
                            "target_ip": target_ip,
                            "status": "failed",
                            "cleanup_verified": False,
                            "error": str(exc),
                        }
                    )

        return expired_results
