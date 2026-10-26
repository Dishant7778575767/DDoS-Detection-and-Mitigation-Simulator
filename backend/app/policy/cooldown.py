"""Cooldown tracker to prevent alert and mitigation flapping."""

from __future__ import annotations

import time

DEFAULT_COOLDOWN_SECONDS: float = 30.0


class AlertCooldownManager:
    """Manages cooldowns and deduplication for alert targets."""

    def __init__(self, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._history: dict[str, float] = {}

    def check_and_update(
        self, target: str, timestamp: float | None = None
    ) -> tuple[bool, str]:
        """Check if target is in cooldown.

        Returns (is_suppressed, reason).
        If not suppressed, the timestamp is recorded.
        """
        now = timestamp if timestamp is not None else time.time()
        last_time = self._history.get(target)
        if last_time is not None and (now - last_time) < self.cooldown_seconds:
            return (
                True,
                f"Target {target} is in cooldown ({now - last_time:.1f}s < {self.cooldown_seconds:.1f}s)",
            )
        self._history[target] = now
        return False, ""

    def reset(self) -> None:
        """Clear all recorded cooldowns."""
        self._history.clear()


# Default singleton instance for global module convenience
_default_manager = AlertCooldownManager(DEFAULT_COOLDOWN_SECONDS)


def is_in_cooldown(
    target: str, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
) -> bool:
    """Check if the given target is currently in a cooldown window."""
    now = time.time()
    last_time = _default_manager._history.get(target, 0.0)
    return (now - last_time) < cooldown_seconds


def record_action_timestamp(target: str) -> None:
    """Record an action timestamp for cooldown calculation."""
    _default_manager._history[target] = time.time()


def reset_cooldowns() -> None:
    """Clear all active cooldown records."""
    _default_manager.reset()
