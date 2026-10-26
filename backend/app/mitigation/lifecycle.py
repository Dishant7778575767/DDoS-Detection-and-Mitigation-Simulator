"""State machine enforcing mitigation lifecycle states and transitions."""

from __future__ import annotations


class IllegalTransitionError(ValueError):
    """Raised when an invalid lifecycle state transition is requested."""


VALID_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"simulated", "applied", "failed"},
    "simulated": {"cancelled", "expired"},
    "applied": {"cancelled", "expired", "recovered", "failed"},
    "failed": set(),
    "cancelled": set(),
    "expired": set(),
    "recovered": set(),
}

TERMINAL_STATES: set[str] = {"failed", "cancelled", "expired", "recovered"}


def validate_lifecycle_transition(current_state: str, target_state: str) -> None:
    """Validate that the requested state transition is allowed."""
    allowed = VALID_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise IllegalTransitionError(
            f"Illegal state transition from '{current_state}' to '{target_state}'. "
            f"Allowed next states: {sorted(allowed) if allowed else 'None (terminal state)'}."
        )


def is_terminal_state(state: str) -> bool:
    """Check if the given state is terminal."""
    return state in TERMINAL_STATES
