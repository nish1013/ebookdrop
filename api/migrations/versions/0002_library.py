"""library: books, conversion jobs, book events

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("reader_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.Text),
        sa.Column("format", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("has_cover", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="books_status"
        ),
        sa.CheckConstraint("format IN ('epub', 'pdf')", name="books_format"),
    )
    op.create_index("books_reader_received", "books", ["reader_id", "received_at"])
    op.create_table(
        "conversion_jobs",
        sa.Column(
            "book_id",
            UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "conversion_jobs_waiting",
        "conversion_jobs",
        ["queued_at"],
        postgresql_where=sa.text("started_at IS NULL"),
    )
    op.create_table(
        "book_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("book_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("book_events_name_at", "book_events", ["name", "at"])
    op.create_index("book_events_book", "book_events", ["book_id"])


def downgrade() -> None:
    op.drop_table("book_events")
    op.drop_table("conversion_jobs")
    op.drop_table("books")
