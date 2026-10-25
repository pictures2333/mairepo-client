from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.database import model

# Read


def read_charts(
    session: Session,
    chart_id: Optional[int] = None,
) -> list[model.Chart]:
    statement = select(model.Chart).options(selectinload(model.Chart.files))
    if chart_id is not None:
        statement = statement.where(model.Chart.id == chart_id)
    return list(session.scalars(statement))


# Write


def create_chart(
    session: Session,
    chart_id: int,
    name: str,
    folder_name: str,
) -> model.Chart:
    chart = model.Chart(
        id=chart_id,
        name=name,
        folder_name=folder_name,
    )
    session.add(chart)
    return chart


def update_chart(chart: model.Chart, name: str) -> None:
    chart.name = name


def delete_chart(session: Session, chart: model.Chart) -> None:
    session.delete(chart)
