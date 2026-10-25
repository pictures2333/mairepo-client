import shutil
from pathlib import Path
from typing import Optional

from src import crud
from src.database import database
from . import log, storage

# Logger

logger = log.get_logger("gc")

# Garbage collection


def collect() -> None:
    logger.info("GC started.")

    # Resolve the complete managed storage snapshot
    storage_directory = storage.get_storage_directory()
    with database.get_session() as session:
        managed_folder_names = {
            chart.folder_name
            for chart in crud.read_charts(session)
        }

    # Inspect only client-owned entries at the storage root
    storage_entries = _read_directory(storage_directory)
    if storage_entries is None:
        logger.info("GC completed.")
        return

    for child in storage_entries:
        if not child.name.startswith(storage.CHART_DIRECTORY_PREFIX):
            continue

        # Managed chart directories without a subscription
        if child.name not in managed_folder_names:
            try:
                if child.is_symlink() or child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    shutil.rmtree(child)
                else:
                    continue
            except OSError as error:
                logger.warning(
                    "Failed to remove chart entry %r: %r",
                    str(child),
                    error,
                )
            continue

        # Collect interrupted sync files at the chart root
        try:
            if child.is_symlink() or not child.is_dir():
                continue
        except OSError as error:
            logger.warning(
                "Failed to inspect chart entry %r: %r",
                str(child),
                error,
            )
            continue
        temporary_entries = _read_directory(child)
        if temporary_entries is None:
            continue
        for temporary in temporary_entries:
            if not temporary.name.startswith(
                (storage.TEMP_FILE_PREFIX, storage.TRASH_FILE_PREFIX)
            ):
                continue
            try:
                if temporary.is_symlink() or temporary.is_file():
                    temporary.unlink(missing_ok=True)
            except OSError as error:
                logger.warning(
                    "Failed to remove temporary entry %r: %r",
                    str(temporary),
                    error,
                )
                continue

    logger.info("GC completed.")


# Helpers


def _read_directory(directory: Path) -> Optional[list[Path]]:
    try:
        return list(directory.iterdir())
    except OSError as error:
        logger.warning(
            "Failed to inspect directory %r: %r",
            str(directory),
            error,
        )
        return None
