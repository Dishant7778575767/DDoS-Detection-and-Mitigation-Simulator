"""Abstract base class for mitigation adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MitigationAdapter(ABC):
    """Abstract interface defining the mitigation contract."""

    @abstractmethod
    def apply_rate_limit(
        self,
        action_id: str,
        target_ip: str,
        rate_limit_pps: int,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Apply or simulate a rate-limiting rule for a target IP."""

    @abstractmethod
    def cancel_rate_limit(
        self,
        action_id: str,
        target_ip: str,
    ) -> dict[str, Any]:
        """Remove or cancel an active rate-limiting rule."""
