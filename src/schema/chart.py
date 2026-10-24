from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


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


chart_index_adapter = TypeAdapter(list[Chart])
