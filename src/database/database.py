from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import alembic.command
import alembic.config
from sqlalchemy import Engine, URL, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Constants

DATABASE_FILENAME = "mairepo.db"
MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[2] / "migrations"

# State

engine: Optional[Engine] = None
session_maker: Optional[sessionmaker[Session]] = None
database_path: Optional[Path] = None

# Lifecycle


def init_db(storage_directory: Path) -> None:
    global engine, session_maker, database_path

    # Resolve the database location
    directory = storage_directory.expanduser().resolve()
    if not directory.is_dir():
        raise RuntimeError("Storage directory does not exist or is not a directory.")

    path = directory / DATABASE_FILENAME

    # Preserve an existing engine for the same database
    if engine is not None and session_maker is not None:
        if database_path == path:
            return
        raise RuntimeError("Database is already initialized for another directory.")

    # Prepare the engine without exposing partial state
    new_engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(path)),
        connect_args={"check_same_thread": False},
    )
    event.listen(new_engine, "connect", _enable_foreign_keys)

    # Upgrade the selected database before publishing the engine
    try:
        _upgrade_schema(new_engine)
    except Exception:
        new_engine.dispose()
        raise

    # Publish the initialized database state
    engine = new_engine
    session_maker = sessionmaker(new_engine, expire_on_commit=False)
    database_path = path


def close_db() -> None:
    global engine, session_maker, database_path

    # Dispose pooled connections
    if engine is not None:
        engine.dispose()

    # Clear lifecycle state
    engine = None
    session_maker = None
    database_path = None


# Sessions


@contextmanager
def get_session() -> Generator[Session, None, None]:
    # Reject use outside the database lifecycle
    if session_maker is None:
        raise RuntimeError("Database is not initialized.")

    # Always close the session at the context boundary
    with session_maker() as session:
        yield session


# Migrations


def _upgrade_schema(database_engine: Engine) -> None:
    migration_config = alembic.config.Config()
    migration_config.set_main_option(
        "script_location",
        str(MIGRATIONS_DIRECTORY),
    )

    with database_engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        alembic.command.upgrade(migration_config, "head")


# SQLite helpers


def _enable_foreign_keys(
    dbapi_connection: Any,
    _: Any,
) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
