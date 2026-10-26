"""Global pytest fixtures and test setup for SENTRIX backend."""

from collections.abc import Generator

import pytest

from app.safety.gate import set_emergency_disabled


@pytest.fixture(autouse=True)
def reset_safety_gate_state() -> Generator[None, None, None]:
    """Ensure emergency disable is reset before and after every test."""
    set_emergency_disabled(False)
    yield
    set_emergency_disabled(False)
