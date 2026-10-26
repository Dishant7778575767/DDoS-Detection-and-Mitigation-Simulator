#!/usr/bin/env python3
"""SENTRIX SQLite to Supabase PostgreSQL Migration Utility.

Safely and idempotently transfers all operational tables from local SQLite (sentrix.db)
to Supabase PostgreSQL in dependency-safe order:
1. threshold_configs (independent)
2. audit_events (independent)
3. observations (independent)
4. detections (depends on observations.id)
5. alerts (depends on detections.id)
6. mitigations (depends on detections.id)

Features:
- Automatic backup of source sentrix.db to sentrix.db.bak
- Schema synchronization (creates missing tables on target PostgreSQL)
- Idempotent record transfer (skips already-migrated IDs on re-runs)
- PostgreSQL auto-increment sequence resynchronization (prevents future ID collisions)
- Comprehensive row-count verification and dry-run mode
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import ssl
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

# Ensure repo root and backend are on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.storage.database import Base
from app.storage.models import (
    AlertModel,
    AuditEventModel,
    DetectionModel,
    MitigationModel,
    ObservationModel,
    ThresholdConfigModel,
)

# Ordered by foreign-key dependency
MIGRATION_TABLES = [
    ("threshold_configs", ThresholdConfigModel),
    ("audit_events", AuditEventModel),
    ("observations", ObservationModel),
    ("detections", DetectionModel),
    ("alerts", AlertModel),
    ("mitigations", MitigationModel),
]


def is_psycopg2_usable() -> bool:
    """Check if psycopg2 can be imported without Windows DLL / AppLocker blocking."""
    try:
        import psycopg2  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def backup_sqlite_db(source_path: Path) -> Path:
    """Create a safe backup of the source SQLite database."""
    backup_path = source_path.with_suffix(".db.bak")
    shutil.copy2(source_path, backup_path)
    print(f"📦 Backup created: {backup_path} ({backup_path.stat().st_size:,} bytes)")
    return backup_path


def read_sqlite_table(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    """Read all rows from an SQLite table as dictionaries."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


def normalize_database_url(url_str: str) -> tuple[str, dict[str, Any]]:
    """Normalize PostgreSQL URLs and determine appropriate driver and SSL settings."""
    cleaned = url_str.strip()
    driver_prefix = "postgresql+psycopg2" if is_psycopg2_usable() else "postgresql+pg8000"

    if cleaned.startswith("postgres://"):
        cleaned = f"{driver_prefix}://" + cleaned[len("postgres://") :]
    elif (
        cleaned.startswith("postgresql://")
        and "+psycopg" not in cleaned
        and "+pg8000" not in cleaned
    ):
        cleaned = f"{driver_prefix}://" + cleaned[len("postgresql://") :]

    connect_args: dict[str, Any] = {}
    if "pg8000" in cleaned:
        connect_args["ssl_context"] = ssl.create_default_context()

    return cleaned, connect_args


