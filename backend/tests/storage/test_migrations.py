import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def test_initial_migration_is_repeatable_and_uses_configured_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database_path = tmp_path / "nested" / "sentrix.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./nested/sentrix.db")
    get_settings.cache_clear()
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(config_path))

    command.upgrade(config, "head")
    get_settings.cache_clear()
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert revision == ("0001_initial",)
