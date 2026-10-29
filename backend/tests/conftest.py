"""Global pytest fixtures and test setup for SENTRIX backend."""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

# Ensure repository root is in sys.path for scripts and package imports
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Isolate test suite from remote cloud database: force local sqlite
os.environ["DATABASE_URL"] = "sqlite:///./sentrix.db"
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token-sentrix")

from app.core.config import get_settings

get_settings.cache_clear()

from app.main import app
from app.safety.gate import set_emergency_disabled


@pytest.fixture(autouse=True)
def reset_safety_gate_state() -> Generator[None, None, None]:
    """Ensure emergency disable, settings cache, and app dependency overrides are reset before and after every test."""
    get_settings.cache_clear()
    set_emergency_disabled(False)
    app.dependency_overrides.clear()
    yield
    set_emergency_disabled(False)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
