from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Optional

from src import crud, schema
from src.database import database
from . import api, chart_state, gc, log, storage, synchronizer

# Logger

logger = log.get_logger("service")

# State

operation_lock = RLock()

# Lifecycle


def connect(connection_settings: schema.ConnectionSettings) -> None:
    with operation_lock:
        logger.info("Backend connection started.")
        if storage.is_initialized():
            raise RuntimeError("The client is already connected.")

        try:
            # Acquire storage before opening its database
            storage.acquire(connection_settings)
            _init_database()
        except Exception as error:
            logger.error("Backend connection failed: %r", error)

            # Leave no partially opened backend after a failed connection
            try:
                database.close_db()
            finally:
                storage.release()

            if isinstance(error, (OSError, RuntimeError)):
                raise RuntimeError(str(error)) from error
            raise RuntimeError("Could not initialize local storage.") from error

        logger.info("Backend initialized.")


def refresh() -> list[schema.ChartState]:
    with operation_lock:
        storage.get_settings()
        logger.info("Remote index refresh started.")

        # Fetch and compare one current remote snapshot
        try:
            gc.collect()
            remote_charts = api.fetch_chart()
            chart_states = _build_chart_states(remote_charts)
        except Exception as error:
            logger.error("Remote index refresh failed: %r", error)
            raise
        logger.info("Remote index refresh completed.")
        return chart_states


def close() -> None:
    with operation_lock:
        logger.info("Backend shutdown started.")
        first_error: Optional[Exception] = None

        # Best-effort shutdown garbage collection
        if storage.is_initialized():
            try:
                gc.collect()
            except Exception as error:
                logger.warning("Shutdown GC failed: %r", error)

        # Close pooled HTTP connections
        try:
            api.close()
        except Exception as error:
            logger.warning("Failed to close the HTTP client: %r", error)
            first_error = first_error or error

        # Close the database before releasing storage ownership
        try:
            database.close_db()
        except Exception as error:
            logger.warning("Failed to close the database: %r", error)
            first_error = first_error or error

        try:
            storage.release()
        except Exception as error:
            logger.warning("Failed to release the storage lock: %r", error)
            first_error = first_error or error

        if first_error is not None:
            logger.error("Backend shutdown completed with errors.")
            raise RuntimeError("Could not close the backend cleanly.") from first_error
        logger.info("Backend shutdown completed.")


# Subscriptions


def set_subscription(
    chart_id: int,
    target_subscribed: bool,
) -> None:
    with operation_lock:
        storage.get_settings()
        target_state = "subscribed" if target_subscribed else "unsubscribed"
        logger.info(
            "Subscription update started: chart %d -> %s.",
            chart_id,
            target_state,
        )

        try:
            # Resolve only the requested chart from the server
            remote_charts = api.fetch_chart(chart_id)
            remote_chart = remote_charts[0] if remote_charts else None

            # Commit the subscription change immediately
            with database.get_session() as session:
                with session.begin():
                    local_charts = crud.read_charts(session, chart_id)
                    local_chart = local_charts[0] if local_charts else None
                    if target_subscribed:
                        if remote_chart is None:
                            raise RuntimeError(
                                "The selected chart is no longer available."
                            )
                        if local_chart is None:
                            crud.create_chart(
                                session,
                                chart_id=remote_chart.id,
                                name=remote_chart.name,
                                folder_name=storage.create_chart_folder_name(
                                    remote_chart.id,
                                ),
                            )
                    elif local_chart is not None:
                        crud.delete_chart(session, local_chart)

            # Remove newly orphaned chart directories without a background task
            if not target_subscribed:
                gc.collect()
        except Exception as error:
            logger.error(
                "Subscription update failed for chart %d: %r",
                chart_id,
                error,
            )
            raise

        logger.info("Chart %d is now %s.", chart_id, target_state)


# Synchronization


def sync(
    progress: Callable[[int, int], None],
) -> schema.SyncReport:
    with operation_lock:
        storage.get_settings()
        logger.info("Synchronization started.")

        try:
            # Pre-sync cleanup
            gc.collect()

            report = synchronizer.sync_charts(progress)

            # Post-sync cleanup
            gc.collect()
        except Exception as error:
            logger.error("Synchronization failed: %r", error)
            raise

        logger.info("Synchronization finished.")
        return report


def get_server_url() -> str:
    with operation_lock:
        if not storage.is_initialized():
            return ""
        return storage.get_server_url()


def get_storage_directory() -> Optional[Path]:
    with operation_lock:
        if not storage.is_initialized():
            return None
        return storage.get_storage_directory()


def is_connected() -> bool:
    with operation_lock:
        return storage.is_initialized()


# Helpers


def _init_database() -> None:
    storage_directory = storage.get_storage_directory()
    expected_path = storage_directory / database.DATABASE_FILENAME
    if database.database_path is not None and database.database_path != expected_path:
        database.close_db()
    database.init_db(storage_directory)


def _build_chart_states(
    remote_charts: list[schema.Chart],
) -> list[schema.ChartState]:
    with database.get_session() as session:
        local_charts = crud.read_charts(session)
    return chart_state.build_chart_states(
        remote_charts,
        local_charts,
    )
