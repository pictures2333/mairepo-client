from pathlib import Path

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


class ConnectionSettings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    storage_directory: Path
    server_url: HttpUrl
    token: str = ""

    @field_validator("storage_directory")
    @classmethod
    def validate_storage_directory(cls, value: Path) -> Path:
        directory = value.expanduser().resolve()
        if not directory.is_dir():
            raise ValueError("storage directory does not exist or is not a directory")
        return directory

    @property
    def normalized_server_url(self) -> str:
        return str(self.server_url).rstrip("/")
