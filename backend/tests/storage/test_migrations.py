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

    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        columns = connection.execute("PRAGMA table_info(observations)").fetchall()
        cf_columns = connection.execute(
            "PRAGMA table_info(cloudfront_kinesis_events)"
        ).fetchall()
        kp_columns = connection.execute(
            "PRAGMA table_info(kinesis_checkpoints)"
        ).fetchall()
    finally:
        connection.close()

    assert revision == ("0003_aws_cloudfront_kinesis",)
    assert "target_ip" in {column[1] for column in columns}
    assert "request_id" in {column[1] for column in cf_columns}
    assert "last_sequence_number" in {column[1] for column in kp_columns}
