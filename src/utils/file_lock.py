import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

# Errors


class FileLockError(RuntimeError):
    pass


# Lifecycle


def acquire(path: Path) -> IO[bytes]:
    file = path.open("a+b")
    try:
        os.chmod(path, 0o600)
        _lock(file)
    except Exception:
        file.close()
        raise
    return file


def release(file: IO[bytes]) -> None:
    try:
        _unlock(file)
    finally:
        file.close()


@contextmanager
def locked(path: Path) -> Iterator[IO[bytes]]:
    file = acquire(path)
    try:
        yield file
    finally:
        release(file)


# Platform helpers


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
            raise FileLockError("The file is already locked.") from error
        return

    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise FileLockError("The file is already locked.") from error


def _unlock(file: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(file.fileno(), fcntl.LOCK_UN)
