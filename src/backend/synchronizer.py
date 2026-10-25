import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from src import crud, schema
from src.database import database, model
from . import api, chart_state, log, manifest, storage

# Logger

logger = log.get_logger("synchronizer")

ProgressCallback = Callable[[int, int], None]

# Synchronization


def sync_charts(progress: ProgressCallback) -> schema.SyncReport:
    # Fetch one remote snapshot for the complete synchronization
    remote_charts = api.fetch_chart()

    # Compare the remote snapshot with subscribed charts
    with database.get_session() as session:
        local_charts = crud.read_charts(session)

    remote_by_id = {chart.id: chart for chart in remote_charts}
    updates: list[tuple[model.Chart, schema.Chart]] = []
    missing = 0
    up_to_date = 0

    for local_chart in local_charts:
        remote_chart = remote_by_id.get(local_chart.id)
        if remote_chart is None:
            missing += 1
        elif chart_state.chart_needs_sync(
            local_chart,
            remote_chart,
        ):
            updates.append((local_chart, remote_chart))
        else:
            up_to_date += 1

    progress(0, len(updates))
    logger.info(
        "Sync plan: %d subscribed, %d updates, %d current, %d missing.",
        len(local_charts),
        len(updates),
        up_to_date,
        missing,
    )

    # Apply and commit one chart at a time
    updated = 0
    failures = []
    for index, (local_chart, remote_chart) in enumerate(updates, start=1):
        try:
            _sync_chart(
                local_chart,
                remote_chart,
            )
            updated += 1
            logger.info("Chart %d synchronized.", remote_chart.id)
        except RuntimeError as error:
            failures.append(f"{remote_chart.name}: {error}")
            logger.warning(
                "Failed to synchronize chart %d: %r",
                remote_chart.id,
                error,
            )
        finally:
            progress(index, len(updates))

    report = schema.SyncReport(
        subscribed=len(local_charts),
        updated=updated,
        up_to_date=up_to_date,
        missing=missing,
        failed=len(failures),
        failures=failures,
    )
    logger.info(
        "Sync completed: %d updated, %d failed.",
        report.updated,
        report.failed,
    )
    return report


def _sync_chart(local_chart: model.Chart, remote_chart: schema.Chart) -> None:
    # Validate the complete destination manifest before writing
    chart_directory = manifest.resolve_chart_directory(
        local_chart.id,
        local_chart.folder_name,
    )
    manifest.validate_remote_files(remote_chart.files)
    local_files = {file.id: file for file in local_chart.files}
    chart_directory.mkdir(exist_ok=True)

    prepared_files: dict[int, tuple[Optional[Path], int]] = {}
    try:
        # Prepare every remote file before changing installed files
        for remote_file in remote_chart.files:
            prepared_files[remote_file.id] = _download_blob(
                chart_directory,
                remote_file,
                local_files.get(remote_file.id),
            )

        # Stage every installed file before replacing the complete chart
        staged_files: dict[int, Path] = {}
        for local_file in local_chart.files:
            source = chart_directory / local_file.filename
            if source.is_symlink():
                raise RuntimeError("A managed file is a symbolic link.")
            if not source.exists():
                continue
            if not source.is_file():
                raise RuntimeError("A managed file path is not a regular file.")

            trash = _temporary_path(chart_directory, storage.TRASH_FILE_PREFIX)
            os.replace(source, trash)
            staged_files[local_file.id] = trash

        # Install downloaded files and restore unchanged staged files
        for remote_file in remote_chart.files:
            destination = chart_directory / remote_file.filename
            if destination.is_symlink():
                raise RuntimeError("A destination file is a symbolic link.")

            prepared, _ = prepared_files[remote_file.id]
            if prepared is None:
                prepared = staged_files.get(remote_file.id)
                if prepared is None:
                    raise RuntimeError("An unchanged local file is unavailable.")
            os.replace(prepared, destination)

        # Commit the installed manifest as one chart unit
        with database.get_session() as session:
            with session.begin():
                _update_chart_manifest(
                    session,
                    remote_chart,
                    prepared_files,
                )

    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError("Could not apply the chart update.") from error


# Database update


def _update_chart_manifest(
    session: Session,
    remote_chart: schema.Chart,
    prepared_files: dict[int, tuple[Optional[Path], int]],
) -> None:
    db_charts = crud.read_charts(session, remote_chart.id)
    if not db_charts:
        raise RuntimeError("The chart subscription no longer exists.")
    db_chart = db_charts[0]

    crud.update_chart(db_chart, remote_chart.name)

    # Remove the previous manifest before reusing IDs and filenames
    for db_file in db_chart.files:
        crud.delete_file(session, db_file)
    session.flush()

    # Store the complete installed manifest
    for remote_file in remote_chart.files:
        prepared = prepared_files.get(remote_file.id)
        if prepared is None:
            raise RuntimeError("A chart file was not prepared.")
        crud.create_file(
            session,
            file_id=remote_file.id,
            chart_id=remote_chart.id,
            filename=remote_file.filename,
            blob_id=prepared[1],
        )


# Download planning


def _download_blob(
    chart_directory: Path,
    remote_file: schema.ChartFile,
    local_file: Optional[model.File],
) -> tuple[Optional[Path], int]:
    if not remote_file.blobs:
        raise RuntimeError(f"{remote_file.filename} has no available blobs.")

    # Keep a current local file without downloading the same blob again
    blobs = sorted(remote_file.blobs, key=lambda blob: blob.id, reverse=True)
    local_exists = (
        local_file is not None
        and manifest.is_regular_file(
            chart_directory / local_file.filename,
        )
    )
    if (
        local_file is not None
        and blobs[0].id == local_file.blob_id
        and local_exists
    ):
        return None, local_file.blob_id

    # Try newer blobs in order and stop at the installed version boundary
    for blob in blobs:
        if local_file is not None:
            if blob.id < local_file.blob_id:
                break
            if blob.id == local_file.blob_id and local_exists:
                break

        temporary = _temporary_path(chart_directory, storage.TEMP_FILE_PREFIX)
        if not api.download_blob(blob.id, temporary):
            temporary.unlink(missing_ok=True)
            continue

        return temporary, blob.id

    raise RuntimeError(
        f"{remote_file.filename} has no acceptable downloadable blob."
    )


def _temporary_path(directory: Path, prefix: str) -> Path:
    return directory / f"{prefix}{uuid.uuid4().hex}"
