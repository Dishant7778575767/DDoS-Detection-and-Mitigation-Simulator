"""Database cleanup and reset script for SENTRIX.

Safely purges all 8 database tables from PostgreSQL (Supabase) or SQLite:
  1. simulation_ticks
  2. simulation_runs
  3. mitigations
  4. alerts
  5. detections
  6. observations
  7. audit_events
  8. threshold_configs (cleared and reset to fresh default v1.0.0)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

from app.core.config import get_settings
from app.storage.database import get_session_factory, init_db
from app.storage.models import (
    AlertModel,
    AuditEventModel,
    DetectionModel,
    MitigationModel,
    ObservationModel,
    SimulationRunModel,
    SimulationTickModel,
    ThresholdConfigModel,
)
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError


def clear_database_tables(db_url: str | None = None, confirm: bool = False) -> None:
    settings = get_settings()
    effective_url = db_url or settings.database_url
    db_target = effective_url.split("@")[-1] if "@" in effective_url else effective_url

    print("=" * 80)
    print("SENTRIX DATABASE RESET UTILITY (ALL 8 TABLES)")
    print("=" * 80)
    print(f"Target Database: {db_target}")

    if not confirm:
        print(
            "\nWARNING: This will permanently purge all existing records from all 8 tables:"
        )
        print("  1. simulation_ticks")
        print("  2. simulation_runs")
        print("  3. mitigations")
        print("  4. alerts")
        print("  5. detections")
        print("  6. observations")
        print("  7. audit_events")
        print("  8. threshold_configs (reset back to factory default v1.0.0)")
        print("\nTable schemas will be preserved.")
        response = input("\nAre you sure you want to proceed? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Operation aborted. No data was deleted.")
            return

    try:
        # Override settings database_url if custom db_url provided
        if db_url:
            settings.database_url = db_url

        # Ensure tables exist
        init_db(settings)
    except (SQLAlchemyError, OSError) as exc:
        print(f"\n[ERROR] Unable to connect to database at {db_target}: {exc}")
        print("\nTroubleshooting:")
        print("  1. Verify your internet connection if connecting to Supabase.")
        print(
            "  2. If running inside a restricted sandbox, run outside the sandbox or pass --database-url."
        )
        print(
            "  3. Check that DATABASE_URL in .env is correct and password does not contain unescaped special characters."
        )
        sys.exit(1)

    session_factory = get_session_factory(settings)
    with session_factory() as session:
        # Measure row counts before deletion across all 8 tables
        counts_before = {
            "simulation_ticks": session.scalar(
                select(func.count(SimulationTickModel.id))
            )
            or 0,
            "simulation_runs": session.scalar(select(func.count(SimulationRunModel.id)))
            or 0,
            "mitigations": session.scalar(select(func.count(MitigationModel.id))) or 0,
            "alerts": session.scalar(select(func.count(AlertModel.id))) or 0,
            "detections": session.scalar(select(func.count(DetectionModel.id))) or 0,
            "observations": session.scalar(select(func.count(ObservationModel.id)))
            or 0,
            "audit_events": session.scalar(select(func.count(AuditEventModel.id))) or 0,
            "threshold_configs": session.scalar(
                select(func.count(ThresholdConfigModel.id))
            )
            or 0,
        }

        print("\nPurging all 8 tables in topological dependency order...")

        # 1. Child simulation ticks
        session.execute(delete(SimulationTickModel))
        session.commit()
        print(
            f"  [1/8] Cleared simulation_ticks     ({counts_before['simulation_ticks']} rows removed)"
        )

        # 2. Parent simulation runs
        session.execute(delete(SimulationRunModel))
        session.commit()
        print(
            f"  [2/8] Cleared simulation_runs      ({counts_before['simulation_runs']} rows removed)"
        )

        # 3. Mitigations
        session.execute(delete(MitigationModel))
        session.commit()
        print(
            f"  [3/8] Cleared mitigations          ({counts_before['mitigations']} rows removed)"
        )

        # 4. Alerts
        session.execute(delete(AlertModel))
        session.commit()
        print(
            f"  [4/8] Cleared alerts               ({counts_before['alerts']} rows removed)"
        )

        # 5. Detections
        session.execute(delete(DetectionModel))
        session.commit()
        print(
            f"  [5/8] Cleared detections           ({counts_before['detections']} rows removed)"
        )

        # 6. Observations
        session.execute(delete(ObservationModel))
        session.commit()
        print(
            f"  [6/8] Cleared observations         ({counts_before['observations']} rows removed)"
        )

        # 7. Audit events
        session.execute(delete(AuditEventModel))
        session.commit()
        print(
            f"  [7/8] Cleared audit_events         ({counts_before['audit_events']} rows removed)"
        )

        # 8. Threshold configurations (clear custom updates and restore fresh default config)
        session.execute(delete(ThresholdConfigModel))
        default_cfg = ThresholdConfigModel(
            version="v1.0.0",
            is_active=True,
            pps_threshold=5000.0,
            bps_threshold=10000000.0,
            syn_pps_threshold=500.0,
            syn_ack_ratio_threshold=5.0,
            rf_probability_threshold=0.75,
            iforest_score_threshold=0.2664,
            updated_by="system",
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        session.add(default_cfg)
        session.commit()
        print(
            f"  [8/8] Reset threshold_configs      ({counts_before['threshold_configs']} rows purged -> seeded fresh default v1.0.0)"
        )

    print("\n" + "=" * 80)
    print(
        "DATABASE RESET COMPLETE: All 8 tables are 100% clean and ready for simulations!"
    )
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset and purge all 8 SENTRIX tables for clean simulation testing."
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional database URL override (e.g. Supabase postgresql:// or sqlite:///...).",
    )
    parser.add_argument(
        "-y",
        "--yes",
        "--force",
        action="store_true",
        help="Skip interactive confirmation prompt and purge immediately.",
    )
    args = parser.parse_args()
    clear_database_tables(db_url=args.database_url, confirm=args.yes)


if __name__ == "__main__":
    main()
