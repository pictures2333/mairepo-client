from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import URL, create_engine, pool
from sqlalchemy.engine import Connection

from src.database.model import Base

# Configuration

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Migration runners


def run_migrations_offline() -> None:
    context.configure(
        url=str(_get_cli_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    external_connection = config.attributes.get("connection")
    if external_connection is not None:
        _run_migrations(external_connection)
        return

    engine = create_engine(
        _get_cli_database_url(),
        poolclass=pool.NullPool,
    )
    try:
        with engine.connect() as connection:
            _run_migrations(connection)
    finally:
        engine.dispose()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# CLI database selection


def _get_cli_database_url() -> URL:
    arguments = context.get_x_argument(as_dictionary=True)
    database_path = arguments.get("database_path")
    if not database_path:
        raise RuntimeError(
            "Pass the SQLite path with -x database_path=/path/to/mairepo.db."
        )
    return URL.create(
        "sqlite+pysqlite",
        database=str(Path(database_path).expanduser().resolve()),
    )


# Entry point

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
