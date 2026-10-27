"""Virtual mitigation effect model and lifecycle management.

Part of Phase 8 (Work Package 8.2): Models virtual rate-limiting, attack reduction,
and legitimate traffic collateral impact without touching host firewalls or networking.
Tracks virtual start ticks, durations, expiry ticks, and cancellation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MitigationStatus = Literal["active", "expired", "cancelled"]


class VirtualMitigation(BaseModel):
    """A virtual mitigation action operating solely within the simulator."""

    model_config = {"extra": "forbid"}

    action_id: str = Field(..., description="Unique simulated mitigation identifier")
    target_ip: str = Field(default="192.168.1.100", description="Virtual target IP")
    target_port: int | None = Field(default=80, description="Virtual target port")
    action_type: str = Field(
        default="simulate_rate_limit", description="Simulated mitigation action type"
    )
    start_tick: int = Field(
        ..., ge=0, description="Virtual tick when action takes effect"
    )
    duration_ticks: int = Field(
        default=15, ge=1, le=3600, description="Duration in ticks before expiration"
    )
    expiry_tick: int = Field(
        ..., ge=0, description="Virtual tick when action automatically expires"
    )
    attack_reduction_rate: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Fraction of attack traffic blocked by this virtual rule (e.g. 0.95 = 95%)",
    )
    collateral_drop_rate: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Fraction of legitimate traffic inadvertently dropped as collateral damage (e.g. 0.02 = 2%)",
    )
    status: MitigationStatus = Field(
        default="active", description="Current lifecycle status of the virtual action"
    )
    cancelled_at_tick: int | None = Field(
        default=None, description="Tick at which the action was manually cancelled"
    )

    def is_active(self, tick: int) -> bool:
        """Check if this action actively filters traffic at the specified virtual tick."""
        return self.status == "active" and (self.start_tick <= tick < self.expiry_tick)

    def check_expiry(self, tick: int) -> bool:
        """Advance action status to expired if the virtual clock reached expiry_tick."""
        if self.status == "active" and tick >= self.expiry_tick:
            self.status = "expired"
            return True
        return False

    def cancel(self, tick: int) -> bool:
        """Cancel this action early at the given tick."""
        if self.status == "active":
            self.status = "cancelled"
            self.cancelled_at_tick = tick
            return True
        return False


class MitigationEffectManager:
    """Manages active, expired, and cancelled virtual mitigations across simulation ticks."""

    def __init__(self) -> None:
        self._actions: dict[str, VirtualMitigation] = {}

    @property
    def all_actions(self) -> list[VirtualMitigation]:
        """Return all recorded virtual mitigations."""
        return list(self._actions.values())

    def get_active_actions(self, tick: int) -> list[VirtualMitigation]:
        """Return all mitigations that are actively filtering traffic at the given tick."""
        return [a for a in self._actions.values() if a.is_active(tick)]

    def add_mitigation(self, mitigation: VirtualMitigation) -> None:
        """Register a new virtual mitigation."""
        self._actions[mitigation.action_id] = mitigation

    def cancel_mitigation(self, action_id: str, tick: int) -> VirtualMitigation | None:
        """Cancel an active virtual mitigation."""
        action = self._actions.get(action_id)
        if action and action.cancel(tick):
            return action
        return None

    def advance_tick(self, tick: int) -> list[VirtualMitigation]:
        """Check all actions for expiration at the new tick and return newly expired actions."""
        newly_expired: list[VirtualMitigation] = []
        for action in self._actions.values():
            if action.check_expiry(tick):
                newly_expired.append(action)
        return newly_expired
