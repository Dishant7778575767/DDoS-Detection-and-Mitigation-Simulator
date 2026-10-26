"""Cooldown tracker to prevent alert and mitigation flapping."""

from __future__ import annotations

import time

# In-memory tracking of recent alert timestamps per target/source
_alert_cooldowns: dict[str, float] = {}
DEFAULT_COOLDOWN_SECONDS: float = 30.0


def is_in_cooldown(
    target: str, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
) -> bool:
    """Check if the given target is currently in a cooldown window."""
    now = time.time()
    last_time = _alert_cooldowns.get(target, 0.0)
    return now - last_time < cooldown_seconds


def record_action_timestamp(target: str) -> None:
    """Record an action timestamp for cooldown calculation."""
    _alert_cooldowns[target] = time.time()


def reset_cooldowns() -> None:
    """Clear all active cooldown records."""
    _alert_cooldowns.clear()
