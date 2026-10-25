from pathlib import Path
from typing import Optional

from src import schema
from . import storage

# Remote manifest validation


def validate_remote_files(
    remote_files: list[schema.ChartFile],
) -> dict[int, schema.ChartFile]:
    files_by_id = {}
    filenames = set()
    for remote_file in remote_files:
        _validate_filename(remote_file.filename)
        normalized_filename = remote_file.filename.casefold()
        if remote_file.id in files_by_id or normalized_filename in filenames:
            raise RuntimeError("The remote chart contains duplicate files.")
        files_by_id[remote_file.id] = remote_file
        filenames.add(normalized_filename)
    return files_by_id


def _validate_filename(filename: str) -> None:
    reserved_names = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
    stem = filename.split(".", 1)[0].casefold()
    if (
        not filename
        or filename in (".", "..")
        or any(character in filename for character in '<>:"/\\|?*\0')
        or filename.endswith((" ", "."))
        or stem in reserved_names
    ):
        raise RuntimeError("The remote chart contains an unsafe filename.")


# Local manifest validation


def resolve_chart_directory(
    chart_id: int,
    folder_name: str,
) -> Path:
    if folder_name != storage.create_chart_folder_name(chart_id):
        raise RuntimeError("The chart folder name is invalid.")

    storage_directory = storage.get_storage_directory().resolve()
    chart_directory = storage_directory / folder_name
    if chart_directory.is_symlink():
        raise RuntimeError("The chart directory is a symbolic link.")
    if chart_directory.exists() and not chart_directory.is_dir():
        raise RuntimeError("The chart directory path is not a directory.")
    return chart_directory


def is_regular_file(path: Optional[Path]) -> bool:
    return (
        path is not None
        and not path.is_symlink()
        and path.is_file()
    )
