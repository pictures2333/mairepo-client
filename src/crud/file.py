from sqlalchemy.orm import Session

from src.database import model

# Write


def create_file(
    session: Session,
    file_id: int,
    chart_id: int,
    filename: str,
    blob_id: int,
) -> model.File:
    file = model.File(
        id=file_id,
        chart_id=chart_id,
        filename=filename,
        blob_id=blob_id,
    )
    session.add(file)
    return file


def delete_file(session: Session, file: model.File) -> None:
    session.delete(file)
