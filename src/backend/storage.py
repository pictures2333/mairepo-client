import os
from pathlib import Path
from typing import IO, Optional

LOCK_FILENAME = ".mairepo.lock"

lock_file: Optional[IO[bytes]] = None
storage_directory: Optional[Path] = None


def acquire(directory: Path) -> None:
    global lock_file, storage_directory

    if lock_file is not None and storage_directory == directory:
        return

    lock_path = directory / LOCK_FILENAME
    new_lock_file = lock_path.open("a+b")
    try:
        os.chmod(lock_path, 0o600)
        _lock(new_lock_file)
    except (OSError, RuntimeError):
        new_lock_file.close()
        raise

    old_lock_file = lock_file
    lock_file = new_lock_file
    storage_directory = directory

    if old_lock_file is not None:
        _release_file(old_lock_file)


def release() -> None:
    global lock_file, storage_directory

    if lock_file is None:
        return

    current_lock_file = lock_file
    lock_file = None
    storage_directory = None
    _release_file(current_lock_file)


def _lock(file: IO[bytes]) -> None:
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

    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise RuntimeError(
            "The storage directory is already in use by another client."
        ) from error


def _release_file(file: IO[bytes]) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    finally:
        file.close()
