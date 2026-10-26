"""Backend Safety Gate enforcing bounds, protected targets, authorization, and simulation mode."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from app.policy.allowlist import is_protected_target


@dataclass
class SafetyGateResult:
    """Outcome of Safety Gate validation."""

    allowed: bool
    rejection_reason: str | None = None


# Operational safety boundaries
MIN_RATE_LIMIT_PPS: int = 100
MAX_RATE_LIMIT_PPS: int = 50_000
MIN_DURATION_SECONDS: int = 10
MAX_DURATION_SECONDS: int = 300
MAX_CONCURRENT_MITIGATIONS: int = 100

# Emergency disable state (can be toggled via emergency disable endpoint)
_emergency_disable_active: bool = False


def is_emergency_disabled() -> bool:
    """Return whether the emergency disable switch is active."""
    return _emergency_disable_active


def set_emergency_disabled(disabled: bool) -> None:
    """Toggle the emergency disable switch."""
    global _emergency_disable_active
    _emergency_disable_active = disabled


def validate_safety_gate(
    target_ip: str | None,
    rate_limit_pps: int,
    duration_seconds: int,
    current_active_count: int = 0,
    mitigation_mode: str = "simulation",
) -> SafetyGateResult:
    """Enforce fail-closed safety checks before allowing any mitigation action."""
    # 1. Check emergency disable switch
    if _emergency_disable_active:
        return SafetyGateResult(
            allowed=False,
            rejection_reason="Emergency disable is currently active. All mitigation requests are blocked.",
        )

    # 2. Validate target IP presence and validity
    if not target_ip or not target_ip.strip():
        return SafetyGateResult(
            allowed=False,
            rejection_reason="Target IP address is required for mitigation.",
        )

    target_cleaned = target_ip.strip()
    try:
        ipaddress.ip_address(target_cleaned)
    except ValueError:
        return SafetyGateResult(
            allowed=False,
            rejection_reason=f"Target '{target_cleaned}' is not a valid IPv4 or IPv6 address.",
        )

    # 3. Check protected target allowlist
    if is_protected_target(target_cleaned):
        return SafetyGateResult(
            allowed=False,
            rejection_reason=f"Target '{target_cleaned}' is a protected infrastructure address and cannot be mitigated.",
        )

    # 4. Check bounded parameters
    if rate_limit_pps < MIN_RATE_LIMIT_PPS or rate_limit_pps > MAX_RATE_LIMIT_PPS:
        return SafetyGateResult(
            allowed=False,
            rejection_reason=(
                f"Rate limit {rate_limit_pps} pps is outside allowed safety bounds "
                f"[{MIN_RATE_LIMIT_PPS}, {MAX_RATE_LIMIT_PPS}]."
            ),
        )

    if (
        duration_seconds < MIN_DURATION_SECONDS
        or duration_seconds > MAX_DURATION_SECONDS
    ):
        return SafetyGateResult(
            allowed=False,
            rejection_reason=(
                f"Duration {duration_seconds}s is outside allowed safety bounds "
                f"[{MIN_DURATION_SECONDS}, {MAX_DURATION_SECONDS}]."
            ),
        )

    # 5. Check concurrency limit
    if current_active_count >= MAX_CONCURRENT_MITIGATIONS:
        return SafetyGateResult(
            allowed=False,
            rejection_reason=(
                f"Maximum concurrent mitigations ({MAX_CONCURRENT_MITIGATIONS}) exceeded. "
                "Request rejected."
            ),
        )

    return SafetyGateResult(allowed=True)
