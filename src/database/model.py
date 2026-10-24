from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Database base


class Base(DeclarativeBase):
    pass


# Tables


class Chart(Base):
    __tablename__ = "charts"

    # Remote identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Local storage
    folder_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Installed files
    files: Mapped[list["File"]] = relationship(
        back_populates="chart",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint(
            "chart_id",
            "filename",
            name="uq_files_chart_id_filename",
        ),
    )

    # Remote identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # Chart ownership
    chart_id: Mapped[int] = mapped_column(
        ForeignKey("charts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chart: Mapped[Chart] = relationship(back_populates="files")

    # Installed file state
    filename: Mapped[str] = mapped_column(String, nullable=False)
    blob_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
