from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

# Saved connection


class SavedConnection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID
    storage_directory: Path
    server_url: HttpUrl
    token: str = ""


# File format


class SavedConnectionFile(BaseModel):
    version: Literal[1] = 1
    connections: list[SavedConnection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_connection_ids(self) -> "SavedConnectionFile":
        connection_ids = [connection.id for connection in self.connections]
        if len(connection_ids) != len(set(connection_ids)):
            raise ValueError("saved connection IDs must be unique")
        return self
