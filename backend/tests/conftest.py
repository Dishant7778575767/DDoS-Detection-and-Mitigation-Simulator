"""Global pytest fixtures and test setup for SENTRIX backend."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

# Ensure repository root is in sys.path for enforcement and scripts imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.main import app
from app.safety.gate import set_emergency_disabled


@pytest.fixture(autouse=True)
def reset_safety_gate_state() -> Generator[None, None, None]:
    """Ensure emergency disable and app dependency overrides are reset before and after every test."""
    set_emergency_disabled(False)
    app.dependency_overrides.clear()
    yield
    set_emergency_disabled(False)
    app.dependency_overrides.clear()