def migrate_data(
    sqlite_path: Path,
    postgres_url: str,
    dry_run: bool = False,
    skip_backup: bool = False,
    batch_size: int = 500,
) -> bool:
    """Execute SQLite to PostgreSQL data migration."""
    print("=" * 70)
    print("🚀 SENTRIX: SQLite to Supabase PostgreSQL Migration")
    print("=" * 70)
    print(f"Source SQLite:   {sqlite_path}")
    masked_url = postgres_url.split("@")[-1] if "@" in postgres_url else postgres_url
    print(f"Target Database: ...@{masked_url}")
    print(f"Execution Mode:  {'DRY-RUN (No changes)' if dry_run else 'LIVE TRANSFER'}")
    print("-" * 70)

    if not sqlite_path.exists():
        print(f"❌ Error: SQLite source database not found at {sqlite_path}")
        return False

    if not skip_backup and not dry_run:
        backup_sqlite_db(sqlite_path)

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)

    # 2. Connect to PostgreSQL using adaptive driver (pg8000 for Windows AppLocker / psycopg2 for Linux)
    cleaned_pg_url, connect_args = normalize_database_url(postgres_url)
    driver_used = "pg8000 (Pure Python)" if "pg8000" in cleaned_pg_url else "psycopg2"
    print(f"🔌 PostgreSQL Driver: {driver_used}")

    try:
        pg_engine = create_engine(
            cleaned_pg_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        # Test connection
        with pg_engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        print("✅ Connected to Target PostgreSQL database successfully.")
    except (SQLAlchemyError, DBAPIError, OSError) as exc:
        print(f"❌ Error connecting to PostgreSQL: {exc}")
        sqlite_conn.close()
        return False

    # 3. Ensure target schema exists
    if not dry_run:
        print("🔧 Ensuring target tables exist...")
        Base.metadata.create_all(bind=pg_engine)

    stats: dict[str, dict[str, int]] = {}

    # 4. Migrate tables in dependency-safe order
    with Session(pg_engine) as pg_session:
        for table_name, model_class in MIGRATION_TABLES:
            sqlite_rows = read_sqlite_table(sqlite_conn, table_name)
            sqlite_count = len(sqlite_rows)

            # Query existing PostgreSQL IDs to avoid duplicate key conflicts
            try:
                existing_ids = set(
                    pg_session.scalars(select(model_class.id)).all()
                )
            except SQLAlchemyError:
                existing_ids = set()

            rows_to_insert = [r for r in sqlite_rows if r["id"] not in existing_ids]

            stats[table_name] = {
                "sqlite_total": sqlite_count,
                "already_present": len(existing_ids),
                "to_insert": len(rows_to_insert),
            }

            if dry_run:
                print(
                    f"  [DRY-RUN] Table '{table_name}': {sqlite_count} in SQLite | "
                    f"{len(existing_ids)} in PG | {len(rows_to_insert)} pending insert"
                )
                continue

            if rows_to_insert:
                print(
                    f"  ⏳ Migrating '{table_name}': inserting {len(rows_to_insert)} records..."
                )
                # Batch insert
                for i in range(0, len(rows_to_insert), batch_size):
                    batch = rows_to_insert[i : i + batch_size]
                    pg_session.bulk_insert_mappings(model_class, batch)
                    pg_session.commit()

            # Resynchronize PostgreSQL auto-increment sequence
            try:
                seq_sql = text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
                )
                pg_session.execute(seq_sql)
                pg_session.commit()
            except SQLAlchemyError:
                pg_session.rollback()

    sqlite_conn.close()

    # 5. Summary Verification
    print("-" * 70)
    print(f"{'TABLE NAME':<22} | {'SQLITE':<8} | {'PG TARGET':<10} | {'STATUS'}")
    print("-" * 70)

    all_verified = True
    with Session(pg_engine) as pg_session:
        for table_name, model_class in MIGRATION_TABLES:
            sqlite_total = stats[table_name]["sqlite_total"]
            try:
                pg_total = pg_session.scalar(select(func.count(model_class.id))) or 0
            except SQLAlchemyError:
                pg_total = 0

            status_str = "MATCH ✅" if (sqlite_total <= pg_total) else "MISMATCH ⚠️"
            if sqlite_total > pg_total and not dry_run:
                all_verified = False

            print(
                f"{table_name:<22} | {sqlite_total:<8} | {pg_total:<10} | {status_str}"
            )

    print("=" * 70)
    if dry_run:
        print("💡 Dry run complete. No records were written. Run without --dry-run to execute.")
        return True
    elif all_verified:
        print("🎉 SUCCESS: All tables migrated and row counts verified!")
        return True
    else:
        print("⚠️ WARNING: Some table row counts did not match. Please inspect logs.")
        return False


def main() -> None:
    # Load .env file if available
    load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Migrate SENTRIX SQLite persistence to Supabase PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=REPO_ROOT / "sentrix.db",
        help="Path to source sentrix.db file (default: ./sentrix.db)",
    )
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL connection string (defaults to DATABASE_URL in .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate row counts without writing changes to PostgreSQL",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip creating a sentrix.db.bak backup file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for bulk inserts (default: 500)",
    )

    args = parser.parse_args()

    if not args.postgres_url or args.postgres_url.startswith("sqlite"):
        print("❌ Error: A valid PostgreSQL DATABASE_URL must be provided via --postgres-url or .env.")
        print("Example:")
        print("  python scripts/migrate_sqlite_to_postgres.py --postgres-url 'postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:5432/postgres'")
        sys.exit(1)

    success = migrate_data(
        sqlite_path=args.sqlite_path,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run,
        skip_backup=args.skip_backup,
        batch_size=args.batch_size,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
