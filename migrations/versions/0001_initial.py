"""Create the initial client database schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers

revision: str = "0001_initial"
down_revision: Optional[str] = None
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None

# Migrations


def upgrade() -> None:
    # Subscribed charts
    op.create_table(
        "charts",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("folder_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder_name"),
    )

    # Installed chart files
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("chart_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("blob_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chart_id"],
            ["charts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blob_id"),
        sa.UniqueConstraint(
            "chart_id",
            "filename",
            name="uq_files_chart_id_filename",
        ),
    )
    op.create_index("ix_files_chart_id", "files", ["chart_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_files_chart_id", table_name="files")
    op.drop_table("files")
    op.drop_table("charts")
