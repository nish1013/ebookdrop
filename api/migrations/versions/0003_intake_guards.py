"""intake guards: book sha256 and size, library bytes used, intake events

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"

MAX_FILE_BYTES = 50 * 1024 * 1024
QUOTA_BYTES = 1024 * 1024 * 1024


def upgrade() -> None:
    op.add_column("books", sa.Column("sha256", sa.Text, nullable=False))
    op.add_column("books", sa.Column("size", sa.BigInteger, nullable=False))
    op.create_check_constraint("books_sha256", "books", "sha256 ~ '^[0-9a-f]{64}$'")
    op.create_check_constraint(
        "books_size", "books", f"size BETWEEN 1 AND {MAX_FILE_BYTES}"
    )
    op.create_unique_constraint("books_reader_sha256", "books", ["reader_id", "sha256"])
    op.create_table(
        "libraries",
        sa.Column("reader_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bytes_used", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint(
            f"bytes_used BETWEEN 0 AND {QUOTA_BYTES}", name="libraries_quota"
        ),
    )
    op.create_table(
        "intake_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("reader_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("intake_events_name_at", "intake_events", ["name", "at"])


def downgrade() -> None:
    op.drop_table("intake_events")
    op.drop_table("libraries")
    op.drop_constraint("books_reader_sha256", "books")
    op.drop_column("books", "size")
    op.drop_column("books", "sha256")
