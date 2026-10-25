import os
import uuid
from pathlib import Path

from pydantic import ValidationError

from src import schema
from src.utils import file_lock

# Files

APPLICATION_DIRECTORY = Path(__file__).resolve().parents[2]
SAVED_CONNECTIONS_PATH = APPLICATION_DIRECTORY / "saved_connections.json"
LOCK_PATH = APPLICATION_DIRECTORY / ".saved_connections.lock"
TEMP_FILE_PREFIX = ".saved_connections."
MAX_FILE_BYTES = 1024 * 1024

# Public operations


def load() -> list[schema.SavedConnection]:
    try:
        with file_lock.locked(LOCK_PATH):
            document = _read_document()
    except file_lock.FileLockError as error:
        raise RuntimeError("The saved connections file is in use.") from error
    except OSError as error:
        raise RuntimeError("Could not read the saved connections file.") from error
    return list(document.connections)


def add(
    settings: schema.ConnectionSettings,
) -> list[schema.SavedConnection]:
    connection = schema.SavedConnection(
        id=uuid.uuid4(),
        storage_directory=settings.storage_directory,
        server_url=settings.server_url,
        token=settings.token,
    )

    committed = False
    try:
        # Reload inside the lock so concurrent writers cannot lose entries
        with file_lock.locked(LOCK_PATH):
            document = _read_document()
            updated = schema.SavedConnectionFile(
                connections=[*document.connections, connection],
            )
            _write_document(updated)
            committed = True
    except file_lock.FileLockError as error:
        raise RuntimeError("The saved connections file is in use.") from error
    except OSError as error:
        if committed:
            return list(updated.connections)
        raise RuntimeError("Could not write the saved connections file.") from error
    return list(updated.connections)


def delete(connection_id: uuid.UUID) -> list[schema.SavedConnection]:
    committed = False
    try:
        # Delete against the latest file state under the same write lock
        with file_lock.locked(LOCK_PATH):
            document = _read_document()
            connections = [
                connection
                for connection in document.connections
                if connection.id != connection_id
            ]
            if len(connections) == len(document.connections):
                return list(document.connections)

            updated = schema.SavedConnectionFile(connections=connections)
            _write_document(updated)
            committed = True
    except file_lock.FileLockError as error:
        raise RuntimeError("The saved connections file is in use.") from error
    except OSError as error:
        if committed:
            return list(updated.connections)
        raise RuntimeError("Could not write the saved connections file.") from error
    return list(updated.connections)


# File operations


def _read_document() -> schema.SavedConnectionFile:
    if not SAVED_CONNECTIONS_PATH.exists():
        return schema.SavedConnectionFile()

    os.chmod(SAVED_CONNECTIONS_PATH, 0o600)
    with SAVED_CONNECTIONS_PATH.open("rb") as file:
        payload = file.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise RuntimeError("The saved connections file is too large.")

    try:
        return schema.SavedConnectionFile.model_validate_json(payload)
    except ValidationError as error:
        raise RuntimeError("The saved connections file is invalid.") from error


def _write_document(document: schema.SavedConnectionFile) -> None:
    temporary_path = APPLICATION_DIRECTORY / (
        f"{TEMP_FILE_PREFIX}{uuid.uuid4().hex}.tmp"
    )
    descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    published = False
    try:
        # Flush the complete replacement before publishing it atomically
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(document.model_dump_json(indent=2))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, SAVED_CONNECTIONS_PATH)
        published = True
    finally:
        if not published:
            temporary_path.unlink(missing_ok=True)
