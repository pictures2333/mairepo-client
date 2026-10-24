from pathlib import Path
from typing import Optional

from src import schema
from src.utils import api
from . import storage

# State

settings: Optional[schema.ConnectionSettings] = None
charts: list[schema.Chart] = []
subscribed_chart_ids: set[int] = set()

# Lifecycle


def connect(connection_settings: schema.ConnectionSettings) -> None:
    global settings, charts

    try:
        # Acquire storage before accepting remote state
        storage.acquire(connection_settings.storage_directory)
        remote_charts = api.fetch_chart_index(connection_settings)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(str(error)) from error

    # Publish the new connection state together
    settings = connection_settings
    charts = remote_charts
    subscribed_chart_ids.clear()


def refresh() -> None:
    global charts

    if settings is None:
        raise RuntimeError("The client is not connected to a server.")

    # Fetch before replacing the current usable index
    try:
        remote_charts = api.fetch_chart_index(settings)
    except RuntimeError as error:
        raise RuntimeError(str(error)) from error

    # Keep subscriptions that still exist remotely
    charts = remote_charts
    subscribed_chart_ids.intersection_update(chart.id for chart in charts)


# Subscriptions


def set_subscription(chart_id: int, subscribed: bool) -> None:
    # Reject stale UI selections
    if not any(chart.id == chart_id for chart in charts):
        raise RuntimeError("The selected chart is no longer available.")

    # Update the in-memory selection
    if subscribed:
        subscribed_chart_ids.add(chart_id)
    else:
        subscribed_chart_ids.discard(chart_id)


# State snapshots


def get_charts() -> list[schema.Chart]:
    return list(charts)


def get_subscribed_chart_ids() -> set[int]:
    return set(subscribed_chart_ids)


def get_server_url() -> str:
    return settings.normalized_server_url if settings else ""


def get_storage_directory() -> Optional[Path]:
    return settings.storage_directory if settings else None


def is_connected() -> bool:
    return settings is not None


def close() -> None:
    global settings, charts

    # Release external resources first
    try:
        storage.release()
    except OSError as error:
        raise RuntimeError("Could not release the storage lock.") from error
    finally:
        # Clear state even when lock release reports an error
        settings = None
        charts = []
        subscribed_chart_ids.clear()
