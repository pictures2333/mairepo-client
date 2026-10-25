import os
from pathlib import Path
from typing import IO, Optional

from src import schema
from . import log

# Logger

logger = log.get_logger("storage")

# Constants

CHART_DIRECTORY_PREFIX = "mairepo-chart-"
LOCK_FILENAME = ".mairepo.lock"
TEMP_FILE_PREFIX = ".mairepo-tmp-"
TRASH_FILE_PREFIX = ".mairepo-trash-"

# State

_lock_file: Optional[IO[bytes]] = None
_settings: Optional[schema.ConnectionSettings] = None

# Lifecycle


def acquire(connection_settings: schema.ConnectionSettings) -> None:
    global _lock_file, _settings

    directory = connection_settings.storage_directory

    # Keep one connection context for the complete application lifetime
    if _lock_file is not None:
        if _settings == connection_settings:
            return
        raise RuntimeError(
            "Restart the client before changing the connection settings."
        )

    # Acquire and publish the storage lock
    lock_path = directory / LOCK_FILENAME
    new_lock_file = lock_path.open("a+b")
    try:
        os.chmod(lock_path, 0o600)
        _lock(new_lock_file)
    except (OSError, RuntimeError):
        new_lock_file.close()
        raise

    _lock_file = new_lock_file
    _settings = connection_settings
    logger.info("Storage lock acquired.")


def release() -> None:
    global _lock_file, _settings

    if _lock_file is None:
        return

    # Clear shared state before closing the handle
    current_lock_file = _lock_file
    _lock_file = None
    _settings = None
    _release_file(current_lock_file)
    logger.info("Storage lock released.")


# Runtime settings


def get_settings() -> schema.ConnectionSettings:
    if _settings is None:
        raise RuntimeError("Storage is not initialized.")
    return _settings


def get_storage_directory() -> Path:
    return get_settings().storage_directory


def get_server_url() -> str:
    return get_settings().normalized_server_url


def is_initialized() -> bool:
    return _settings is not None and _lock_file is not None


# Chart paths


def create_chart_folder_name(chart_id: int) -> str:
    return f"{CHART_DIRECTORY_PREFIX}{chart_id}"


# Platform helpers


def _lock(file: IO[bytes]) -> None:
    # Windows byte-range lock
    if os.name == "nt":
        import msvcrt

        try:
            file.seek(0)
            if file.read(1) == b"":
                file.write(b"0")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError(
                "The storage directory is already in use by another client."
            ) from error
        return

    # POSIX advisory lock
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise RuntimeError(
            "The storage directory is already in use by another client."
        ) from error


def _release_file(file: IO[bytes]) -> None:
    try:
        # Unlock with the matching platform primitive
        if os.name == "nt":
            import msvcrt

            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    finally:
        file.close()
