"""Unit tests for mitigation lifecycle state machine."""

import pytest

from app.mitigation.lifecycle import (
    IllegalTransitionError,
    is_terminal_state,
    validate_lifecycle_transition,
)


def test_valid_lifecycle_transitions() -> None:
    """Ensure legal state machine transitions pass validation."""
    validate_lifecycle_transition("proposed", "simulated")
    validate_lifecycle_transition("proposed", "applied")
    validate_lifecycle_transition("simulated", "cancelled")
    validate_lifecycle_transition("simulated", "expired")
    validate_lifecycle_transition("active", "cancelled")
    validate_lifecycle_transition("active", "expired")
    validate_lifecycle_transition("applied", "cancelled")
    validate_lifecycle_transition("applied", "expired")
    validate_lifecycle_transition("applied", "recovered")


def test_invalid_lifecycle_transitions_raise_error() -> None:
    """Ensure illegal transitions raise IllegalTransitionError."""
    # Terminal states cannot transition further
    with pytest.raises(IllegalTransitionError):
        validate_lifecycle_transition("cancelled", "applied")

    with pytest.raises(IllegalTransitionError):
        validate_lifecycle_transition("expired", "simulated")

    # Cannot skip directly from proposed to expired
    with pytest.raises(IllegalTransitionError):
        validate_lifecycle_transition("proposed", "expired")


def test_terminal_states() -> None:
    """Check identification of terminal lifecycle states."""
    assert is_terminal_state("cancelled") is True
    assert is_terminal_state("expired") is True
    assert is_terminal_state("failed") is True
    assert is_terminal_state("recovered") is True
    assert is_terminal_state("proposed") is False
    assert is_terminal_state("simulated") is False
