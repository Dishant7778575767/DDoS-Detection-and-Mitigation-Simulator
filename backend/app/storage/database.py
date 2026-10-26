import ssl
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def is_psycopg2_usable() -> bool:
    try:
        import psycopg2  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def create_database_engine(database_url: str) -> Engine:
    cleaned = database_url.strip()
    driver_prefix = (
        "postgresql+psycopg2" if is_psycopg2_usable() else "postgresql+pg8000"
    )

    if cleaned.startswith("postgres://"):
        cleaned = f"{driver_prefix}://" + cleaned[len("postgres://") :]
    elif (
        cleaned.startswith("postgresql://")
        and "+psycopg" not in cleaned
        and "+pg8000" not in cleaned
    ):
        cleaned = f"{driver_prefix}://" + cleaned[len("postgresql://") :]

    url = make_url(cleaned)
    if url.drivername == "sqlite":
        return _create_sqlite_engine(cleaned, url.database)
    if url.drivername.startswith("postgresql"):
        return _create_postgres_engine(cleaned)

    raise ValueError(
        f"Unsupported database dialect '{url.drivername}'. Only SQLite and PostgreSQL are supported."
    )


@lru_cache(maxsize=8)
def _create_sqlite_engine(database_url: str, database: str | None) -> Engine:
    if database not in (None, "", ":memory:"):
        Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)

    return create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )


@lru_cache(maxsize=8)
def _create_postgres_engine(database_url: str) -> Engine:
    connect_args = {}
    if "pg8000" in database_url:
        connect_args["ssl_context"] = ssl.create_default_context()

    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )


@lru_cache(maxsize=8)
def _session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_database_engine(database_url),
        autoflush=False,
        expire_on_commit=False,
    )


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    database_url = (
        settings.database_url if settings is not None else get_settings().database_url
    )
    return _session_factory(database_url)


def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        yield session


def init_db(settings: Settings | None = None) -> None:
    """Initialize database tables and seed initial threshold configuration idempotently."""
    import app.storage.models  # noqa: F401
    from app.storage.repositories import ThresholdConfigRepository

    s = settings or get_settings()
    engine = create_database_engine(s.database_url)
    Base.metadata.create_all(bind=engine)

    session_factory = get_session_factory(s)
    with session_factory() as session:
        repo = ThresholdConfigRepository(session)
        repo.get_active()
