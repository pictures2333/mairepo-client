from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

# Remote chart schema


class Blob(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[int, Field(gt=0)]
    drive_revision_id: Annotated[str, Field(min_length=1)]
    created_at: datetime


class ChartFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[int, Field(gt=0)]
    filename: Annotated[str, Field(min_length=1)]
    drive_head_revision_id: Annotated[str, Field(min_length=1)]
    blobs: list[Blob]


class Chart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Annotated[int, Field(gt=0)]
    name: Annotated[str, Field(min_length=1)]
    files: list[ChartFile]


# Local chart state


class ChartState(BaseModel):
    id: int
    name: str
    subscribed: bool
    missing: bool
    outdated: bool


# Synchronization result


class SyncReport(BaseModel):
    subscribed: int
    updated: int
    up_to_date: int
    missing: int
    failed: int
    failures: list[str]


# Index validator

chart_index_adapter = TypeAdapter(list[Chart])
