"""Linux lab mitigation adapter executing safe, restricted nftables enforcement."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path for enforcement module import
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from enforcement.agent import LinuxEnforcementAgent
from enforcement.rules import (
    validate_enforcement_bounds,
    validate_lab_target,
)

from app.mitigation.base import MitigationAdapter

APPROVAL_FILE_PATH = (
    Path(__file__).resolve().parents[3] / "enforcement" / "approval.json"
)


class LabAuthorizationError(PermissionError):
    """Raised when lab enforcement is attempted without explicit authorization."""


def verify_lab_authorization(approval_path: Path | None = None) -> dict[str, Any]:
    """Verify that lab enforcement is formally approved and valid."""
    path = approval_path or APPROVAL_FILE_PATH
    if not path.exists():
        raise LabAuthorizationError(
            f"Lab approval manifest not found at '{path}'. Linux lab enforcement is forbidden."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise LabAuthorizationError(
            f"Failed to read lab approval manifest: {exc}"
        ) from exc

    if not data.get("approved") or not data.get("enforcement_enabled"):
        raise LabAuthorizationError(
            "Lab enforcement is disabled or not approved in approval manifest."
        )

    # Check expiration if present
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.datetime.now(datetime.timezone.utc) >= exp_dt:
                raise LabAuthorizationError(
                    f"Lab approval expired at {expires_at}. Enforcement is halted."
                )
        except ValueError:
            pass

    return data


class LinuxLabAdapter(MitigationAdapter):
    """Restricted Linux enforcement adapter operating strictly in the isolated lab namespace."""

    def __init__(
        self,
        agent: LinuxEnforcementAgent | None = None,
        dry_run: bool = True,
        approval_path: Path | None = None,
    ) -> None:
        self.approval_path = approval_path
        self.dry_run = dry_run
        # Verify approval at instantiation
        self.approval_manifest = verify_lab_authorization(self.approval_path)
        self.agent = agent or LinuxEnforcementAgent(dry_run=dry_run)
        self.agent.initialize()

    def apply_rate_limit(
        self,
        action_id: str,
        target_ip: str,
        rate_limit_pps: int,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Apply bounded nftables rate-limit in the lab interface."""
        # 1. Re-verify lab authorization gate
        verify_lab_authorization(self.approval_path)

        # 2. Strict target validation (10.200.0.0/24, no protected hosts)
        validated_ip = validate_lab_target(target_ip)

        # 3. Parameter safety bounds
        validate_enforcement_bounds(rate_limit_pps, duration_seconds)

        # 4. Delegate to agent
        return self.agent.apply_rate_limit(
            action_id=action_id,
            target_ip=validated_ip,
            rate_limit_pps=rate_limit_pps,
            duration_seconds=duration_seconds,
        )

    def cancel_rate_limit(
        self,
        action_id: str,
        target_ip: str,
    ) -> dict[str, Any]:
        """Cancel nftables rate-limit and verify removal (TC-10)."""
        # Re-verify authorization
        verify_lab_authorization(self.approval_path)
        validated_ip = validate_lab_target(target_ip)

        return self.agent.cancel_rate_limit(
            action_id=action_id,
            target_ip=validated_ip,
        )
